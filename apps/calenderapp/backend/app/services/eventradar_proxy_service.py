"""HTTP proxy to the *eventradar* service (forward-looking / expected events).

Mirrors the shape of :mod:`stockkb_proxy_service` so the calenderapp backend
talks to eventradar through one well-known boundary instead of importing
``akshare`` or any data-source SDK directly.

Lifecycle note — eventradar is still being built. ``EVENTRADAR_API_BASE_URL``
is empty by default; in that mode every method short-circuits to a
``not_configured`` placeholder payload (HTTP 200) so the frontend can render
its mock view without needing the upstream up. Once eventradar is running,
set the env var and these methods start hitting the real service. The
placeholder responses intentionally use the same key names that the real
service is planned to return — frontend code written against the placeholder
will keep working when the upstream goes live.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.settings import EVENTRADAR_API_BASE_URL, EVENTRADAR_API_TIMEOUT


class EventradarProxyError(RuntimeError):
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


# Static placeholder payloads returned while eventradar is not yet configured.
# Kept in module scope so tests can import them and assert the contract.
NOT_CONFIGURED_STATUS: Dict[str, Any] = {
    "status": "not_configured",
    "upstream": "eventradar",
    "base_url": "",
    "message": (
        "eventradar 服务尚未配置（EVENTRADAR_API_BASE_URL 未设置），"
        "当前返回占位数据。"
    ),
}


class EventradarProxyService:
    """Thin HTTP proxy + placeholder-mode for the eventradar service."""

    # ---------- public API ----------

    @classmethod
    def is_configured(cls) -> bool:
        return bool(EVENTRADAR_API_BASE_URL)

    @classmethod
    def health(cls) -> Dict[str, Any]:
        if not cls.is_configured():
            return dict(NOT_CONFIGURED_STATUS)
        payload = cls._request_json("GET", "/health")
        return {
            "status": payload.get("status", "unknown"),
            "upstream": "eventradar",
            "base_url": EVENTRADAR_API_BASE_URL,
        }

    @classmethod
    def list_announcements(
        cls,
        *,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "expected_at",
        sort_order: str = "asc",
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """List forward-looking events.

        Filter shape (all optional):
            date_from / date_to: YYYY-MM-DD bounds for ``expected_at``
            scope:               "industry" | "leader" | "stock" | "macro" | ""
            event_type:          "earnings" | "ipo_unlock" | "macro" | ...
            keyword:             free-text search across title / industries
            stock_code, industry: exact filters
        """
        if not cls.is_configured():
            return cls._placeholder_list(page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order)

        payload = cls._request_json(
            "POST",
            "/events/expected",
            {
                "page": page,
                "page_size": page_size,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "filters": filters or {},
            },
        )
        items = [cls._normalize_announcement(item) for item in (payload.get("items") or [])]
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
    def get_announcement_detail(cls, event_id: str) -> Dict[str, Any]:
        event_id = (event_id or "").strip()
        if not event_id:
            raise ValueError("event_id 不能为空")
        if not cls.is_configured():
            return {"found": False, "event_id": event_id, "placeholder": True}
        payload = cls._request_json("GET", f"/events/expected/{event_id}")
        event = payload.get("event")
        if not payload.get("found", False) or not isinstance(event, dict):
            return {"found": False, "event_id": event_id}
        return {
            "found": True,
            "event_id": event_id,
            "event": cls._normalize_announcement(event),
        }

    @classmethod
    def get_filter_meta(cls) -> Dict[str, Any]:
        """Distinct values powering the filter dropdowns on the announcements page."""
        if not cls.is_configured():
            return {
                "industries": [],
                "themes": [],
                "event_types": [],
                "scopes": [],
                "date_min": "",
                "date_max": "",
                "placeholder": True,
            }
        payload = cls._request_json("GET", "/events/expected/filters/meta")
        return {
            "industries": [str(item) for item in (payload.get("industries") or []) if str(item).strip()],
            "themes": [str(item) for item in (payload.get("themes") or []) if str(item).strip()],
            "event_types": [str(item) for item in (payload.get("event_types") or []) if str(item).strip()],
            "scopes": [str(item) for item in (payload.get("scopes") or []) if str(item).strip()],
            "date_min": str(payload.get("date_min") or ""),
            "date_max": str(payload.get("date_max") or ""),
        }

    # ---------- internals ----------

    @staticmethod
    def _placeholder_list(*, page: int, page_size: int, sort_by: str, sort_order: str) -> Dict[str, Any]:
        """Empty paginated payload. Frontend treats this identically to a real
        upstream response that happens to have zero rows.
        """
        return {
            "items": [],
            "count": 0,
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "has_more": False,
            "placeholder": True,
            "upstream_status": "not_configured",
        }

    @classmethod
    def _normalize_announcement(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce upstream fields into stable shapes the frontend can rely on.

        Field naming is deliberately aligned with stockkb's market_event
        contract so the same UI components can render both — ``event_name``,
        ``event_type``, ``event_scope``, ``affected_industries``,
        ``affected_themes``, ``affected_stocks``, etc. The eventradar-specific
        ones (``expected_at``, ``time_certainty``, ``importance``, ``source``)
        are added on top.
        """
        normalized = dict(item)
        normalized["event_id"] = str(normalized.get("event_id") or "")
        normalized["event_name"] = str(normalized.get("event_name") or "")
        normalized["event_type"] = str(normalized.get("event_type") or "")
        normalized["event_scope"] = str(normalized.get("event_scope") or "")
        normalized["scope_reason"] = str(normalized.get("scope_reason") or "")
        normalized["event_content"] = str(normalized.get("event_content") or "")
        normalized["expected_at"] = str(normalized.get("expected_at") or "")
        normalized["expected_at_end"] = str(normalized.get("expected_at_end") or "")
        normalized["time_certainty"] = str(normalized.get("time_certainty") or "")
        normalized["source"] = str(normalized.get("source") or "")
        normalized["source_url"] = str(normalized.get("source_url") or "")
        normalized["importance"] = int(normalized.get("importance") or 0)
        normalized["affected_industries"] = cls._parse_string_list(normalized.get("affected_industries"))
        normalized["affected_themes"] = cls._parse_string_list(normalized.get("affected_themes"))
        normalized["affected_stocks"] = cls._parse_affected_stocks(normalized.get("affected_stocks"))
        normalized["leaders"] = cls._parse_affected_stocks(normalized.get("leaders"))
        return normalized

    @staticmethod
    def _parse_string_list(value: Any) -> List[str]:
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

    @staticmethod
    def _parse_affected_stocks(value: Any) -> List[Dict[str, str]]:
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

        items: List[Dict[str, str]] = []
        seen: set[str] = set()
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            stock_code = str(raw.get("stock_code") or "").strip()
            stock_name = str(raw.get("stock_name") or "").strip()
            dedupe_key = stock_code or stock_name
            if not dedupe_key or dedupe_key in seen:
                continue
            items.append({"stock_code": stock_code, "stock_name": stock_name})
            seen.add(dedupe_key)
        return items

    @classmethod
    def _request_json(cls, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{EVENTRADAR_API_BASE_URL}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, data=data, headers=headers, method=method.upper())

        try:
            with urlopen(request, timeout=EVENTRADAR_API_TIMEOUT) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            message = cls._extract_upstream_message(body) or f"eventradar 上游请求失败（HTTP {exc.code}）"
            raise EventradarProxyError(message, http_status=502, upstream_status=exc.code) from exc
        except (URLError, TimeoutError) as exc:
            raise EventradarProxyError("eventradar 服务不可用", http_status=502) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EventradarProxyError("eventradar 返回格式无效", http_status=502) from exc

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
