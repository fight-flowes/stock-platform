"""REST endpoints for the announcements (forward-looking events) feature.

Mounted at ``/api/announcements``. Routes proxy through
:class:`EventradarProxyService`, which today returns placeholder payloads
because the eventradar service is still being built. The contract is stable:
once eventradar is configured (see ``EVENTRADAR_API_BASE_URL`` in
``app.settings``) these routes start returning real data with no frontend
change.
"""

from __future__ import annotations

from flask import request
from flask_restx import Namespace, Resource

from app.api.params import parse_date, parse_int
from app.services.eventradar_proxy_service import (
    EventradarProxyError,
    EventradarProxyService,
)
from config.api_config import APIConstants, APIResponse


announcements_ns = Namespace(
    "announcements",
    description="预期事件（公告 / 行业 / 龙头 / 宏观）代理 → eventradar",
)


def _proxy_error_response(exc: EventradarProxyError):
    """Translate a proxy-layer exception into the platform's error envelope."""
    if exc.upstream_status == 404:
        return (
            APIResponse.error(
                message=str(exc) or "事件不存在",
                code=APIConstants.ERROR_CODES["NOT_FOUND"],
                http_status=404,
            ),
            404,
        )
    return (
        APIResponse.error(
            message=str(exc),
            code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
            http_status=exc.http_status,
        ),
        exc.http_status,
    )


def _parse_tri_bool(value):
    """Coerce request JSON into True / False / None.

    Accepts JSON booleans (the common case from the frontend), plus the
    string forms ``"true"``/``"false"`` so an old query-string client can
    still send them. Anything else — including the omitted key — collapses
    to None, which the downstream layer treats as "no filter".
    """
    if value is True or value is False:
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
    return None


def _validation_error_response(exc: ValueError):
    return (
        APIResponse.error(
            message=str(exc),
            code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
            http_status=400,
        ),
        400,
    )


@announcements_ns.route("/health")
class AnnouncementsHealth(Resource):
    """Pass-through to eventradar /health, or a "not_configured" placeholder
    when the upstream URL is unset. Always 200 in placeholder mode so the
    frontend status badge can render without surfacing red errors."""

    def get(self):
        try:
            return APIResponse.success(EventradarProxyService.health())
        except EventradarProxyError as exc:
            return _proxy_error_response(exc)


@announcements_ns.route("")
class AnnouncementsList(Resource):
    """List forward-looking events with pagination + filters.

    POST body (all optional):
        page, page_size, sort_by, sort_order
        filters: { date_from, date_to, scope, event_type, keyword,
                   industry, theme, stock_code, importance_min }

    While eventradar is unconfigured this returns an empty paginated payload
    with ``placeholder=true``; the frontend currently renders mock data on
    top of that, but the response shape is the same one the real upstream
    will return.
    """

    def post(self):
        try:
            payload = request.get_json(force=True, silent=True) or {}
            page = parse_int(str(payload.get("page", 1)), default=1, minimum=1)
            page_size = parse_int(
                str(payload.get("page_size", 20)),
                default=20,
                minimum=1,
                maximum=200,
            )
            sort_by = str(payload.get("sort_by") or "expected_at").strip() or "expected_at"
            sort_order = str(payload.get("sort_order") or "asc").strip() or "asc"

            raw_filters = payload.get("filters") or {}
            if not isinstance(raw_filters, dict):
                raise ValueError("filters 必须为对象")

            filters = {
                "date_from": parse_date(raw_filters.get("date_from"), required=False) or "",
                "date_to": parse_date(raw_filters.get("date_to"), required=False) or "",
                "scope": str(raw_filters.get("scope") or "").strip().lower(),
                "event_type": str(raw_filters.get("event_type") or "").strip().lower(),
                # Adapter-level source identifier — single value
                # ("em_yjyg") or comma-separated for unioning a platform's
                # multiple sources ("em_gsrl,em_yjyg" for all of 东方财富).
                "source": str(raw_filters.get("source") or "").strip(),
                "keyword": str(raw_filters.get("keyword") or "").strip(),
                "industry": str(raw_filters.get("industry") or "").strip(),
                "theme": str(raw_filters.get("theme") or "").strip(),
                "stock_code": str(raw_filters.get("stock_code") or "").strip().upper(),
                "importance_min": raw_filters.get("importance_min"),
                # has_leader is a tri-state: True / False / None (unset).
                # We pass JSON booleans straight through; anything else (a
                # missing key or a stray string) becomes None and the
                # eventradar layer treats it as "no filter".
                "has_leader": _parse_tri_bool(raw_filters.get("has_leader")),
            }

            data = EventradarProxyService.list_announcements(
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
                filters=filters,
            )
            return APIResponse.success(data)
        except ValueError as exc:
            return _validation_error_response(exc)
        except EventradarProxyError as exc:
            return _proxy_error_response(exc)


@announcements_ns.route("/<string:event_id>")
class AnnouncementDetail(Resource):
    def get(self, event_id: str):
        try:
            data = EventradarProxyService.get_announcement_detail(event_id)
            if not data.get("found", False):
                # Placeholder mode also lands here. We return 404 with a
                # friendly message rather than 200/found:false because clients
                # treating "missing event" as an error path is the standard
                # convention everywhere else in this API.
                return (
                    APIResponse.error(
                        message=f"事件不存在: {event_id}",
                        code=APIConstants.ERROR_CODES["NOT_FOUND"],
                        http_status=404,
                    ),
                    404,
                )
            return APIResponse.success(data)
        except ValueError as exc:
            return _validation_error_response(exc)
        except EventradarProxyError as exc:
            return _proxy_error_response(exc)


@announcements_ns.route("/filters/meta")
class AnnouncementFilterMeta(Resource):
    """Distinct values powering the filter dropdowns. Empty arrays in
    placeholder mode."""

    def get(self):
        try:
            return APIResponse.success(EventradarProxyService.get_filter_meta())
        except EventradarProxyError as exc:
            return _proxy_error_response(exc)


@announcements_ns.route("/source-counts")
class AnnouncementSourceCounts(Resource):
    """Per-source event counts — feeds the platform/source tabs.

    Response shape: ``{"counts": {"em_yjyg": 7800, "em_gsrl": 701, ...}}``.
    Empty ``counts`` dict in placeholder mode (eventradar unconfigured).
    """

    def get(self):
        try:
            return APIResponse.success(EventradarProxyService.get_source_counts())
        except EventradarProxyError as exc:
            return _proxy_error_response(exc)
