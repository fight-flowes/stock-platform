from __future__ import annotations

from flask import request
from flask_restx import Namespace, Resource

from app.api.params import parse_date, parse_int
from app.services.calendar_v2_service import CalendarV2Service, CalendarV2ServiceError
from config.api_config import APIConstants, APIResponse


calendar_v2_ns = Namespace("calendar-v2", description="可信事件日历（DuckDB / stockkb）")


def _error_response(exc: Exception, http_status: int = 500):
    code = APIConstants.ERROR_CODES["INTERNAL_ERROR"]
    if http_status == 400:
        code = APIConstants.ERROR_CODES["VALIDATION_ERROR"]
    if http_status == 404:
        code = APIConstants.ERROR_CODES["NOT_FOUND"]
    return (
        APIResponse.error(
            message=str(exc),
            code=code,
            http_status=http_status,
        ),
        http_status,
    )


@calendar_v2_ns.route("/health")
class CalendarV2Health(Resource):
    def get(self):
        try:
            return APIResponse.success(CalendarV2Service.health())
        except CalendarV2ServiceError as exc:
            return _error_response(exc, 500)


@calendar_v2_ns.route("/filters/meta")
class CalendarV2FilterMeta(Resource):
    def get(self):
        try:
            return APIResponse.success(CalendarV2Service.get_filter_meta())
        except CalendarV2ServiceError as exc:
            return _error_response(exc, 500)


@calendar_v2_ns.route("/events")
class CalendarV2Events(Resource):
    @calendar_v2_ns.param("start_date", "开始日期 YYYY-MM-DD")
    @calendar_v2_ns.param("end_date", "结束日期 YYYY-MM-DD")
    @calendar_v2_ns.param("keyword", "关键词")
    @calendar_v2_ns.param("industry", "行业")
    @calendar_v2_ns.param("event_type", "事件类型")
    @calendar_v2_ns.param("status", "状态 all/trusted/pending/caution/excluded")
    @calendar_v2_ns.param("override_mode", "覆写视图 all/manual/auto/manual_include/manual_exclude")
    def get(self):
        try:
            args = request.args
            data = CalendarV2Service.list_events(
                start_date=parse_date(args.get("start_date"), required=False),
                end_date=parse_date(args.get("end_date"), required=False),
                keyword=str(args.get("keyword") or "").strip(),
                industry=str(args.get("industry") or "").strip(),
                event_type=str(args.get("event_type") or "all").strip().lower(),
                status=str(args.get("status") or "all").strip().lower(),
                override_mode=str(args.get("override_mode") or "all").strip().lower(),
            )
            return APIResponse.success(data)
        except ValueError as exc:
            return _error_response(exc, 400)
        except CalendarV2ServiceError as exc:
            return _error_response(exc, 500)


@calendar_v2_ns.route("/upcoming")
class CalendarV2Upcoming(Resource):
    @calendar_v2_ns.param("days", "未来天数", type=int, default=14)
    @calendar_v2_ns.param("limit", "返回条数", type=int, default=20)
    def get(self):
        try:
            args = request.args
            days = parse_int(args.get("days"), default=14, minimum=1, maximum=90)
            limit = parse_int(args.get("limit"), default=20, minimum=1, maximum=100)
            return APIResponse.success(CalendarV2Service.list_upcoming(days=days, limit=limit))
        except ValueError as exc:
            return _error_response(exc, 400)
        except CalendarV2ServiceError as exc:
            return _error_response(exc, 500)


@calendar_v2_ns.route("/events/<string:event_key>")
class CalendarV2EventDetail(Resource):
    def get(self, event_key: str):
        try:
            data = CalendarV2Service.get_event_detail(event_key)
            if not data.get("found", False):
                return _error_response(ValueError(f"事件不存在: {event_key}"), 404)
            return APIResponse.success(data)
        except ValueError as exc:
            return _error_response(exc, 400)
        except CalendarV2ServiceError as exc:
            return _error_response(exc, 500)


@calendar_v2_ns.route("/events/<string:event_key>/override")
class CalendarV2EventOverride(Resource):
    def post(self, event_key: str):
        try:
            payload = request.get_json(force=True, silent=True) or {}
            data = CalendarV2Service.set_override(
                event_key,
                decision=str(payload.get("decision") or "").strip().lower(),
                calendar_date_start=parse_date(payload.get("calendar_date_start"), required=False) or "",
                calendar_date_end=parse_date(payload.get("calendar_date_end"), required=False) or "",
                note=str(payload.get("note") or "").strip(),
            )
            return APIResponse.success(data, message="override_saved")
        except ValueError as exc:
            return _error_response(exc, 400)
        except CalendarV2ServiceError as exc:
            return _error_response(exc, 500)
