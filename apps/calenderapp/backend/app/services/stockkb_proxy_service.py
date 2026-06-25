from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.settings import STOCKKB_API_BASE_URL, STOCKKB_API_TIMEOUT


class StockkbProxyError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int = 502,
        upstream_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.upstream_status = upstream_status


class StockkbProxyService:
    @classmethod
    def health(cls) -> Dict[str, Any]:
        payload = cls._request_json("GET", "/health")
        return {
            "status": payload.get("status", "unknown"),
            "upstream": "stockkb",
            "base_url": STOCKKB_API_BASE_URL,
        }

    @classmethod
    def get_report_summary(cls, stock_code: str, report_date: str) -> Dict[str, Any]:
        raw_stock_code = (stock_code or "").strip()
        report_date = (report_date or "").strip()
        if not raw_stock_code:
            raise ValueError("stock_code 不能为空")
        if not report_date:
            raise ValueError("report_date 不能为空")

        reports: list[dict[str, Any]] = []
        resolved_stock_code = raw_stock_code
        for candidate in cls._stock_code_candidates(raw_stock_code):
            payload = cls._request_json(
                "POST",
                "/kb/simple/reports",
                {
                    "page": 1,
                    "page_size": 5,
                    "sort_by": "report_date",
                    "sort_order": "desc",
                    "filters": {
                        "stock_code": candidate,
                        "report_date": report_date,
                    },
                },
            )
            reports = payload.get("reports") or []
            if reports:
                resolved_stock_code = candidate
                break

        if not reports:
            return {
                "report_exists": False,
                "report_id": None,
                "report_title": None,
                "core_logic": "",
                "stock_code": raw_stock_code,
                "stock_name": None,
                "report_date": report_date,
                "event_count": 0,
                "risk_summary": "",
            }

        report = reports[0]
        return {
            "report_exists": True,
            "report_id": report.get("report_id") or "",
            "report_title": report.get("report_title") or "",
            "core_logic": str(report.get("core_logic") or ""),
            "stock_code": report.get("stock_code") or resolved_stock_code,
            "stock_name": report.get("stock_name") or "",
            "report_date": str(report.get("report_date") or report_date),
            "event_count": int(report.get("event_count") or 0),
            "risk_summary": str(report.get("risk_summary") or ""),
        }

    @classmethod
    def list_events(
        cls,
        *,
        stock_code: str,
        report_date: str,
        page: int = 1,
        page_size: int = 20,
        event_scope: str = "default",
    ) -> Dict[str, Any]:
        del event_scope
        raw_stock_code = (stock_code or "").strip()
        report_date = (report_date or "").strip()
        if not raw_stock_code:
            raise ValueError("stock_code 不能为空")
        if not report_date:
            raise ValueError("report_date 不能为空")

        payload: Dict[str, Any] = {}
        events: list[dict[str, Any]] = []
        resolved_stock_code = raw_stock_code
        for candidate in cls._stock_code_candidates(raw_stock_code):
            payload = cls._request_json(
                "POST",
                "/kb/simple/events",
                {
                    "page": page,
                    "page_size": page_size,
                    "sort_by": "event_time_normalized",
                    "sort_order": "desc",
                    "filters": {
                        "stock_code": candidate,
                        "report_date": report_date,
                    },
                },
            )
            events = payload.get("events") or []
            if events or int(payload.get("total_count", 0) or 0) > 0:
                resolved_stock_code = candidate
                break

        items = [cls._normalize_simple_event(item) for item in events]
        return {
            "stock_code": resolved_stock_code,
            "report_date": report_date,
            "count": int(payload.get("count", len(items)) or 0),
            "total_count": int(payload.get("total_count", len(items)) or 0),
            "page": int(payload.get("page", page) or page),
            "page_size": int(payload.get("page_size", page_size) or page_size),
            "sort_by": str(payload.get("sort_by", "event_time_normalized") or "event_time_normalized"),
            "sort_order": str(payload.get("sort_order", "desc") or "desc"),
            "has_more": bool(payload.get("has_more", False)),
            "items": items,
        }

    @classmethod
    def list_all_events(
        cls,
        *,
        stock_code: str,
        report_date: str,
        page_size: int = 200,
        event_scope: str = "default",
    ) -> Dict[str, Any]:
        page_size = max(1, min(int(page_size), 200))
        page = 1
        aggregated_items: list[dict[str, Any]] = []
        resolved_stock_code = (stock_code or "").strip()
        while True:
            payload = cls.list_events(
                stock_code=resolved_stock_code or stock_code,
                report_date=report_date,
                page=page,
                page_size=page_size,
                event_scope=event_scope,
            )
            if page == 1:
                resolved_stock_code = str(payload.get("stock_code") or resolved_stock_code or stock_code)
            page_items = payload.get("items") or []
            aggregated_items.extend(page_items)
            if not payload.get("has_more") or not page_items:
                return {
                    "stock_code": resolved_stock_code,
                    "report_date": report_date,
                    "count": len(aggregated_items),
                    "total_count": int(payload.get("total_count", len(aggregated_items)) or len(aggregated_items)),
                    "page": 1,
                    "page_size": page_size,
                    "sort_by": str(payload.get("sort_by", "event_time_normalized") or "event_time_normalized"),
                    "sort_order": str(payload.get("sort_order", "desc") or "desc"),
                    "has_more": False,
                    "items": aggregated_items,
                }
            page += 1

    @classmethod
    def get_event_detail(cls, event_id: str) -> Dict[str, Any]:
        event_id = (event_id or "").strip()
        if not event_id:
            raise ValueError("event_id 不能为空")
        payload = cls._request_json("GET", f"/kb/simple/events/{event_id}")
        event = payload.get("event")
        if not payload.get("found", False) or not isinstance(event, dict):
            return {"found": False, "event_id": event_id}
        normalized_event = cls._normalize_simple_event(event)
        return {
            "found": True,
            "event_id": event_id,
            "event": normalized_event,
        }

    @classmethod
    def favorite_event(cls, event_id: str) -> Dict[str, Any]:
        event_id = (event_id or "").strip()
        if not event_id:
            raise ValueError("event_id 不能为空")
        return cls._request_json("POST", f"/kb/simple/events/{event_id}/favorite")

    @classmethod
    def unfavorite_event(cls, event_id: str) -> Dict[str, Any]:
        event_id = (event_id or "").strip()
        if not event_id:
            raise ValueError("event_id 不能为空")
        return cls._request_json("DELETE", f"/kb/simple/events/{event_id}/favorite")

    @classmethod
    def unfavorite_market_event(cls, event_key: str) -> Dict[str, Any]:
        """Proxy DELETE /kb/simple/market-events/{key}/favorite.

        Bulk-unfavorites every simple event under the given market event.
        Used by the /events page's per-card "remove" button — one click in
        the UI fans out to clear all underlying simple-event favourites
        that caused the market event to surface.
        """
        event_key = (event_key or "").strip()
        if not event_key:
            raise ValueError("event_key 不能为空")
        return cls._request_json("DELETE", f"/kb/simple/market-events/{event_key}/favorite")

    @classmethod
    def list_market_events(
        cls,
        *,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "latest_active_date",
        sort_order: str = "desc",
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = cls._request_json(
            "POST",
            "/kb/simple/market-events",
            {
                "page": page,
                "page_size": page_size,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "filters": filters or {},
            },
        )
        items = [cls._normalize_market_event_list_item(item) for item in payload.get("items") or []]
        return {
            "items": items,
            "count": int(payload.get("count", len(items)) or 0),
            "total_count": int(payload.get("total_count", len(items)) or 0),
            "page": int(payload.get("page", page) or page),
            "page_size": int(payload.get("page_size", page_size) or page_size),
            "sort_by": str(payload.get("sort_by", sort_by) or sort_by),
            "sort_order": str(payload.get("sort_order", sort_order) or sort_order),
            "has_more": bool(payload.get("has_more", False)),
        }

    @classmethod
    def get_market_event_detail(cls, event_key: str) -> Dict[str, Any]:
        event_key = (event_key or "").strip()
        if not event_key:
            raise ValueError("event_key 不能为空")
        payload = cls._request_json("GET", f"/kb/simple/market-events/{event_key}")
        event = payload.get("event")
        if not payload.get("found", False) or not isinstance(event, dict):
            return {"found": False, "event_key": event_key}
        normalized_event = cls._normalize_market_event_detail(event)
        normalized_event["source_reports"] = cls._enrich_market_event_source_reports(
            normalized_event.get("source_reports"),
            normalized_event.get("source_event_ids"),
            normalized_event.get("event_name"),
        )
        return {
            "found": True,
            "event_key": event_key,
            "event": normalized_event,
        }

    @classmethod
    def get_market_event_timeline(cls, event_key: str) -> Dict[str, Any]:
        event_key = (event_key or "").strip()
        if not event_key:
            raise ValueError("event_key 不能为空")
        payload = cls._request_json("GET", f"/kb/simple/market-events/{event_key}/timeline")
        timeline = [cls._normalize_market_event_timeline_point(item) for item in payload.get("timeline") or []]
        return {
            "event_key": str(payload.get("event_key") or event_key),
            "timeline": timeline,
        }

    @classmethod
    def get_market_event_filter_meta(cls) -> Dict[str, Any]:
        payload = cls._request_json("GET", "/kb/simple/market-events/filters/meta")
        return {
            "industries": [str(item) for item in (payload.get("industries") or []) if str(item).strip()],
            "themes": [str(item) for item in (payload.get("themes") or []) if str(item).strip()],
            "date_min": str(payload.get("date_min") or ""),
            "date_max": str(payload.get("date_max") or ""),
        }

    @classmethod
    def get_market_event_review(cls, event_key: str) -> Dict[str, Any]:
        event_key = (event_key or "").strip()
        if not event_key:
            raise ValueError("event_key 不能为空")
        payload = cls._request_json("GET", f"/kb/simple/market-events/{event_key}/review")
        review = payload.get("review")
        normalized_review = cls._normalize_market_event_review(review) if isinstance(review, dict) else None
        return {
            "found": bool(payload.get("found", False) and normalized_review),
            "event_key": str(payload.get("event_key") or event_key),
            "review": normalized_review,
        }

    @classmethod
    def list_market_event_review_session_ids(cls) -> list[Dict[str, str]]:
        """Lightweight enumerate used by the GC sweep — returns one entry per
        review row that currently points at an upstream Vibe-Trading session.
        """
        payload = cls._request_json("GET", "/kb/simple/market-events/reviews/sessions")
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return []
        result: list[Dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            event_key = str(item.get("event_key") or "").strip()
            sid = str(item.get("vibe_session_id") or "").strip()
            if event_key and sid:
                result.append({"event_key": event_key, "vibe_session_id": sid})
        return result

    @classmethod
    def put_market_event_review(cls, event_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_key = (event_key or "").strip()
        if not event_key:
            raise ValueError("event_key 不能为空")
        upstream = cls._request_json("PUT", f"/kb/simple/market-events/{event_key}/review", payload)
        review = upstream.get("review")
        normalized_review = cls._normalize_market_event_review(review) if isinstance(review, dict) else None
        response: Dict[str, Any] = {
            "found": bool(upstream.get("found", False) and normalized_review),
            "event_key": str(upstream.get("event_key") or event_key),
            "review": normalized_review,
        }
        event = upstream.get("event")
        if isinstance(event, dict):
            response["event"] = cls._normalize_market_event_detail(event)
        return response

    @classmethod
    def run_market_event_review(cls, event_key: str) -> Dict[str, Any]:
        event_key = (event_key or "").strip()
        if not event_key:
            raise ValueError("event_key 不能为空")
        payload = cls._request_json("POST", f"/kb/simple/market-events/{event_key}/review/run")
        review = payload.get("review")
        event = payload.get("event")
        return {
            "found": bool(payload.get("found", False)),
            "event_key": str(payload.get("event_key") or event_key),
            "review": cls._normalize_market_event_review(review) if isinstance(review, dict) else None,
            "event": cls._normalize_market_event_detail(event) if isinstance(event, dict) else None,
        }

    @staticmethod
    def _stock_code_candidates(stock_code: str) -> list[str]:
        raw = (stock_code or "").strip().upper()
        if not raw:
            return []
        candidates: list[str] = []
        for item in (raw, raw.split(".", 1)[0]):
            value = item.strip()
            if value and value not in candidates:
                candidates.append(value)
        return candidates

    @classmethod
    def _normalize_simple_event(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(item)
        normalized["affected_stocks"] = cls._parse_affected_stocks(
            normalized.get("affected_stocks", normalized.get("affected_stock_codes_json"))
        )
        normalized["event_name"] = str(normalized.get("event_name") or "")
        normalized["event_time_text"] = str(normalized.get("event_time_text") or "")
        normalized["event_time_normalized"] = str(normalized.get("event_time_normalized") or "")
        normalized["event_content"] = str(normalized.get("event_content") or "")
        normalized["risk_summary"] = str(normalized.get("risk_summary") or "")
        normalized["report_title"] = str(normalized.get("report_title") or "")
        normalized["stock_code"] = str(normalized.get("stock_code") or "")
        normalized["stock_name"] = str(normalized.get("stock_name") or "")
        normalized["report_date"] = str(normalized.get("report_date") or "")
        normalized["source_path"] = str(normalized.get("source_path") or "")
        normalized["source_name"] = str(normalized.get("source_name") or "")
        normalized["source_url"] = str(normalized.get("source_url") or "")
        normalized["event_type"] = str(normalized.get("event_type") or "")
        normalized["event_scope"] = str(normalized.get("event_scope") or "")
        normalized["scope_reason"] = str(normalized.get("scope_reason") or "")
        normalized["affected_industries"] = cls._parse_string_list(normalized.get("affected_industries"))
        normalized["affected_themes"] = cls._parse_string_list(normalized.get("affected_themes"))
        normalized["is_favorite"] = bool(normalized.get("is_favorite", False))
        return normalized

    @classmethod
    def _normalize_market_event_list_item(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(item)
        normalized["event_key"] = str(normalized.get("event_key") or "")
        normalized["event_name"] = str(normalized.get("event_name") or "")
        normalized["event_time_text"] = str(normalized.get("event_time_text") or "")
        normalized["event_content"] = str(normalized.get("event_content") or "")
        normalized["event_type"] = str(normalized.get("event_type") or "")
        normalized["event_scope"] = str(normalized.get("event_scope") or "")
        normalized["scope_reason"] = str(normalized.get("scope_reason") or "")
        normalized["primary_industry"] = str(normalized.get("primary_industry") or "")
        normalized["primary_theme"] = str(normalized.get("primary_theme") or "")
        normalized["affected_industries"] = cls._parse_string_list(normalized.get("affected_industries"))
        normalized["affected_themes"] = cls._parse_string_list(normalized.get("affected_themes"))
        normalized["affected_stock_count"] = int(normalized.get("affected_stock_count") or 0)
        normalized["affected_stocks_preview"] = cls._parse_affected_stocks(normalized.get("affected_stocks_preview"))
        normalized["source_report_count"] = int(normalized.get("source_report_count") or 0)
        normalized["first_seen_date"] = str(normalized.get("first_seen_date") or "")
        normalized["latest_active_date"] = str(normalized.get("latest_active_date") or "")
        normalized["active_dates"] = cls._parse_string_list(normalized.get("active_dates"))
        normalized["is_cross_stock"] = bool(normalized.get("is_cross_stock", False))
        # is_active is DEPRECATED — see kb_market_event schema notes. Frozen at
        # False for new rows; pass through as-is for historical rows so the
        # contract stays stable while the activity concept is being redesigned.
        normalized["is_active"] = bool(normalized.get("is_active", False))
        normalized["is_favorite"] = bool(normalized.get("is_favorite", False))
        normalized["review_status"] = str(normalized.get("review_status") or "")
        normalized["event_truth"] = str(normalized.get("event_truth") or "")
        normalized["review_updated_at"] = str(normalized.get("review_updated_at") or "")
        return normalized

    @classmethod
    def _normalize_market_event_detail(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized = cls._normalize_market_event_list_item(item)
        normalized["risk_summary"] = str(item.get("risk_summary") or "")
        normalized["affected_stocks"] = cls._parse_affected_stocks(item.get("affected_stocks"))
        normalized["source_reports"] = cls._parse_market_event_source_reports(item.get("source_reports"))
        normalized["source_event_ids"] = cls._parse_string_list(item.get("source_event_ids"))
        return normalized

    @classmethod
    def _enrich_market_event_source_reports(
        cls,
        source_reports: Any,
        source_event_ids: Any,
        event_name: Any,
    ) -> list[dict[str, str]]:
        reports = cls._parse_market_event_source_reports(source_reports)
        event_ids = cls._parse_string_list(source_event_ids)
        target_event_name = str(event_name or "")
        if not reports or not event_ids:
            return cls._backfill_market_event_sources_from_report_context(reports, target_event_name)

        report_lookup: dict[str, dict[str, str]] = {
            str(report.get("report_id") or "").strip(): dict(report)
            for report in reports
            if str(report.get("report_id") or "").strip()
        }
        if not report_lookup:
            return reports

        for event_id in event_ids:
            try:
                payload = cls._request_json("GET", f"/kb/simple/events/{event_id}")
            except StockkbProxyError:
                continue
            event = payload.get("event")
            if not payload.get("found", False) or not isinstance(event, dict):
                continue
            normalized_event = cls._normalize_simple_event(event)
            report_id = str(normalized_event.get("report_id") or "").strip()
            if not report_id or report_id not in report_lookup:
                continue
            target = report_lookup[report_id]
            if not str(target.get("source_name") or "").strip():
                target["source_name"] = str(normalized_event.get("source_name") or "")
            if not str(target.get("source_url") or "").strip():
                target["source_url"] = str(normalized_event.get("source_url") or "")

        enriched = [report_lookup.get(str(report.get("report_id") or "").strip(), dict(report)) for report in reports]
        return cls._backfill_market_event_sources_from_report_context(enriched, target_event_name)

    @classmethod
    def _backfill_market_event_sources_from_report_context(
        cls,
        source_reports: list[dict[str, str]],
        event_name: str,
    ) -> list[dict[str, str]]:
        target_name = cls._normalize_event_name_key(event_name)
        if not source_reports or not target_name:
            return source_reports

        enriched_reports: list[dict[str, str]] = []
        event_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for report in source_reports:
            current = dict(report)
            has_source = bool(str(current.get("source_name") or "").strip() or str(current.get("source_url") or "").strip())
            if has_source:
                enriched_reports.append(current)
                continue

            stock_code = str(current.get("stock_code") or "").strip()
            report_date = str(current.get("report_date") or "").strip()
            if not stock_code or not report_date:
                enriched_reports.append(current)
                continue

            cache_key = (stock_code, report_date)
            if cache_key not in event_cache:
                event_cache[cache_key] = cls._load_simple_events_for_report(stock_code, report_date)

            matched_source = cls._match_event_source_from_simple_events(event_cache[cache_key], target_name)
            if matched_source:
                if not str(current.get("source_name") or "").strip():
                    current["source_name"] = str(matched_source.get("source_name") or "")
                if not str(current.get("source_url") or "").strip():
                    current["source_url"] = str(matched_source.get("source_url") or "")
            enriched_reports.append(current)
        return enriched_reports

    @classmethod
    def _load_simple_events_for_report(cls, stock_code: str, report_date: str) -> list[dict[str, Any]]:
        try:
            payload = cls._request_json(
                "POST",
                "/kb/simple/events",
                {
                    "page": 1,
                    "page_size": 100,
                    "sort_by": "event_time_normalized",
                    "sort_order": "desc",
                    "filters": {
                        "stock_code": stock_code,
                        "report_date": report_date,
                    },
                },
            )
        except StockkbProxyError:
            return []
        raw_items = payload.get("events") or payload.get("items") or []
        return [cls._normalize_simple_event(item) for item in raw_items if isinstance(item, dict)]

    @classmethod
    def _match_event_source_from_simple_events(
        cls,
        events: list[dict[str, Any]],
        target_name: str,
    ) -> dict[str, Any] | None:
        exact_match: dict[str, Any] | None = None
        fallback_match: dict[str, Any] | None = None
        for item in events:
            candidate_name = cls._normalize_event_name_key(item.get("event_name"))
            if not candidate_name:
                continue
            has_source = bool(str(item.get("source_name") or "").strip() or str(item.get("source_url") or "").strip())
            if candidate_name == target_name and has_source:
                return item
            if candidate_name == target_name:
                exact_match = exact_match or item
            if has_source and (candidate_name in target_name or target_name in candidate_name):
                fallback_match = fallback_match or item
        return exact_match or fallback_match

    @staticmethod
    def _normalize_event_name_key(value: Any) -> str:
        text = str(value or "").strip().lower()
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)

    @classmethod
    def _normalize_market_event_timeline_point(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(item)
        normalized["date"] = str(normalized.get("date") or "")
        normalized["affected_stock_count"] = int(normalized.get("affected_stock_count") or 0)
        normalized["stocks"] = cls._parse_affected_stocks(normalized.get("stocks"))
        normalized["source_report_count"] = int(normalized.get("source_report_count") or 0)
        return normalized

    @classmethod
    def _normalize_market_event_review(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(item)
        normalized["event_key"] = str(normalized.get("event_key") or "")
        normalized["review_status"] = str(normalized.get("review_status") or "")
        normalized["review_version"] = str(normalized.get("review_version") or "")
        normalized["review_source"] = str(normalized.get("review_source") or "")
        normalized["vibe_session_id"] = str(normalized.get("vibe_session_id") or "")
        normalized["event_truth"] = str(normalized.get("event_truth") or "")
        normalized["time_truth"] = str(normalized.get("time_truth") or "")
        normalized["content_truth"] = str(normalized.get("content_truth") or "")
        normalized["disposition"] = str(normalized.get("disposition") or "")
        normalized["confidence"] = float(normalized.get("confidence") or 0.0)
        normalized["headline"] = str(normalized.get("headline") or "")
        normalized["summary"] = str(normalized.get("summary") or "")
        normalized["review_payload"] = normalized.get("review_payload") if isinstance(normalized.get("review_payload"), dict) else {}
        normalized["source_snapshot"] = normalized.get("source_snapshot") if isinstance(normalized.get("source_snapshot"), dict) else {}
        normalized["error_message"] = str(normalized.get("error_message") or "")
        normalized["requested_at"] = str(normalized.get("requested_at") or "")
        normalized["completed_at"] = str(normalized.get("completed_at") or "")
        normalized["created_at"] = str(normalized.get("created_at") or "")
        normalized["updated_at"] = str(normalized.get("updated_at") or "")
        return normalized

    @staticmethod
    def _parse_affected_stocks(value: Any) -> list[dict[str, str]]:
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = []
            raw_items = parsed if isinstance(parsed, list) else []
        else:
            raw_items = []

        items: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            stock_code = str(raw.get("stock_code") or "").strip()
            stock_name = str(raw.get("stock_name") or "").strip()
            dedupe_key = stock_code or stock_name
            if not dedupe_key or dedupe_key in seen:
                continue
            items.append(
                {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                }
            )
            seen.add(dedupe_key)
        return items

    @staticmethod
    def _parse_market_event_source_reports(value: Any) -> list[dict[str, str]]:
        raw_items = value if isinstance(value, list) else []
        items: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            report_id = str(raw.get("report_id") or "").strip()
            if not report_id or report_id in seen:
                continue
            items.append(
                {
                    "report_id": report_id,
                    "report_title": str(raw.get("report_title") or ""),
                    "stock_code": str(raw.get("stock_code") or ""),
                    "stock_name": str(raw.get("stock_name") or ""),
                    "report_date": str(raw.get("report_date") or ""),
                    "source_name": str(raw.get("source_name") or ""),
                    "source_url": str(raw.get("source_url") or ""),
                    "source_path": str(raw.get("source_path") or ""),
                }
            )
            seen.add(report_id)
        return items

    @staticmethod
    def _parse_string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return [value]
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        return []

    @classmethod
    def _request_json(cls, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{STOCKKB_API_BASE_URL}{path}"
        data = None
        headers = {
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=data, headers=headers, method=method.upper())

        try:
            with urlopen(request, timeout=STOCKKB_API_TIMEOUT) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            message = cls._extract_upstream_message(body) or f"stockkb 上游请求失败（HTTP {exc.code}）"
            raise StockkbProxyError(message, http_status=502, upstream_status=exc.code) from exc
        except (URLError, TimeoutError) as exc:
            raise StockkbProxyError("stockkb 服务不可用", http_status=502) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StockkbProxyError("stockkb 返回格式无效", http_status=502) from exc

    @staticmethod
    def _extract_upstream_message(body: str) -> Optional[str]:
        if not body:
            return None
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body[:200]
        if isinstance(payload, dict):
            return payload.get("detail") or payload.get("message")
        return None
