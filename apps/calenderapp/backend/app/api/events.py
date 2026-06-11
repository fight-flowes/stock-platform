from flask import make_response, request
from flask_restx import Namespace, Resource, fields

from app.api.params import parse_date, parse_int
from app.services.csv_import_service import CsvImportService
from app.services.calendar_service import CalendarService
from app.services.events_service import EventsService
from config.api_config import APIConstants, APIResponse, EventTypes


events_ns = Namespace("events", description="日历事件")

event_model = events_ns.model(
    "CalendarEvent",
    {
        "id": fields.Integer(readonly=True),
        "event_date": fields.String(required=True),
        "title": fields.String(required=True),
        "importance": fields.Integer(required=True, min=1, max=5),
        "event_type": fields.String,
        "source": fields.String,
        "source_url": fields.String,  # 新增
        "description": fields.String,
        "stock_list": fields.List(fields.String),
        "credibility": fields.String,  # 新增
        "created_at": fields.String(readonly=True),
        "updated_at": fields.String(readonly=True),
    },
)


@events_ns.route("/")
class Events(Resource):
    @events_ns.param("page", "页码", type=int, default=APIConstants.DEFAULT_PAGE)
    @events_ns.param("page_size", "每页数量", type=int, default=APIConstants.DEFAULT_PAGE_SIZE)
    @events_ns.param("start_date", "开始日期 YYYY-MM-DD")
    @events_ns.param("end_date", "结束日期 YYYY-MM-DD")
    @events_ns.param("q", "搜索关键词")
    @events_ns.param("importance_min", "最小重要性", type=int)
    @events_ns.param("importance_max", "最大重要性", type=int)
    @events_ns.param("event_type", "事件类型")
    @events_ns.param("stock_code", "股票代码")
    def get(self):
        args = request.args
        page = parse_int(args.get("page"), default=APIConstants.DEFAULT_PAGE, minimum=1)
        page_size = parse_int(
            args.get("page_size"),
            default=APIConstants.DEFAULT_PAGE_SIZE,
            minimum=1,
            maximum=APIConstants.MAX_PAGE_SIZE,
        )
        start_date = parse_date(args.get("start_date"))
        end_date = parse_date(args.get("end_date"))
        result = EventsService.list_events(
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date,
            q=args.get("q"),
            importance_min=args.get("importance_min"),
            importance_max=args.get("importance_max"),
            event_type=args.get("event_type"),
            stock_code=args.get("stock_code"),
        )
        extra = {"event_types": EventTypes.all()}
        if start_date and end_date:
            extra["day_meta"] = CalendarService.day_meta_map(start_date, end_date, ensure=True)
        return APIResponse.paginated(
            data=result["items"],
            total=result["total"],
            page=page,
            page_size=page_size,
            extra=extra,
        )

    @events_ns.expect(event_model, validate=False)
    def post(self):
        try:
            payload = request.get_json(force=True, silent=True) or {}
            created = EventsService.create_event(payload)
            return APIResponse.success(created, message="创建成功"), 201
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )


@events_ns.route("/<int:event_id>")
class EventDetail(Resource):
    def get(self, event_id: int):
        event = EventsService.get_event(event_id)
        if event:
            return APIResponse.success(event)
        return (
            APIResponse.error(
                message="事件不存在",
                code=APIConstants.ERROR_CODES["NOT_FOUND"],
                http_status=404,
            ),
            404,
        )

    @events_ns.expect(event_model, validate=False)
    def put(self, event_id: int):
        try:
            payload = request.get_json(force=True, silent=True) or {}
            updated = EventsService.update_event(event_id, payload)
            if not updated:
                return (
                    APIResponse.error(
                        message="事件不存在",
                        code=APIConstants.ERROR_CODES["NOT_FOUND"],
                        http_status=404,
                    ),
                    404,
                )
            return APIResponse.success(updated, message="更新成功")
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )

    def delete(self, event_id: int):
        ok = EventsService.delete_event(event_id)
        if not ok:
            return (
                APIResponse.error(
                    message="事件不存在",
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        return APIResponse.success(message="删除成功")


@events_ns.route("/upcoming")
class Upcoming(Resource):
    @events_ns.param("days", "未来天数", type=int, default=7)
    @events_ns.param("importance_min", "最小重要性", type=int, default=3)
    def get(self):
        args = request.args
        days = parse_int(args.get("days"), default=7, minimum=1, maximum=366)
        importance_min = parse_int(args.get("importance_min"), default=3, minimum=1, maximum=5)
        items = EventsService.upcoming(days=days, importance_min=importance_min)
        return APIResponse.success(items)


@events_ns.route("/statistics")
class Statistics(Resource):
    @events_ns.param("start_date", "开始日期 YYYY-MM-DD")
    @events_ns.param("end_date", "结束日期 YYYY-MM-DD")
    def get(self):
        args = request.args
        start_date = parse_date(args.get("start_date"), required=True)
        end_date = parse_date(args.get("end_date"), required=True)
        data = EventsService.statistics(start_date=start_date, end_date=end_date)
        return APIResponse.success(data)


@events_ns.route("/template.csv")
class EventsTemplate(Resource):
    def get(self):
        csv_text = CsvImportService.events_template_csv()
        resp = make_response(csv_text)
        resp.headers["Content-Type"] = "text/csv; charset=utf-8"
        resp.headers["Content-Disposition"] = "attachment; filename=events_template.csv"
        return resp


@events_ns.route("/import")
class EventsImport(Resource):
    def post(self):
        file = request.files.get("file")
        if not file:
            return (
                APIResponse.error(
                    message="缺少文件字段 file",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        filename = (file.filename or "events.csv").strip() or "events.csv"
        if not filename.lower().endswith(".csv"):
            return (
                APIResponse.error(
                    message="仅支持 CSV 文件",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        raw = file.read()
        if len(raw) > 5 * 1024 * 1024:
            return (
                APIResponse.error(
                    message="文件过大",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=413,
                ),
                413,
            )
        try:
            result = CsvImportService.import_events_csv(raw, filename=filename)
            return APIResponse.success(result.to_dict(), message="导入完成")
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
