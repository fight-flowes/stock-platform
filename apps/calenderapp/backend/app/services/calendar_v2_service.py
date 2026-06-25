from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import duckdb

from app.settings import CALENDAR_V2_DUCKDB_PATH, STOCKKB_DUCKDB_PATH


class CalendarV2ServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedDateRange:
    start_date: Optional[str]
    end_date: Optional[str]
    precision: str

    @property
    def resolved(self) -> bool:
        return bool(self.start_date)


def _parse_json_array(text: Any) -> List[Any]:
    if not text:
        return []
    if isinstance(text, list):
        return text
    try:
        value = json.loads(text)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _format_ts(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _derive_review_bucket(row: Dict[str, Any]) -> str:
    review_status = _normalize_text(row.get("review_status")).lower()
    event_truth = _normalize_text(row.get("event_truth")).lower()
    time_truth = _normalize_text(row.get("time_truth")).lower()
    content_truth = _normalize_text(row.get("content_truth")).lower()
    disposition = _normalize_text(row.get("disposition")).lower()

    if review_status != "completed":
        return "pending"
    if (
        event_truth == "true"
        and time_truth == "time_aligned"
        and content_truth in {"accurate", "mostly_accurate"}
        and disposition in {"adopt", "adopt_with_caution"}
    ):
        return "trusted"
    if disposition in {"adopt", "adopt_with_caution"}:
        return "caution"
    return "excluded"


def _resolve_event_date_range(event_time_text: str, active_dates: Iterable[str]) -> ResolvedDateRange:
    text = _normalize_text(event_time_text)
    if not text:
        sorted_dates = sorted(x for x in active_dates if _parse_iso_date(x))
        if sorted_dates:
            first = sorted_dates[0]
            last = sorted_dates[-1]
            precision = "timeline_exact" if first == last else "timeline_range"
            return ResolvedDateRange(first, last, precision)
        return ResolvedDateRange(None, None, "unresolved")

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return ResolvedDateRange(text, text, "exact")

    match = re.fullmatch(r"预期(\d{4}-\d{2}-\d{2})", text)
    if match:
        resolved = match.group(1)
        return ResolvedDateRange(resolved, resolved, "expected_exact")

    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})（[^）]+）", text)
    if match:
        resolved = match.group(1)
        return ResolvedDateRange(resolved, resolved, "annotated_exact")

    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})至(\d{4}-\d{2}-\d{2})", text)
    if match:
        return ResolvedDateRange(match.group(1), match.group(2), "range")

    match = re.fullmatch(r"(\d{4}-\d{2})-(\d{2})至(\d{2})日", text)
    if match:
        month_prefix = match.group(1)
        return ResolvedDateRange(
            f"{month_prefix}-{match.group(2)}",
            f"{month_prefix}-{match.group(3)}",
            "range",
        )

    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        resolved = match.group(1)
        return ResolvedDateRange(resolved, resolved, "approx")

    sorted_dates = sorted(x for x in active_dates if _parse_iso_date(x))
    if sorted_dates:
        first = sorted_dates[0]
        last = sorted_dates[-1]
        precision = "timeline_exact" if first == last else "timeline_range"
        return ResolvedDateRange(first, last, precision)

    return ResolvedDateRange(None, None, "unresolved")


