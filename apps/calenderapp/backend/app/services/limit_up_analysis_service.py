"""
涨停股分析服务
仅负责从 MinIO 读取并导入已产出的 Markdown 分析报告。
"""

import os
import re
import hmac
import hashlib
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from sqlalchemy import and_, select

from app.models.limit_up_analysis import LimitUpAnalysis
from app.models.limit_up_stock import LimitUpStock
from app.utils.cache import CACHE_MEDIUM, api_cache
from app.db import session_scope


class LimitUpAnalysisService:
    """涨停股分析服务。"""

    MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "127.0.0.1:9010")
    MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
    MINIO_BUCKET = os.environ.get("MINIO_DEFAULT_BUCKET", "stockinfo")
    MINIO_REGION = os.environ.get("MINIO_REGION", "us-east-1")

    @classmethod
    def _report_stock_code(cls, stock_code: str) -> str:
        code = (stock_code or "").strip().upper()
        if "." in code:
            code = code.split(".", 1)[0]
        return code

    @classmethod
    def _stock_code_candidates(cls, stock_code: str) -> List[str]:
        raw = (stock_code or "").strip().upper()
        if not raw:
            return []

        candidates: List[str] = []
        seen = set()

        def add(value: str) -> None:
            value = (value or "").strip().upper()
            if value and value not in seen:
                seen.add(value)
                candidates.append(value)

        add(raw)
        base = cls._report_stock_code(raw)
        add(base)

        if base.isdigit():
            if base.startswith(("60", "68")):
                add(f"{base}.SH")
            elif base.startswith(("00", "30", "20")):
                add(f"{base}.SZ")

        return candidates

    @classmethod
    def _normalize_report_name(cls, value: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"\.md$", "", text, flags=re.IGNORECASE)
        return re.sub(r"[\W_]+", "", text, flags=re.UNICODE).lower()

    @classmethod
    def _limit_up_snapshot(cls, limit_up: LimitUpStock) -> Dict[str, Any]:
        return {
            "id": limit_up.id,
            "stock_code": limit_up.stock_code,
            "stock_name": limit_up.stock_name,
            "strength_level": limit_up.strength_level,
            "industry": limit_up.industry,
            "is_dragon_head": limit_up.is_dragon_head,
            "dragon_rank": limit_up.dragon_rank,
        }

    @classmethod
    def _extract_markdown_table_value(cls, report_text: str, field_name: str) -> Optional[str]:
        target = f"| {field_name} |"
        for line in report_text.splitlines():
            if not line.startswith("|") or target not in line:
                continue
            parts = [part.strip() for part in line.split("|")[1:-1]]
            if len(parts) >= 2 and parts[0] == field_name:
                return parts[1] or None
        return None

    @classmethod
    def _extract_section_text(cls, report_text: str, heading: str) -> Optional[str]:
        lines = report_text.splitlines()
        start_idx = None
        for idx, line in enumerate(lines):
            if line.strip() == heading:
                start_idx = idx + 1
                break
        if start_idx is None:
            return None

        collected = []
        for line in lines[start_idx:]:
            if line.strip().startswith("## "):
                break
            collected.append(line)

        content = "\n".join(collected).strip()
        return content or None

    @classmethod
    def _aws_signature_key(cls, date_stamp: str) -> bytes:
        secret = f"AWS4{cls.MINIO_SECRET_KEY}".encode("utf-8")
        k_date = hmac.new(secret, date_stamp.encode("utf-8"), hashlib.sha256).digest()
        k_region = hmac.new(k_date, cls.MINIO_REGION.encode("utf-8"), hashlib.sha256).digest()
        k_service = hmac.new(k_region, b"s3", hashlib.sha256).digest()
        return hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()

    @classmethod
    def _minio_request(cls, method: str, path: str, query: Optional[Dict[str, str]] = None) -> bytes:
        now = datetime.utcnow()
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(b"").hexdigest()

        canonical_uri = "/" + quote(path.lstrip("/"), safe="/~")
        query = query or {}
        encoded_query_pairs = []
        for key in sorted(query.keys()):
            encoded_query_pairs.append(
                f"{quote(str(key), safe='-_.~')}={quote(str(query[key]), safe='-_.~')}"
            )
        canonical_querystring = "&".join(encoded_query_pairs)

        host = cls.MINIO_ENDPOINT
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = (
            f"{method}\n{canonical_uri}\n{canonical_querystring}\n"
            f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )
        credential_scope = f"{date_stamp}/{cls.MINIO_REGION}/s3/aws4_request"
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )
        signature = hmac.new(
            cls._aws_signature_key(date_stamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            f"AWS4-HMAC-SHA256 Credential={cls.MINIO_ACCESS_KEY}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        scheme = "https" if cls.MINIO_SECURE else "http"
        url = f"{scheme}://{host}{canonical_uri}"
        if canonical_querystring:
            url = f"{url}?{canonical_querystring}"

        req = Request(
            url,
            method=method,
            headers={
                "Authorization": authorization,
                "x-amz-content-sha256": payload_hash,
                "x-amz-date": amz_date,
                "Host": host,
            },
        )
        with urlopen(req, timeout=15) as resp:
            return resp.read()

    @classmethod
    def _minio_list_objects(cls, prefix: str, max_keys: int = 50) -> List[str]:
        try:
            payload = cls._minio_request(
                "GET",
                cls.MINIO_BUCKET,
                {"list-type": "2", "prefix": prefix, "max-keys": str(max_keys)},
            )
        except (HTTPError, URLError, TimeoutError):
            return []

        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return []

        items: List[str] = []
        for elem in root.iter():
            if elem.tag.endswith("Key") and elem.text:
                items.append(elem.text)
        return items

    @classmethod
    def _minio_get_text(cls, object_name: str) -> Optional[str]:
        try:
            payload = cls._minio_request("GET", f"{cls.MINIO_BUCKET}/{object_name}")
        except (HTTPError, URLError, TimeoutError):
            return None
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            return payload.decode("utf-8", errors="replace")

    @classmethod
    def _find_external_report_object(cls, stock_code: str, stock_name: str, analysis_date: date) -> Optional[str]:
        code = cls._report_stock_code(stock_code)
        prefix = f"{analysis_date.strftime('%Y/%m/%d')}/{code}_"
        expected_name = f"{prefix}{stock_name}.md"

        candidates = cls._minio_list_objects(prefix=prefix, max_keys=100)
        if not candidates:
            return None
        if expected_name in candidates:
            return expected_name

        normalized_stock_name = cls._normalize_report_name(stock_name)
        exact_matches = []
        fuzzy_matches = []
        for object_name in candidates:
            if not object_name.lower().endswith(".md"):
                continue
            basename = object_name.rsplit("/", 1)[-1]
            candidate_name = basename.split("_", 1)[1] if "_" in basename else basename
            normalized_candidate = cls._normalize_report_name(candidate_name)
            if normalized_candidate == normalized_stock_name:
                exact_matches.append(object_name)
            elif normalized_stock_name and (
                normalized_candidate.startswith(normalized_stock_name)
                or normalized_stock_name.startswith(normalized_candidate)
            ):
                fuzzy_matches.append(object_name)

        if exact_matches:
            return sorted(exact_matches)[0]
        if fuzzy_matches:
            return sorted(fuzzy_matches)[0]

        markdown_candidates = sorted(name for name in candidates if name.lower().endswith(".md"))
        return markdown_candidates[0] if markdown_candidates else None

    @classmethod
    def _load_external_report(cls, stock_code: str, stock_name: str, analysis_date: date) -> Optional[Dict[str, Any]]:
        object_name = cls._find_external_report_object(stock_code, stock_name, analysis_date)
        if not object_name:
            return None

        report_text = cls._minio_get_text(object_name)
        if not report_text:
            return None

        filename = object_name.rsplit("/", 1)[-1]
        parsed_stock_name = filename[:-3].split("_", 1)[1] if "_" in filename else stock_name
        industry = cls._extract_markdown_table_value(report_text, "所属行业")
        main_event = cls._extract_markdown_table_value(report_text, "事件")
        reason_detail = cls._extract_section_text(report_text, "## 上涨核心逻辑")

        return {
            "stock_name": parsed_stock_name.strip() or stock_name,
            "industry": industry,
            "main_event": main_event,
            "reason_detail": reason_detail,
            "full_report": report_text,
            "analysis_source": "minio-stockinfo",
            "source_object": object_name,
        }

    @classmethod
    @api_cache(ttl=CACHE_MEDIUM, maxsize=5000)
    def has_external_report(cls, stock_code: str, stock_name: str, analysis_date: date) -> bool:
        return cls._find_external_report_object(stock_code, stock_name, analysis_date) is not None

    @classmethod
    def _import_external_report(
        cls,
        limit_up_data: Dict[str, Any],
        analysis_date: date,
        report_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        with session_scope() as session:
            existing = session.execute(
                select(LimitUpAnalysis).where(
                    and_(
                        LimitUpAnalysis.stock_code == limit_up_data["stock_code"],
                        LimitUpAnalysis.analysis_date == analysis_date,
                    )
                )
            ).scalars().first()

            strength_rating = max(1, min(5, int(limit_up_data.get("strength_level") or 3)))
            stock_name = report_data.get("stock_name") or limit_up_data["stock_name"]
            industry = report_data.get("industry") or limit_up_data.get("industry")
            full_report = report_data.get("full_report")
            reason_detail = report_data.get("reason_detail")
            main_event = report_data.get("main_event")
            analysis_source = report_data.get("analysis_source", "minio-stockinfo")

            if existing:
                existing.stock_name = stock_name
                existing.main_event = main_event or existing.main_event
                existing.event_impact = reason_detail or existing.event_impact
                existing.industry = industry
                existing.strength_rating = strength_rating
                existing.is_dragon = bool(limit_up_data.get("is_dragon_head"))
                existing.dragon_type = "空间龙" if limit_up_data.get("dragon_rank") == 1 else existing.dragon_type
                existing.full_report = full_report
                existing.analysis_source = analysis_source
                existing.updated_at = datetime.now()
                session.flush()
                return existing.to_dict()

            analysis = LimitUpAnalysis(
                limit_up_id=limit_up_data["id"],
                stock_code=limit_up_data["stock_code"],
                stock_name=stock_name,
                analysis_date=analysis_date,
                main_event=main_event,
                event_impact=reason_detail,
                industry=industry,
                strength_rating=strength_rating,
                is_dragon=bool(limit_up_data.get("is_dragon_head")),
                dragon_type="空间龙" if limit_up_data.get("dragon_rank") == 1 else None,
                full_report=full_report,
                analysis_source=analysis_source,
            )
            session.add(analysis)
            session.flush()
            return analysis.to_dict()

    @classmethod
    def analyze_stock(cls, stock_code: str, analysis_date: date, force: bool = False) -> Dict[str, Any]:
        stock_code_candidates = cls._stock_code_candidates(stock_code)

        with session_scope() as session:
            existing = session.execute(
                select(LimitUpAnalysis).where(
                    and_(
                        LimitUpAnalysis.stock_code.in_(stock_code_candidates),
                        LimitUpAnalysis.analysis_date == analysis_date,
                    )
                )
            ).scalars().first()

            if existing and not force:
                return {
                    "status": "exists",
                    "message": "该股票已有分析记录",
                    "data": existing.to_dict(),
                }

        with session_scope() as session:
            limit_up = session.execute(
                select(LimitUpStock).where(
                    and_(
                        LimitUpStock.stock_code.in_(stock_code_candidates),
                        LimitUpStock.limit_up_date == analysis_date,
                    )
                )
            ).scalars().first()

            if not limit_up:
                return {
                    "status": "error",
                    "message": f"未找到 {stock_code} 在 {analysis_date} 的涨停记录",
                }

            limit_up_data = cls._limit_up_snapshot(limit_up)
            stock_name = limit_up_data["stock_name"]

        external_report = cls._load_external_report(stock_code, stock_name, analysis_date)
        if not external_report:
            return {
                "status": "error",
                "message": "当前股票在该日期下暂无可导入的 MinIO 分析报告",
            }

        imported = cls._import_external_report(limit_up_data, analysis_date, external_report)
        if not imported:
            return {
                "status": "error",
                "message": "导入 MinIO 分析报告失败",
            }

        return {
            "status": "success",
            "message": "已导入 MinIO 分析报告",
            "data": imported,
        }

    @classmethod
    def get_analysis(cls, stock_code: str, analysis_date: date) -> Optional[Dict[str, Any]]:
        stock_code_candidates = cls._stock_code_candidates(stock_code)
        with session_scope() as session:
            analysis = session.execute(
                select(LimitUpAnalysis).where(
                    and_(
                        LimitUpAnalysis.stock_code.in_(stock_code_candidates),
                        LimitUpAnalysis.analysis_date == analysis_date,
                    )
                )
            ).scalars().first()
            if analysis:
                return analysis.to_dict()

        with session_scope() as session:
            limit_up = session.execute(
                select(LimitUpStock).where(
                    and_(
                        LimitUpStock.stock_code.in_(stock_code_candidates),
                        LimitUpStock.limit_up_date == analysis_date,
                    )
                )
            ).scalars().first()
            limit_up_data = cls._limit_up_snapshot(limit_up) if limit_up else None

        if not limit_up_data:
            return None

        external_report = cls._load_external_report(stock_code, limit_up_data["stock_name"], analysis_date)
        if not external_report:
            return None

        return cls._import_external_report(limit_up_data, analysis_date, external_report)

    @classmethod
    def get_analysis_by_id(cls, analysis_id: int) -> Optional[Dict[str, Any]]:
        with session_scope() as session:
            analysis = session.get(LimitUpAnalysis, analysis_id)
            return analysis.to_dict() if analysis else None
