from flask import request
from flask_restx import Namespace, Resource

from app.api.params import parse_date, parse_int
from app.services.stockkb_proxy_service import StockkbProxyError, StockkbProxyService
from config.api_config import APIConstants, APIResponse


stockkb_ns = Namespace("stockkb", description="stockkb 事件知识库代理")


@stockkb_ns.route("/health")
class StockkbHealth(Resource):
    def get(self):
        try:
            return APIResponse.success(StockkbProxyService.health())
        except StockkbProxyError as exc:
            if exc.upstream_status == 404:
                return (
                    APIResponse.error(
                        message="事件不存在",
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


@stockkb_ns.route("/report")
class StockkbReport(Resource):
    @stockkb_ns.param("stock_code", "股票代码", required=True)
    @stockkb_ns.param("report_date", "报告日期 YYYY-MM-DD", required=True)
    def get(self):
        try:
            stock_code = (request.args.get("stock_code") or "").strip()
            report_date = parse_date(request.args.get("report_date"), required=True)
            data = StockkbProxyService.get_report_summary(stock_code, report_date)
            return APIResponse.success(data)
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except StockkbProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@stockkb_ns.route("/events")
class StockkbEvents(Resource):
    def post(self):
        try:
            payload = request.get_json(force=True, silent=True) or {}
            stock_code = (payload.get("stock_code") or "").strip()
            report_date = parse_date(payload.get("report_date"), required=True)
            page = parse_int(str(payload.get("page", 1)), default=1, minimum=1)
            page_size = parse_int(str(payload.get("page_size", 20)), default=20, minimum=1, maximum=200)
            event_scope = (payload.get("event_scope") or "default").strip() or "default"
            data = StockkbProxyService.list_events(
                stock_code=stock_code,
                report_date=report_date,
                page=page,
                page_size=page_size,
                event_scope=event_scope,
            )
            return APIResponse.success(data)
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except StockkbProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@stockkb_ns.route("/events/<string:event_id>")
class StockkbEventDetail(Resource):
    def get(self, event_id: str):
        try:
            data = StockkbProxyService.get_event_detail(event_id)
            if not data.get("found", False):
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
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except StockkbProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@stockkb_ns.route("/market-events")
class StockkbMarketEvents(Resource):
    def post(self):
        try:
            payload = request.get_json(force=True, silent=True) or {}
            page = parse_int(str(payload.get("page", 1)), default=1, minimum=1)
            page_size = parse_int(str(payload.get("page_size", 20)), default=20, minimum=1, maximum=200)
            sort_by = str(payload.get("sort_by") or "latest_active_date").strip() or "latest_active_date"
            sort_order = str(payload.get("sort_order") or "desc").strip() or "desc"
            raw_filters = payload.get("filters") or {}
            if not isinstance(raw_filters, dict):
                raise ValueError("filters 必须为对象")
            filters = {
                "date_from": parse_date(raw_filters.get("date_from"), required=False) or "",
                "date_to": parse_date(raw_filters.get("date_to"), required=False) or "",
                "keyword": str(raw_filters.get("keyword") or "").strip(),
                "industry": str(raw_filters.get("industry") or "").strip(),
                "theme": str(raw_filters.get("theme") or "").strip(),
                "event_type": str(raw_filters.get("event_type") or "").strip().lower(),
                "favorites_only": raw_filters.get("favorites_only"),
                "is_cross_stock": raw_filters.get("is_cross_stock"),
                "min_affected_stock_count": raw_filters.get("min_affected_stock_count"),
                "is_active": raw_filters.get("is_active"),
            }
            data = StockkbProxyService.list_market_events(
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
                filters=filters,
            )
            return APIResponse.success(data)
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except StockkbProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@stockkb_ns.route("/market-events/filters/meta")
class StockkbMarketEventFilterMeta(Resource):
    def get(self):
        try:
            data = StockkbProxyService.get_market_event_filter_meta()
            return APIResponse.success(data)
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except StockkbProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@stockkb_ns.route("/market-events/<string:event_key>")
class StockkbMarketEventDetail(Resource):
    def get(self, event_key: str):
        try:
            data = StockkbProxyService.get_market_event_detail(event_key)
            if not data.get("found", False):
                return (
                    APIResponse.error(
                        message=f"市场事件不存在: {event_key}",
                        code=APIConstants.ERROR_CODES["NOT_FOUND"],
                        http_status=404,
                    ),
                    404,
                )
            return APIResponse.success(data)
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except StockkbProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@stockkb_ns.route("/market-events/<string:event_key>/timeline")
class StockkbMarketEventTimeline(Resource):
    def get(self, event_key: str):
        try:
            data = StockkbProxyService.get_market_event_timeline(event_key)
            return APIResponse.success(data)
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except StockkbProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )


@stockkb_ns.route("/events/<string:event_id>/favorite")
class StockkbEventFavorite(Resource):
    def post(self, event_id: str):
        try:
            data = StockkbProxyService.favorite_event(event_id)
            if not data.get("found", False):
                return (
                    APIResponse.error(
                        message=f"事件不存在: {event_id}",
                        code=APIConstants.ERROR_CODES["NOT_FOUND"],
                        http_status=404,
                    ),
                    404,
                )
            return APIResponse.success(data, message="收藏成功")
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except StockkbProxyError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=exc.http_status,
                ),
                exc.http_status,
            )

    def delete(self, event_id: str):
        try:
            data = StockkbProxyService.unfavorite_event(event_id)
            if not data.get("found", False):
                return (
                    APIResponse.error(
                        message=f"事件不存在: {event_id}",
                        code=APIConstants.ERROR_CODES["NOT_FOUND"],
                        http_status=404,
                    ),
                    404,
                )
            return APIResponse.success(data, message="已取消收藏")
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
