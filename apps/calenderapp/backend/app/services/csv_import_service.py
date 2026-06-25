from __future__ import annotations

import base64
import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select

from app.db import session_scope
from app.models.stock import Stock


def _decode_utf8_csv(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except Exception:
        raise ValueError("CSV 文件必须为 UTF-8 编码")


def _norm(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _parse_date_ymd(s: str) -> date:
    v = _norm(s)
    if not v:
        raise ValueError("event_date 不能为空")
    try:
        d = datetime.strptime(v, "%Y-%m-%d").date()
    except Exception:
        raise ValueError("event_date 必须为 YYYY-MM-DD")
    return d


def _parse_int_range(s: Any, *, field: str, default: int, minimum: int, maximum: int) -> int:
    v = _norm(s)
    if not v:
        return default
    try:
        n = int(v)
    except Exception:
        raise ValueError(f"{field} 必须为整数")
    if n < minimum or n > maximum:
        raise ValueError(f"{field} 必须在 {minimum}~{maximum} 之间")
    return n


def _parse_stock_list(s: Any) -> List[str]:
    v = _norm(s)
    if not v:
        return []
    parts = []
    for seg in v.replace(";", ",").replace("|", ",").split(","):
        t = seg.strip()
        if t:
            parts.append(t)
    return parts


def _validate_headers(headers: Iterable[str], required: Iterable[str]) -> Tuple[bool, List[str]]:
    hs = [h.strip() for h in headers if h is not None]
    missing = [k for k in required if k not in hs]
    return (len(missing) == 0), missing


def _error_csv_base64(headers: List[str], rows: List[Dict[str, Any]]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    raw = out.getvalue().encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


@dataclass
class ImportResult:
    total: int
    created: int
    updated: int
    failed: int
    warnings: int
    error_csv_filename: Optional[str]
    error_csv_base64: Optional[str]
    error_rows: List[Dict[str, Any]]
    warning_rows: List[Dict[str, Any]]

    def to_dict(self):
        return {
            "total": self.total,
            "created": self.created,
            "updated": self.updated,
            "failed": self.failed,
            "warnings": self.warnings,
            "error_csv_filename": self.error_csv_filename,
            "error_csv_base64": self.error_csv_base64,
            "error_rows": self.error_rows[:200],
            "warning_rows": self.warning_rows[:200],
        }


class CsvImportService:
    STOCK_TEMPLATE_HEADERS = ["code", "name", "exchange"]

    @staticmethod
    def stocks_template_csv() -> str:
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(CsvImportService.STOCK_TEMPLATE_HEADERS)
        writer.writerow(["600519", "贵州茅台", "SH"])
        return out.getvalue()

    @staticmethod
    def import_stocks_csv(data: bytes, *, filename: str = "stocks.csv") -> ImportResult:
        text = _decode_utf8_csv(data)
        reader = csv.DictReader(io.StringIO(text))
        ok, missing = _validate_headers(reader.fieldnames or [], ["code", "name"])
        if not ok:
            raise ValueError(f"CSV 表头缺失字段: {', '.join(missing)}")

        created = 0
        updated = 0
        errors = []
        total = 0

        with session_scope() as session:
            for idx, row in enumerate(reader, start=2):
                total += 1
                try:
                    code = _norm(row.get("code"))
                    name = _norm(row.get("name"))
                    exchange = _norm(row.get("exchange")) or None
                    if not code or not name:
                        raise ValueError("code 和 name 不能为空")
                    if len(code) > 32:
                        raise ValueError("code 过长")
                    if len(name) > 128:
                        raise ValueError("name 过长")
                    if exchange and len(exchange) > 16:
                        raise ValueError("exchange 过长")

                    existing = session.execute(select(Stock).where(Stock.code == code)).scalars().first()
                    if existing:
                        existing.name = name
                        existing.exchange = exchange
                        updated += 1
                    else:
                        session.add(Stock(code=code, name=name, exchange=exchange))
                        created += 1
                except Exception as e:
                    errors.append({"row": idx, "error": str(e), **{k: (row.get(k) or "") for k in (reader.fieldnames or [])}})

        error_csv_base64 = None
        error_csv_filename = None
        if errors:
            headers = ["row", "error"] + (reader.fieldnames or [])
            error_csv_base64 = _error_csv_base64(headers, errors)
            error_csv_filename = f"import_errors_{filename}"

        return ImportResult(
            total=total,
            created=created,
            updated=updated,
            failed=len(errors),
            warnings=0,
            error_csv_filename=error_csv_filename,
            error_csv_base64=error_csv_base64,
            error_rows=errors,
            warning_rows=[],
        )