class CalendarV2Service:
    @staticmethod
    def _ensure_local_store_dir() -> Path:
        CALENDAR_V2_DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return CALENDAR_V2_DUCKDB_PATH

    @staticmethod
    def _ensure_stockkb_duckdb() -> Path:
        if not STOCKKB_DUCKDB_PATH.exists():
            raise CalendarV2ServiceError(f"未找到 stockkb DuckDB 文件: {STOCKKB_DUCKDB_PATH}")
        return STOCKKB_DUCKDB_PATH

    @staticmethod
    def _connect_stockkb():
        db_path = CalendarV2Service._ensure_stockkb_duckdb()
        return duckdb.connect(str(db_path), read_only=True)

    @staticmethod
    def _connect_local_store():
        db_path = CalendarV2Service._ensure_local_store_dir()
        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calendar_event_override (
              event_key VARCHAR PRIMARY KEY,
              decision VARCHAR NOT NULL,
              calendar_date_start VARCHAR,
              calendar_date_end VARCHAR,
              note VARCHAR,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        return conn

    @staticmethod
    def _load_overrides() -> Dict[str, Dict[str, Any]]:
        with CalendarV2Service._connect_local_store() as conn:
            cursor = conn.execute(
                """
                SELECT
                  event_key,
                  decision,
                  calendar_date_start,
                  calendar_date_end,
                  note,
                  created_at,
                  updated_at
                FROM calendar_event_override
                """
            )
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return {
            _normalize_text(row.get("event_key")): {
                "event_key": _normalize_text(row.get("event_key")),
                "decision": _normalize_text(row.get("decision")),
                "calendar_date_start": _normalize_text(row.get("calendar_date_start")),
                "calendar_date_end": _normalize_text(row.get("calendar_date_end")),
                "note": _normalize_text(row.get("note")),
                "created_at": _format_ts(row.get("created_at")),
                "updated_at": _format_ts(row.get("updated_at")),
            }
            for row in rows
        }

    @staticmethod
    def _fetch_base_rows() -> List[Dict[str, Any]]:
        sql = """
        WITH favorite_market_events AS (
          SELECT DISTINCT member.event_key
          FROM kb_market_event_member AS member
          INNER JOIN kb_simple_event_favorite AS favorite
            ON favorite.event_id = member.event_id
        )
        SELECT
          event.event_key,
          event.event_name,
          event.event_time_text,
          event.event_content,
          event.event_type,
          event.event_scope,
          event.scope_reason,
          event.primary_industry,
          event.primary_theme,
          event.risk_summary,
          event.affected_stock_count,
          event.affected_stocks_preview_json,
          event.affected_stocks_json,
          event.affected_industries_json,
          event.affected_themes_json,
          event.timeline_json,
          event.first_seen_date,
          event.latest_active_date,
          event.active_dates_json,
          event.source_report_count,
          event.source_event_count,
          event.source_event_ids_json,
          event.is_cross_stock,
          event.is_active,
          event.created_at,
          event.updated_at,
          review.review_status,
          review.review_version,
          review.review_source,
          review.event_truth,
          review.time_truth,
          review.content_truth,
          review.disposition,
          review.confidence,
          review.headline,
          review.summary,
          review.error_message,
          review.requested_at,
          review.completed_at,
          review.updated_at AS review_updated_at
        FROM kb_market_event AS event
        INNER JOIN favorite_market_events AS favorite_event
          ON favorite_event.event_key = event.event_key
        LEFT JOIN kb_market_event_review AS review
          ON review.event_key = event.event_key
        ORDER BY review.completed_at DESC NULLS LAST,
                 review.updated_at DESC NULLS LAST,
                 event.created_at DESC NULLS LAST,
                 event.event_key DESC
        """
        with CalendarV2Service._connect_stockkb() as conn:
            cursor = conn.execute(sql)
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    @staticmethod
    def _materialize_event(row: Dict[str, Any]) -> Dict[str, Any]:
        active_dates = _parse_json_array(row.get("active_dates_json"))
        resolved = _resolve_event_date_range(row.get("event_time_text") or "", active_dates)
        review_bucket = _derive_review_bucket(row)
        calendar_ready = review_bucket == "trusted" and resolved.resolved

        affected_stocks_preview = _parse_json_array(row.get("affected_stocks_preview_json"))
        affected_stocks = _parse_json_array(row.get("affected_stocks_json"))
        affected_industries = _parse_json_array(row.get("affected_industries_json"))
        affected_themes = _parse_json_array(row.get("affected_themes_json"))
        timeline = _parse_json_array(row.get("timeline_json"))
        source_event_ids = _parse_json_array(row.get("source_event_ids_json"))

        return {
            "event_key": _normalize_text(row.get("event_key")),
            "event_name": _normalize_text(row.get("event_name")),
            "event_time_text": _normalize_text(row.get("event_time_text")),
            "event_content": _normalize_text(row.get("event_content")),
            "event_type": _normalize_text(row.get("event_type")) or "other",
            "event_scope": _normalize_text(row.get("event_scope")),
            "scope_reason": _normalize_text(row.get("scope_reason")),
            "primary_industry": _normalize_text(row.get("primary_industry")),
            "primary_theme": _normalize_text(row.get("primary_theme")),
            "risk_summary": _normalize_text(row.get("risk_summary")),
            "affected_stock_count": int(row.get("affected_stock_count") or 0),
            "affected_stocks_preview": affected_stocks_preview,
            "affected_stocks": affected_stocks,
            "affected_industries": affected_industries,
            "affected_themes": affected_themes,
            "timeline": timeline,
            "first_seen_date": _normalize_text(row.get("first_seen_date")),
            "latest_active_date": _normalize_text(row.get("latest_active_date")),
            "active_dates": active_dates,
            "source_report_count": int(row.get("source_report_count") or 0),
            "source_event_count": int(row.get("source_event_count") or 0),
            "source_event_ids": source_event_ids,
            "is_cross_stock": bool(row.get("is_cross_stock")),
            "is_active": bool(row.get("is_active")),
            "review_status": _normalize_text(row.get("review_status")) or "not_started",
            "review_version": _normalize_text(row.get("review_version")),
            "review_source": _normalize_text(row.get("review_source")),
            "event_truth": _normalize_text(row.get("event_truth")),
            "time_truth": _normalize_text(row.get("time_truth")),
            "content_truth": _normalize_text(row.get("content_truth")),
            "disposition": _normalize_text(row.get("disposition")),
            "confidence": float(row.get("confidence") or 0),
            "review_headline": _normalize_text(row.get("headline")),
            "review_summary": _normalize_text(row.get("summary")),
            "review_error_message": _normalize_text(row.get("error_message")),
            "requested_at": _format_ts(row.get("requested_at")),
            "completed_at": _format_ts(row.get("completed_at")),
            "review_updated_at": _format_ts(row.get("review_updated_at")),
            "created_at": _format_ts(row.get("created_at")),
            "updated_at": _format_ts(row.get("updated_at")),
            "review_bucket": review_bucket,
            "calendar_ready": calendar_ready,
            "calendar_date_start": resolved.start_date,
            "calendar_date_end": resolved.end_date,
            "date_precision": resolved.precision,
        }

    @staticmethod
    def _apply_override(item: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = dict(item)
        payload["override"] = override or None
        payload["override_decision"] = _normalize_text((override or {}).get("decision"))
        payload["override_note"] = _normalize_text((override or {}).get("note"))
        payload["override_updated_at"] = _normalize_text((override or {}).get("updated_at"))

        if not override:
            payload["calendar_source"] = "rule"
            return payload

        decision = _normalize_text(override.get("decision")).lower()
        override_start = _normalize_text(override.get("calendar_date_start")) or payload.get("calendar_date_start")
        override_end = _normalize_text(override.get("calendar_date_end")) or payload.get("calendar_date_end") or override_start

        if decision == "include":
            payload["calendar_ready"] = bool(override_start)
            payload["calendar_date_start"] = override_start
            payload["calendar_date_end"] = override_end
            payload["date_precision"] = "manual_override"
            payload["calendar_source"] = "manual_include"
            return payload

        if decision == "exclude":
            payload["calendar_ready"] = False
            payload["calendar_source"] = "manual_exclude"
            return payload

        payload["calendar_source"] = "rule"
        return payload

    @staticmethod
    def _matches_filters(
        item: Dict[str, Any],
        *,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: str,
        industry: str,
        event_type: str,
        status: str,
        override_mode: str,
    ) -> bool:
        if industry and industry not in {
            item.get("primary_industry", ""),
            *(item.get("affected_industries") or []),
        }:
            return False

        normalized_event_type = _normalize_text(event_type).lower()
        if normalized_event_type and normalized_event_type != "all":
            if _normalize_text(item.get("event_type")).lower() != normalized_event_type:
                return False

        normalized_status = _normalize_text(status).lower()
        if normalized_status and normalized_status != "all":
            if _normalize_text(item.get("review_bucket")).lower() != normalized_status:
                return False

        normalized_override_mode = _normalize_text(override_mode).lower()
        calendar_source = _normalize_text(item.get("calendar_source")).lower()
        override_decision = _normalize_text(item.get("override_decision")).lower()
        if normalized_override_mode and normalized_override_mode != "all":
            if normalized_override_mode == "manual":
                if not override_decision:
                    return False
            elif normalized_override_mode == "auto":
                if override_decision:
                    return False
            elif normalized_override_mode == "manual_include":
                if calendar_source != "manual_include":
                    return False
            elif normalized_override_mode == "manual_exclude":
                if calendar_source != "manual_exclude":
                    return False

        query = _normalize_text(keyword).lower()
        if query:
            haystacks = [
                item.get("event_name", ""),
                item.get("event_content", ""),
                item.get("primary_industry", ""),
                item.get("primary_theme", ""),
                item.get("review_summary", ""),
                item.get("risk_summary", ""),
            ]
            affected_stocks = item.get("affected_stocks") or []
            haystacks.extend(stock.get("stock_name", "") for stock in affected_stocks if isinstance(stock, dict))
            haystacks.extend(stock.get("stock_code", "") for stock in affected_stocks if isinstance(stock, dict))
            if query not in " ".join(str(x or "").lower() for x in haystacks):
                return False

        start = _parse_iso_date(start_date)
        end = _parse_iso_date(end_date)
        event_start = _parse_iso_date(item.get("calendar_date_start"))
        event_end = _parse_iso_date(item.get("calendar_date_end")) or event_start

        if start or end:
            if not event_start:
                return True
            if start and event_end and event_end < start:
                return False
            if end and event_start > end:
                return False

        return True

    @staticmethod
    def _load_events() -> List[Dict[str, Any]]:
        overrides = CalendarV2Service._load_overrides()
        items = []
        for row in CalendarV2Service._fetch_base_rows():
            item = CalendarV2Service._materialize_event(row)
            item = CalendarV2Service._apply_override(item, overrides.get(item["event_key"]))
            items.append(item)
        return items

    @staticmethod
    def get_filter_meta() -> Dict[str, Any]:
        items = CalendarV2Service._load_events()
        industries = sorted({x for item in items for x in ([item.get("primary_industry")] + (item.get("affected_industries") or [])) if x})
        event_types = sorted({_normalize_text(item.get("event_type")) for item in items if item.get("event_type")})
        ready_dates = [item.get("calendar_date_start") for item in items if item.get("calendar_date_start")]
        return {
            "industries": industries,
            "event_types": event_types,
            "date_min": min(ready_dates) if ready_dates else "",
            "date_max": max(ready_dates) if ready_dates else "",
        }

    @staticmethod
    def list_events(
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        keyword: str = "",
        industry: str = "",
        event_type: str = "all",
        status: str = "all",
        override_mode: str = "all",
    ) -> Dict[str, Any]:
        all_items = CalendarV2Service._load_events()
        visible_items = [
            item
            for item in all_items
            if CalendarV2Service._matches_filters(
                item,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
                industry=industry,
                event_type=event_type,
                status=status,
                override_mode=override_mode,
            )
        ]

        stats = {
            "favorite_total": len(all_items),
            "visible_total": len(visible_items),
            "calendar_ready_total": sum(1 for item in all_items if item.get("calendar_ready")),
            "trusted_total": sum(1 for item in all_items if item.get("review_bucket") == "trusted"),
            "pending_total": sum(1 for item in all_items if item.get("review_bucket") == "pending"),
            "caution_total": sum(1 for item in all_items if item.get("review_bucket") == "caution"),
            "excluded_total": sum(1 for item in all_items if item.get("review_bucket") == "excluded"),
            "unresolved_time_total": sum(1 for item in all_items if not item.get("calendar_date_start")),
            "manual_include_total": sum(1 for item in all_items if item.get("calendar_source") == "manual_include"),
            "manual_exclude_total": sum(1 for item in all_items if item.get("calendar_source") == "manual_exclude"),
        }

        visible_items.sort(
            key=lambda item: (
                0 if item.get("calendar_ready") else 1,
                item.get("calendar_date_start") or "9999-12-31",
                item.get("event_name") or "",
            )
        )

        return {"items": visible_items, "stats": stats}

    @staticmethod
    def list_upcoming(*, days: int = 14, limit: int = 20) -> Dict[str, Any]:
        today = date.today()
        end = today + timedelta(days=max(1, days))
        data = CalendarV2Service.list_events(
            start_date=today.isoformat(),
            end_date=end.isoformat(),
            status="trusted",
        )
        items = [item for item in data["items"] if item.get("calendar_ready")]
        items.sort(key=lambda item: (item.get("calendar_date_start") or "", item.get("event_name") or ""))
        return {"items": items[: max(1, limit)], "days": days}

    @staticmethod
    def get_event_detail(event_key: str) -> Dict[str, Any]:
        normalized_key = _normalize_text(event_key)
        if not normalized_key:
            raise ValueError("event_key 不能为空")

        items = CalendarV2Service._load_events()
        target = next((item for item in items if item.get("event_key") == normalized_key), None)
        if not target:
            return {"found": False, "event_key": normalized_key}

        detail_sql = """
        SELECT
          member.event_id,
          member.report_id,
          member.is_primary,
          simple_event.event_name AS source_event_name,
          simple_event.event_time_text AS source_event_time_text,
          simple_event.event_content AS source_event_content,
          simple_event.source_name AS source_name,
          simple_event.source_url AS source_url,
          simple_event.evidence_text AS evidence_text,
          report.report_title,
          report.stock_code,
          report.stock_name,
          report.report_date,
          report.source_path,
          report.risk_summary AS report_risk_summary,
          report.core_logic AS report_core_logic
        FROM kb_market_event_member AS member
        LEFT JOIN kb_simple_event AS simple_event
          ON simple_event.event_id = member.event_id
        LEFT JOIN kb_simple_report AS report
          ON report.report_id = COALESCE(member.report_id, simple_event.report_id)
        WHERE member.event_key = ?
        ORDER BY member.is_primary DESC, report.report_date DESC, member.event_id ASC
        """
        with CalendarV2Service._connect_stockkb() as conn:
            cursor = conn.execute(detail_sql, [normalized_key])
            columns = [item[0] for item in cursor.description]
            detail_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        source_reports = []
        seen_reports = set()
        source_events = []
        for row in detail_rows:
            report_id = _normalize_text(row.get("report_id"))
            if report_id and report_id not in seen_reports:
                seen_reports.add(report_id)
                source_reports.append(
                    {
                        "report_id": report_id,
                        "report_title": _normalize_text(row.get("report_title")),
                        "stock_code": _normalize_text(row.get("stock_code")),
                        "stock_name": _normalize_text(row.get("stock_name")),
                        "report_date": _normalize_text(row.get("report_date")),
                        "source_name": _normalize_text(row.get("source_name")),
                        "source_path": _normalize_text(row.get("source_path")),
                        "source_url": _normalize_text(row.get("source_url")),
                        "risk_summary": _normalize_text(row.get("report_risk_summary")),
                        "core_logic": _normalize_text(row.get("report_core_logic")),
                    }
                )

            source_events.append(
                {
                    "event_id": _normalize_text(row.get("event_id")),
                    "event_name": _normalize_text(row.get("source_event_name")),
                    "event_time_text": _normalize_text(row.get("source_event_time_text")),
                    "event_content": _normalize_text(row.get("source_event_content")),
                    "source_name": _normalize_text(row.get("source_name")),
                    "source_url": _normalize_text(row.get("source_url")),
                    "evidence_text": _normalize_text(row.get("evidence_text")),
                    "is_primary": bool(row.get("is_primary")),
                }
            )

        payload = dict(target)
        payload["found"] = True
        payload["source_reports"] = source_reports
        payload["source_events"] = source_events
        return payload

    @staticmethod
    def set_override(
        event_key: str,
        *,
        decision: str,
        calendar_date_start: str = "",
        calendar_date_end: str = "",
        note: str = "",
    ) -> Dict[str, Any]:
        normalized_key = _normalize_text(event_key)
        normalized_decision = _normalize_text(decision).lower()
        if not normalized_key:
            raise ValueError("event_key 不能为空")
        if normalized_decision not in {"include", "exclude", "clear"}:
            raise ValueError("decision 必须为 include / exclude / clear")

        target = CalendarV2Service.get_event_detail(normalized_key)
        if not target.get("found"):
            raise ValueError(f"事件不存在: {normalized_key}")

        start_date = _normalize_text(calendar_date_start)
        end_date = _normalize_text(calendar_date_end)
        if start_date and not _parse_iso_date(start_date):
            raise ValueError("calendar_date_start 格式必须为 YYYY-MM-DD")
        if end_date and not _parse_iso_date(end_date):
            raise ValueError("calendar_date_end 格式必须为 YYYY-MM-DD")
        if start_date and end_date and end_date < start_date:
            raise ValueError("calendar_date_end 不能早于 calendar_date_start")

        if normalized_decision == "include":
            if not start_date:
                start_date = target.get("calendar_date_start") or ""
            if not end_date:
                end_date = target.get("calendar_date_end") or start_date
            if not start_date:
                raise ValueError("手动纳入日历时必须提供明确日期")

        with CalendarV2Service._connect_local_store() as conn:
            if normalized_decision == "clear":
                conn.execute("DELETE FROM calendar_event_override WHERE event_key = ?", [normalized_key])
            else:
                existing_row = conn.execute(
                    "SELECT created_at FROM calendar_event_override WHERE event_key = ?",
                    [normalized_key],
                ).fetchone()
                created_at = existing_row[0] if existing_row else datetime.utcnow()
                updated_at = datetime.utcnow()
                conn.execute("DELETE FROM calendar_event_override WHERE event_key = ?", [normalized_key])
                conn.execute(
                    """
                    INSERT INTO calendar_event_override (
                      event_key,
                      decision,
                      calendar_date_start,
                      calendar_date_end,
                      note,
                      created_at,
                      updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        normalized_key,
                        normalized_decision,
                        start_date or None,
                        end_date or None,
                        _normalize_text(note) or None,
                        created_at,
                        updated_at,
                    ],
                )

        return CalendarV2Service.get_event_detail(normalized_key)

    @staticmethod
    def health() -> Dict[str, Any]:
        db_path = CalendarV2Service._ensure_stockkb_duckdb()
        items = CalendarV2Service._load_events()
        overrides = CalendarV2Service._load_overrides()
        return {
            "status": "ok",
            "stockkb_duckdb_path": str(db_path),
            "calendar_v2_duckdb_path": str(CalendarV2Service._ensure_local_store_dir()),
            "favorite_event_count": len(items),
            "reviewed_event_count": sum(1 for item in items if item.get("review_bucket") != "pending"),
            "pending_review_count": sum(1 for item in items if item.get("review_bucket") == "pending"),
            "calendar_ready_count": sum(1 for item in items if item.get("calendar_ready")),
            "override_count": len(overrides),
        }
