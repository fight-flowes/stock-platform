from flask import request
from flask_restx import Namespace, Resource, fields

from app.api.params import parse_bool, parse_date
from app.services.calendar_service import CalendarService
from config.api_config import APIResponse

calendar_ns = Namespace("calendar", description="日历元数据")

day_model = calendar_ns.model(
    "CalendarDay",
    {
        "date": fields.String(required=True),
        "lunar_day": fields.String(required=True),
        "holiday_name": fields.String,
        "is_rest": fields.Boolean(required=True),
        "is_work": fields.Boolean(required=True),
        "is_trading_day": fields.Boolean,
        "created_at": fields.String,
        "updated_at": fields.String,
    },
)


@calendar_ns.route("/days")
class CalendarDays(Resource):
    @calendar_ns.param("start_date", "开始日期 YYYY-MM-DD", required=True)
    @calendar_ns.param("end_date", "结束日期 YYYY-MM-DD", required=True)
    @calendar_ns.param("ensure", "缺失日期是否自动生成并写入数据库", type=bool, default=True)
    def get(self):
        args = request.args
        start_date = parse_date(args.get("start_date"), required=True)
        end_date = parse_date(args.get("end_date"), required=True)
        ensure = parse_bool(args.get("ensure"), default=True)
        items = CalendarService.list_days(start_date, end_date, ensure=ensure)
        trading_days = set(CalendarService.trading_days(start_date, end_date))
        for item in items:
            item["is_trading_day"] = item["date"] in trading_days
        return APIResponse.success({"items": items, "start_date": start_date, "end_date": end_date})
