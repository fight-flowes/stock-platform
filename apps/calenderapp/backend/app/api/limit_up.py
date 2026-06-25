import json
from flask import make_response, request
from flask_restx import Namespace, Resource, fields

from app.api.params import parse_bool, parse_date, parse_int
from app.services.limit_up_service import LimitUpService
from app.services.stockkb_proxy_service import StockkbProxyError, StockkbProxyService
from config.api_config import APIConstants, APIResponse
from app.config import get_tushare_pro


limit_up_ns = Namespace("limit-up", description="涨停股票管理")


def _limit_up_query_filters(args):
    return {
        "start_date": args.get("start_date"),
        "end_date": args.get("end_date"),
        "consecutive_min": args.get("consecutive_min"),
        "consecutive_max": args.get("consecutive_max"),
        "close_min": args.get("close_min"),
        "close_max": args.get("close_max"),
        "open_count_min": args.get("open_count_min"),
        "open_count_max": args.get("open_count_max"),
        "industry": args.get("industry"),
        "concept": args.get("concept"),
        "strength_min": args.get("strength_min"),
        "strength_max": args.get("strength_max"),
        "is_dragon_head": parse_bool(args.get("is_dragon_head"), default=None),
        "limit_up_type": args.get("limit_up_type"),
        "q": args.get("q"),
    }


def _join_values(values, *, item_sep=" | ", pair_sep=" "):
    normalized = []
    for value in values or []:
        if isinstance(value, dict):
            left = str(value.get("stock_name") or "").strip()
            right = str(value.get("stock_code") or "").strip()
            text = (left + pair_sep + right).strip() if left or right else ""
        else:
            text = str(value or "").strip()
        if text:
            normalized.append(text)
    return item_sep.join(normalized)

limit_up_model = limit_up_ns.model(
    "LimitUpStock",
    {
        "id": fields.Integer(readonly=True),
        "stock_code": fields.String(required=True, description="股票代码"),
        "stock_name": fields.String(required=True, description="股票名称"),
        "limit_up_date": fields.String(required=True, description="涨停日期 YYYY-MM-DD"),
        "consecutive_days": fields.Integer(description="连板数", default=1),
        "limit_up_type": fields.String(description="涨停类型", default="first_board"),
        "seal_amount": fields.Float(description="封单金额（万元）", default=0),
        "seal_ratio": fields.Float(description="封单比", default=0),
        "turnover_rate": fields.Float(description="换手率%", default=0),
        "first_limit_time": fields.String(description="首次涨停时间 HH:MM:SS"),
        "last_limit_time": fields.String(description="最后涨停时间 HH:MM:SS"),
        "open_count": fields.Integer(description="开板次数", default=0),
        "industry": fields.String(description="所属行业"),
        "concept_tags": fields.List(fields.String, description="概念标签"),
        "institution_net_buy": fields.Float(description="机构净买入（万元）", default=0),
        "hot_money_net_buy": fields.Float(description="游资净买入（万元）", default=0),
        "north_net_buy": fields.Float(description="北向净买入（万元）", default=0),
        "total_net_buy": fields.Float(description="总净买入（万元）", default=0),
        "reason_category": fields.String(description="原因分类"),
        "reason_detail": fields.String(description="原因详情"),
        "strength_level": fields.Integer(readonly=True, description="强度等级1-5"),
        "strength_score": fields.Float(readonly=True, description="强度评分"),
        "is_dragon_head": fields.Boolean(description="是否龙头", default=False),
        "dragon_rank": fields.Integer(description="龙头排名", default=0),
        "has_analysis_report": fields.Boolean(description="MinIO 中是否存在分析报告", default=False),
        "source": fields.String(description="数据来源", default="manual"),
        "created_at": fields.String(readonly=True),
        "updated_at": fields.String(readonly=True),
    },
)


@limit_up_ns.route("/")
class LimitUps(Resource):
    @limit_up_ns.param("page", "页码", type=int, default=APIConstants.DEFAULT_PAGE)
    @limit_up_ns.param("page_size", "每页数量", type=int, default=APIConstants.DEFAULT_PAGE_SIZE)
    @limit_up_ns.param("start_date", "开始日期 YYYY-MM-DD")
    @limit_up_ns.param("end_date", "结束日期 YYYY-MM-DD")
    @limit_up_ns.param("consecutive_min", "最小连板数", type=int)
    @limit_up_ns.param("consecutive_max", "最大连板数", type=int)
    @limit_up_ns.param("close_min", "最低价格（严格大于）", type=float)
    @limit_up_ns.param("close_max", "最高价格", type=float)
    @limit_up_ns.param("open_count_min", "最小开板次数（严格大于）", type=int)
    @limit_up_ns.param("open_count_max", "最大开板次数", type=int)
    @limit_up_ns.param("industry", "行业筛选")
    @limit_up_ns.param("concept", "概念筛选")
    @limit_up_ns.param("strength_min", "最小强度等级", type=int)
    @limit_up_ns.param("strength_max", "最大强度等级", type=int)
    @limit_up_ns.param("is_dragon_head", "仅龙头", type=bool)
    @limit_up_ns.param("limit_up_type", "涨停类型")
    @limit_up_ns.param("q", "搜索关键词")
    def get(self):
        """涨停股列表"""
        args = request.args
        page = parse_int(args.get("page"), default=APIConstants.DEFAULT_PAGE, minimum=1)
        page_size = parse_int(
            args.get("page_size"),
            default=APIConstants.DEFAULT_PAGE_SIZE,
            minimum=1,
            maximum=APIConstants.MAX_PAGE_SIZE,
        )
        result = LimitUpService.list_limit_ups(
            page=page,
            page_size=page_size,
            **_limit_up_query_filters(args),
        )
        return APIResponse.paginated(
            data=result["items"],
            total=result["total"],
            page=page,
            page_size=page_size,
        )

    @limit_up_ns.expect(limit_up_model, validate=False)
    def post(self):
        """创建涨停记录"""
        try:
            payload = request.get_json(force=True, silent=True) or {}
            created = LimitUpService.create_limit_up(payload)
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


@limit_up_ns.route("/<int:limit_up_id>")
class LimitUpDetail(Resource):
    def get(self, limit_up_id: int):
        """涨停详情"""
        item = LimitUpService.get_limit_up(limit_up_id)
        if item:
            return APIResponse.success(item)
        return (
            APIResponse.error(
                message="涨停记录不存在",
                code=APIConstants.ERROR_CODES["NOT_FOUND"],
                http_status=404,
            ),
            404,
        )

    @limit_up_ns.expect(limit_up_model, validate=False)
    def put(self, limit_up_id: int):
        """更新涨停记录"""
        try:
            payload = request.get_json(force=True, silent=True) or {}
            updated = LimitUpService.update_limit_up(limit_up_id, payload)
            if not updated:
                return (
                    APIResponse.error(
                        message="涨停记录不存在",
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

    def delete(self, limit_up_id: int):
        """删除涨停记录"""
        ok = LimitUpService.delete_limit_up(limit_up_id)
        if not ok:
            return (
                APIResponse.error(
                    message="涨停记录不存在",
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        return APIResponse.success(message="删除成功")


@limit_up_ns.route("/batch-update")
class LimitUpBatchUpdate(Resource):
    def put(self):
        """批量更新涨停记录"""
        try:
            payload = request.get_json(force=True, silent=True) or {}
            items = payload.get("items") or []
            updates = payload.get("updates") or {}
            if updates:
                result = LimitUpService.batch_update_limit_ups(items, updates)
                return APIResponse.success(result, message=f"批量更新成功，共 {result['updated']} 条")

            from app.services.tushare_enhanced_service import TushareEnhancedService
            result = TushareEnhancedService.refresh_selected_limit_ups(items)
            return APIResponse.success(result, message=f"自动更新完成，共刷新 {result['updated']} 条")
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )


@limit_up_ns.route("/consecutive")
class ConsecutiveRank(Resource):
    @limit_up_ns.param("date", "交易日期 YYYY-MM-DD", required=True)
    def get(self):
        """连板榜排名"""
        args = request.args
        trade_date = parse_date(args.get("date"), required=True)
        try:
            items = LimitUpService.consecutive_rank(trade_date)
            return APIResponse.success(items)
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )


@limit_up_ns.route("/dragon-head")
class DragonHeads(Resource):
    @limit_up_ns.param("date", "交易日期 YYYY-MM-DD", required=True)
    def get(self):
        """龙头股列表"""
        args = request.args
        trade_date = parse_date(args.get("date"), required=True)
        try:
            items = LimitUpService.dragon_heads(trade_date)
            return APIResponse.success(items)
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )


@limit_up_ns.route("/statistics")
class Statistics(Resource):
    @limit_up_ns.param("start_date", "开始日期 YYYY-MM-DD")
    @limit_up_ns.param("end_date", "结束日期 YYYY-MM-DD")
    def get(self):
        """区间统计"""
        args = request.args
        start_date = parse_date(args.get("start_date"), required=True)
        end_date = parse_date(args.get("end_date"), required=True)
        data = LimitUpService.statistics(start_date=start_date, end_date=end_date)
        return APIResponse.success(data)


@limit_up_ns.route("/fund-flow")
class FundFlowRank(Resource):
    @limit_up_ns.param("start_date", "开始日期 YYYY-MM-DD")
    @limit_up_ns.param("end_date", "结束日期 YYYY-MM-DD")
    @limit_up_ns.param("top", "返回数量", type=int, default=20)
    def get(self):
        """资金流向排行"""
        args = request.args
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        top = parse_int(args.get("top"), default=20, minimum=1, maximum=50)
        data = LimitUpService.fund_flow_rank(start_date=start_date, end_date=end_date, top=top)
        return APIResponse.success(data)


@limit_up_ns.route("/concept-hot")
class ConceptHot(Resource):
    @limit_up_ns.param("start_date", "开始日期 YYYY-MM-DD")
    @limit_up_ns.param("end_date", "结束日期 YYYY-MM-DD")
    @limit_up_ns.param("top", "返回数量", type=int, default=20)
    def get(self):
        """概念热度统计"""
        args = request.args
        start_date = parse_date(args.get("start_date"), required=True)
        end_date = parse_date(args.get("end_date"), required=True)
        top = parse_int(args.get("top"), default=20, minimum=1, maximum=50)
        data = LimitUpService.concept_statistics(start_date=start_date, end_date=end_date, top=top)
        return APIResponse.success(data)


@limit_up_ns.route("/template.csv")
class LimitUpTemplate(Resource):
    def get(self):
        """下载导入模板"""
        csv_text = """stock_code,stock_name,limit_up_date,consecutive_days,seal_amount,first_limit_time,open_count,industry,concept_tags,institution_net_buy,hot_money_net_buy,reason_detail
002361.SZ,神剑股份,2026-04-01,5,230000,09:35:00,0,航天军工,"航天|军工|低空经济",120000,80000,低空经济政策利好"""
        resp = make_response(csv_text)
        resp.headers["Content-Type"] = "text/csv; charset=utf-8"
        resp.headers["Content-Disposition"] = "attachment; filename=limit_up_template.csv"
        return resp


@limit_up_ns.route("/export")
class LimitUpExport(Resource):
    @limit_up_ns.param("start_date", "开始日期 YYYY-MM-DD")
    @limit_up_ns.param("end_date", "结束日期 YYYY-MM-DD")
    @limit_up_ns.param("format", "导出格式 csv/json", default="csv")
    def get(self):
        """导出涨停数据"""
        import io
        from datetime import datetime
        
        args = request.args
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        export_format = args.get("format", "csv")
        
        # 获取数据
        result = LimitUpService.list_limit_ups(
            page=1,
            page_size=10000,  # 最大导出数量
            start_date=start_date,
            end_date=end_date,
        )
        
        items = result.get("items", [])
        
        if export_format == "json":
            # JSON 导出
            resp = make_response(json.dumps(items, ensure_ascii=False, indent=2))
            resp.headers["Content-Type"] = "application/json; charset=utf-8"
            resp.headers["Content-Disposition"] = f"attachment; filename=limit_up_export_{datetime.now().strftime('%Y%m%d')}.json"
            return resp
        else:
            # CSV 导出
            import csv
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            headers = ["股票代码", "股票名称", "涨停日期", "连板数", "涨停类型", "封单金额(万)", 
                       "封单比", "换手率", "封板时间", "开板次数", "行业", "概念标签",
                       "机构净买(万)", "游资净买(万)", "强度等级", "强度评分", "是否龙头"]
            writer.writerow(headers)
            
            # 写入数据
            for item in items:
                concept_str = "|".join(item.get("concept_tags") or [])
                row = [
                    item.get("stock_code", ""),
                    item.get("stock_name", ""),
                    item.get("limit_up_date", ""),
                    item.get("consecutive_days", 1),
                    item.get("limit_up_type", ""),
                    item.get("seal_amount", 0),
                    item.get("seal_ratio", 0),
                    item.get("turnover_rate", 0),
                    item.get("first_limit_time", ""),
                    item.get("open_count", 0),
                    item.get("industry", ""),
                    concept_str,
                    item.get("institution_net_buy", 0),
                    item.get("hot_money_net_buy", 0),
                    item.get("strength_level", 0),
                    item.get("strength_score", 0),
                    "是" if item.get("is_dragon_head") else "否",
                ]
                writer.writerow(row)
            
            output.seek(0)
            resp = make_response(output.getvalue())
            resp.headers["Content-Type"] = "text/csv; charset=utf-8"
            resp.headers["Content-Disposition"] = f"attachment; filename=limit_up_export_{datetime.now().strftime('%Y%m%d')}.csv"
            return resp


@limit_up_ns.route("/events-export")
class LimitUpEventsExport(Resource):
    @limit_up_ns.param("date", "交易日期 YYYY-MM-DD", required=True)
    @limit_up_ns.param("consecutive_min", "最小连板数", type=int)
    @limit_up_ns.param("consecutive_max", "最大连板数", type=int)
    @limit_up_ns.param("close_min", "最低价格（严格大于）", type=float)
    @limit_up_ns.param("close_max", "最高价格", type=float)
    @limit_up_ns.param("open_count_min", "最小开板次数（严格大于）", type=int)
    @limit_up_ns.param("open_count_max", "最大开板次数", type=int)
    @limit_up_ns.param("industry", "行业筛选")
    @limit_up_ns.param("concept", "概念筛选")
    @limit_up_ns.param("strength_min", "最小强度等级", type=int)
    @limit_up_ns.param("strength_max", "最大强度等级", type=int)
    @limit_up_ns.param("is_dragon_head", "仅龙头", type=bool)
    @limit_up_ns.param("limit_up_type", "涨停类型")
    @limit_up_ns.param("q", "搜索关键词")
    def get(self):
        """导出当日涨停解析事件"""
        import csv
        import io

        args = request.args
        trade_date = parse_date(args.get("date"), required=True)
        filters = _limit_up_query_filters(args)
        filters["start_date"] = trade_date
        filters["end_date"] = trade_date

        try:
            result = LimitUpService.list_limit_ups(
                page=1,
                page_size=5000,
                **filters,
            )
            limit_up_items = result.get("items", [])
            report_candidates = [item for item in limit_up_items if item.get("has_analysis_report")]

            rows = []
            failed_count = 0
            for item in report_candidates:
                stock_code = str(item.get("stock_code") or "").strip()
                stock_name = str(item.get("stock_name") or "").strip()
                if not stock_code:
                    continue
                try:
                    events_payload = StockkbProxyService.list_all_events(
                        stock_code=stock_code,
                        report_date=trade_date,
                        page_size=200,
                    )
                    event_items = events_payload.get("items") or []
                    if not event_items:
                        continue
                    report_summary = StockkbProxyService.get_report_summary(stock_code, trade_date)
                except (StockkbProxyError, ValueError):
                    failed_count += 1
                    continue

                for event in event_items:
                    rows.append(
                        [
                            trade_date,
                            stock_code,
                            stock_name,
                            item.get("consecutive_days", 1),
                            "是" if item.get("is_dragon_head") else "否",
                            item.get("industry", "") or "",
                            report_summary.get("report_title", "") or event.get("report_title", "") or "",
                            report_summary.get("core_logic", "") or "",
                            report_summary.get("risk_summary", "") or "",
                            event.get("event_id", "") or "",
                            event.get("event_name", "") or "",
                            event.get("event_time_text", "") or "",
                            event.get("event_scope", "") or "",
                            event.get("event_type", "") or "",
                            event.get("scope_reason", "") or "",
                            event.get("event_content", "") or "",
                            event.get("source_name", "") or "",
                            event.get("source_url", "") or "",
                            _join_values(event.get("affected_stocks")),
                            _join_values(event.get("affected_industries")),
                            _join_values(event.get("affected_themes")),
                        ]
                    )

            if not rows:
                if report_candidates and failed_count == len(report_candidates):
                    return (
                        APIResponse.error(
                            message="事件导出失败，stockkb 数据暂时不可用",
                            code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                            http_status=502,
                        ),
                        502,
                    )
                return (
                    APIResponse.error(
                        message="当日暂无可导出的解析事件",
                        code=APIConstants.ERROR_CODES["NOT_FOUND"],
                        http_status=404,
                    ),
                    404,
                )

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "涨停日期",
                    "股票代码",
                    "股票名称",
                    "连板数",
                    "是否龙头",
                    "所属行业",
                    "报告标题",
                    "上涨逻辑",
                    "风险摘要",
                    "事件ID",
                    "事件名称",
                    "事件时间",
                    "事件范围",
                    "事件类型",
                    "范围说明",
                    "事件内容",
                    "来源平台",
                    "来源链接",
                    "影响个股",
                    "影响行业",
                    "影响主题",
                ]
            )
            writer.writerows(rows)
            resp = make_response("\ufeff" + output.getvalue())
            resp.headers["Content-Type"] = "text/csv; charset=utf-8"
            resp.headers["Content-Disposition"] = f"attachment; filename=limit_up_events_{trade_date}.csv"
            return resp
        except ValueError as exc:
            return (
                APIResponse.error(
                    message=str(exc),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )


@limit_up_ns.route("/import")
class LimitUpImport(Resource):
    def post(self):
        """CSV批量导入"""
        import csv
        import io
        from datetime import datetime

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

        filename = (file.filename or "limit_up.csv").strip() or "limit_up.csv"
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
            text = raw.decode("utf-8-sig")
        except Exception:
            return (
                APIResponse.error(
                    message="CSV 文件必须为 UTF-8 编码",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )

        reader = csv.DictReader(io.StringIO(text))
        required_fields = ["stock_code", "stock_name", "limit_up_date"]
        if not reader.fieldnames:
            return (
                APIResponse.error(
                    message="CSV 文件无表头",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )

        missing = [f for f in required_fields if f not in reader.fieldnames]
        if missing:
            return (
                APIResponse.error(
                    message=f"CSV 表头缺失字段: {', '.join(missing)}",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )

        created = 0
        updated = 0
        errors = []
        total = 0

        for idx, row in enumerate(reader, start=2):
            total += 1
            try:
                payload = {
                    "stock_code": (row.get("stock_code") or "").strip(),
                    "stock_name": (row.get("stock_name") or "").strip(),
                    "limit_up_date": (row.get("limit_up_date") or "").strip(),
                    "consecutive_days": int(row.get("consecutive_days") or 1),
                    "seal_amount": float(row.get("seal_amount") or 0),
                    "first_limit_time": (row.get("first_limit_time") or "").strip() or None,
                    "open_count": int(row.get("open_count") or 0),
                    "industry": (row.get("industry") or "").strip() or None,
                    "concept_tags": [s.strip() for s in (row.get("concept_tags") or "").replace("|", ",").replace(";", ",").split(",") if s.strip()],
                    "institution_net_buy": float(row.get("institution_net_buy") or 0),
                    "hot_money_net_buy": float(row.get("hot_money_net_buy") or 0),
                    "reason_detail": (row.get("reason_detail") or "").strip() or None,
                }

                LimitUpService.create_limit_up(payload)
                created += 1
            except ValueError as e:
                errors.append({"row": idx, "error": str(e), "stock_code": row.get("stock_code", "")})
            except Exception as e:
                errors.append({"row": idx, "error": str(e), "stock_code": row.get("stock_code", "")})

        return APIResponse.success(
            {
                "total": total,
                "created": created,
                "updated": updated,
                "failed": len(errors),
                "errors": errors[:100],
            },
            message="导入完成",
        )


@limit_up_ns.route("/sync-tushare")
class SyncTushare(Resource):
    @limit_up_ns.param("date", "交易日期 YYYY-MM-DD", required=True)
    def post(self):
        """从 Tushare 同步涨停数据"""
        from app.services.tushare_sync_service import TushareSyncService
        
        args = request.args
        trade_date = parse_date(args.get("date"), required=True)
        
        try:
            result = TushareSyncService.sync_limit_up(trade_date)
            return APIResponse.success(result, message=f"同步完成: 新增 {result['created']} 条，更新 {result['updated']} 条")
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"同步失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@limit_up_ns.route("/sync-full")
class SyncFullTushare(Resource):
    @limit_up_ns.param("date", "交易日期 YYYY-MM-DD", required=True)
    def post(self):
        """完整同步（涨停+龙虎榜+概念板块+龙头识别）"""
        from app.services.tushare_enhanced_service import TushareEnhancedService
        
        args = request.args
        trade_date = args.get("date")
        
        if not trade_date:
            return (
                APIResponse.error(
                    message="date 参数必填",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        try:
            result = TushareEnhancedService.sync_limit_up_full(trade_date)
            return APIResponse.success(result, message=f"完整同步完成")
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"同步失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@limit_up_ns.route("/sync-range")
class SyncDateRange(Resource):
    @limit_up_ns.param("start_date", "开始日期 YYYY-MM-DD", required=True)
    @limit_up_ns.param("end_date", "结束日期 YYYY-MM-DD", required=True)
    def post(self):
        """批量同步日期范围"""
        from app.services.tushare_enhanced_service import TushareEnhancedService
        
        args = request.args
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        
        if not start_date or not end_date:
            return (
                APIResponse.error(
                    message="start_date 和 end_date 参数必填",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        try:
            result = TushareEnhancedService.sync_date_range(start_date, end_date)
            return APIResponse.success(result, message=f"批量同步完成")
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"同步失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@limit_up_ns.route("/hot-concepts")
class HotConcepts(Resource):
    @limit_up_ns.param("date", "交易日期 YYYY-MM-DD", required=True)
    def get(self):
        """获取热门概念板块"""
        from app.services.tushare_enhanced_service import TushareEnhancedService
        
        args = request.args
        trade_date = args.get("date")
        
        if not trade_date:
            return (
                APIResponse.error(
                    message="date 参数必填",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        try:
            concepts = TushareEnhancedService.get_hot_concepts(trade_date)
            return APIResponse.success(concepts)
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"查询失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@limit_up_ns.route("/stock-concepts/<stock_code>")
class StockConcepts(Resource):
    def get(self, stock_code: str):
        """获取股票所属概念"""
        from app.services.tushare_enhanced_service import TushareEnhancedService
        
        try:
            concepts = TushareEnhancedService.get_stock_concepts(stock_code)
            return APIResponse.success(concepts)
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"查询失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@limit_up_ns.route("/identify-dragon")
class IdentifyDragon(Resource):
    @limit_up_ns.param("date", "交易日期 YYYY-MM-DD", required=True)
    def post(self):
        """重新识别龙头股"""
        from app.services.tushare_enhanced_service import TushareEnhancedService
        from datetime import datetime
        
        args = request.args
        trade_date = args.get("date")
        
        if not trade_date:
            return (
                APIResponse.error(
                    message="date 参数必填",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        try:
            date_obj = datetime.strptime(trade_date, '%Y-%m-%d').date()
            result = TushareEnhancedService._auto_identify_dragon(date_obj)
            return APIResponse.success(result, message=f"识别到 {result['count']} 只龙头股")
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"识别失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@limit_up_ns.route("/<int:limit_up_id>/kline")
class LimitUpKline(Resource):
    @limit_up_ns.param("days", "查询天数", type=int, default=60)
    @limit_up_ns.param("date", "涨停日期 YYYY-MM-DD（分区表需要）")
    def get(self, limit_up_id: int):
        """获取涨停股近N日K线数据"""
        from datetime import datetime, timedelta
        
        # 获取涨停日期参数（分区表复合主键需要）
        limit_up_date_param = request.args.get('date')
        
        # 获取涨停股信息
        item = LimitUpService.get_limit_up(limit_up_id, limit_up_date_param)
        if not item:
            return (
                APIResponse.error(
                    message="涨停记录不存在",
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        
        stock_code = item['stock_code']
        limit_up_date = item['limit_up_date']
        days = parse_int(request.args.get('days'), default=60, minimum=1, maximum=120)
        
        # 计算日期范围
        end_date = datetime.strptime(limit_up_date, '%Y-%m-%d')
        start_date = end_date - timedelta(days=days + 30)  # 多取一些以确保足够交易日
        
        try:
            pro = get_tushare_pro()
            
            # 获取日K线
            df = pro.daily(
                ts_code=stock_code,
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d')
            )
            
            if df is None or df.empty:
                return APIResponse.success([], message="无K线数据")
            
            # 获取换手率数据
            df_basic = pro.daily_basic(
                ts_code=stock_code,
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d'),
                fields='trade_date,turnover_rate'
            )
            
            # 合并换手率数据
            turnover_map = {}
            if df_basic is not None and not df_basic.empty:
                for _, row in df_basic.iterrows():
                    turnover_map[row['trade_date']] = float(row['turnover_rate']) if row['turnover_rate'] else 0
            
            # 转换为前端需要的格式
            kline_data = []
            for _, row in df.sort_values('trade_date').iterrows():
                trade_date = row['trade_date']
                kline_data.append({
                    'date': trade_date,
                    'open': float(row['open']) if row['open'] else 0,
                    'high': float(row['high']) if row['high'] else 0,
                    'low': float(row['low']) if row['low'] else 0,
                    'close': float(row['close']) if row['close'] else 0,
                    'volume': float(row['vol']) if row['vol'] else 0,
                    'amount': float(row['amount']) if row['amount'] else 0,
                    'pct_chg': float(row['pct_chg']) if row['pct_chg'] else 0,
                    'turnover_rate': turnover_map.get(trade_date, 0)
                })
            
            return APIResponse.success({
                'stock_code': stock_code,
                'stock_name': item['stock_name'],
                'limit_up_date': limit_up_date,
                'kline': kline_data[-days:]  # 返回最近N天
            })
            
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"获取K线数据失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@limit_up_ns.route("/<int:limit_up_id>/intraday")
class LimitUpIntraday(Resource):
    @limit_up_ns.param("date", "涨停日期 YYYY-MM-DD（分区表需要）")
    def get(self, limit_up_id: int):
        """获取涨停股当日分时线数据"""
        from datetime import datetime
        
        # 获取涨停日期参数（分区表复合主键需要）
        limit_up_date_param = request.args.get('date')
        
        # 获取涨停股信息
        item = LimitUpService.get_limit_up(limit_up_id, limit_up_date_param)
        if not item:
            return (
                APIResponse.error(
                    message="涨停记录不存在",
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        
        stock_code = item['stock_code']
        limit_up_date = item['limit_up_date']
        date_str = limit_up_date.replace('-', '')
        
        try:
            pro = get_tushare_pro()
            
            # 获取分钟线数据（需要专业版权限，如果失败返回模拟结构）
            try:
                df = pro.stk_mins(ts_code=stock_code, start_date=date_str + '0930', end_date=date_str + '1500', freq='1min')
            except Exception as e:
                # 权限不足时返回空数据
                error_msg = str(e)
                if '最多访问' in error_msg or '权限' in error_msg:
                    return APIResponse.success({
                        'stock_code': stock_code,
                        'stock_name': item['stock_name'],
                        'limit_up_date': limit_up_date,
                        'intraday': [],
                        'limit_up_price': None,
                        'message': '分时数据需要 Tushare 专业版权限'
                    })
                raise
            
            if df is None or df.empty:
                return APIResponse.success({
                    'stock_code': stock_code,
                    'stock_name': item['stock_name'],
                    'limit_up_date': limit_up_date,
                    'intraday': [],
                    'limit_up_price': None,
                    'message': '暂无分时数据'
                })
            
            # 获取涨停价
            daily_df = pro.daily(ts_code=stock_code, start_date=date_str, end_date=date_str)
            limit_up_price = None
            if daily_df is not None and not daily_df.empty:
                close_price = float(daily_df.iloc[0]['close'])
                pct_chg = float(daily_df.iloc[0]['pct_chg'])
                if pct_chg >= 9.5:
                    limit_up_price = close_price
            
            # 转换分时数据
            intraday_data = []
            for _, row in df.sort_values('time').iterrows():
                intraday_data.append({
                    'time': row['time'],
                    'price': float(row['close']) if row['close'] else 0,
                    'volume': float(row['vol']) if row['vol'] else 0,
                    'amount': float(row['amount']) if row['amount'] else 0,
                })
            
            return APIResponse.success({
                'stock_code': stock_code,
                'stock_name': item['stock_name'],
                'limit_up_date': limit_up_date,
                'intraday': intraday_data,
                'limit_up_price': limit_up_price
            })
            
        except Exception as e:
            # 权限错误返回友好提示，而不是500错误
            error_msg = str(e)
            if '最多访问' in error_msg or '权限' in error_msg:
                return APIResponse.success({
                    'stock_code': stock_code,
                    'stock_name': item['stock_name'],
                    'limit_up_date': limit_up_date,
                    'intraday': [],
                    'limit_up_price': None,
                    'message': '分时数据需要 Tushare 专业版权限'
                })
            return (
                APIResponse.error(
                    message=f"获取分时数据失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )

# ============================================================================
# 涨停股分析接口
# ============================================================================

@limit_up_ns.route("/analyze")
class AnalyzeLimitUp(Resource):
    @limit_up_ns.param("stock_code", "股票代码", required=True)
    @limit_up_ns.param("date", "分析日期 YYYY-MM-DD", required=True)
    @limit_up_ns.param("force", "强制重新分析", type=bool, default=False)
    def post(self):
        """分析涨停股票（从 MinIO 导入现有 Markdown 报告）"""
        from app.services.limit_up_analysis_service import LimitUpAnalysisService
        
        args = request.args
        stock_code = args.get("stock_code")
        date_str = args.get("date")
        force = args.get("force", "false").lower() == "true"
        
        if not stock_code or not date_str:
            return (
                APIResponse.error(
                    message="stock_code 和 date 参数必填",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        try:
            from datetime import datetime
            analysis_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return (
                APIResponse.error(
                    message="日期格式错误，应为 YYYY-MM-DD",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        try:
            result = LimitUpAnalysisService.analyze_stock(stock_code, analysis_date, force)
            
            if result.get("status") == "error":
                return (
                    APIResponse.error(
                        message=result.get("message", "分析失败"),
                        code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                        http_status=400,
                    ),
                    400,
                )
            
            return APIResponse.success(
                result.get("data"),
                message=result.get("message", "分析完成")
            )
            
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"分析失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@limit_up_ns.route("/analysis/<string:stock_code>")
class GetLimitUpAnalysis(Resource):
    @limit_up_ns.param("date", "分析日期 YYYY-MM-DD", required=True)
    def get(self, stock_code: str):
        """获取涨停股分析结果"""
        from app.services.limit_up_analysis_service import LimitUpAnalysisService
        
        args = request.args
        date_str = args.get("date")
        
        if not date_str:
            return (
                APIResponse.error(
                    message="date 参数必填",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        try:
            from datetime import datetime
            analysis_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return (
                APIResponse.error(
                    message="日期格式错误，应为 YYYY-MM-DD",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        result = LimitUpAnalysisService.get_analysis(stock_code, analysis_date)
        
        if not result:
            return (
                APIResponse.error(
                    message="未找到分析记录，请先执行分析",
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        
        return APIResponse.success(result)


@limit_up_ns.route("/analysis/id/<int:analysis_id>")
class GetLimitUpAnalysisById(Resource):
    def get(self, analysis_id: int):
        """根据ID获取分析结果"""
        from app.services.limit_up_analysis_service import LimitUpAnalysisService
        
        result = LimitUpAnalysisService.get_analysis_by_id(analysis_id)
        
        if not result:
            return (
                APIResponse.error(
                    message="分析记录不存在",
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        
        return APIResponse.success(result)


# ============================================================================
# 兼容路由（前端旧路径兼容）
# ============================================================================

@limit_up_ns.route("/analyze")
class AnalyzeLimitUpCompat(Resource):
    """兼容旧的前端 API 路径"""
    @limit_up_ns.param("stock_code", "股票代码", required=True)
    @limit_up_ns.param("date", "分析日期 YYYY-MM-DD", required=True)
    @limit_up_ns.param("force", "强制重新分析", type=bool, default=False)
    def post(self):
        """分析涨停股票（兼容路由）"""
        from app.services.limit_up_analysis_service import LimitUpAnalysisService
        
        args = request.args
        stock_code = args.get("stock_code")
        date_str = args.get("date")
        force = args.get("force", "false").lower() == "true"
        
        if not stock_code or not date_str:
            return (
                APIResponse.error(
                    message="stock_code 和 date 参数必填",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        try:
            from datetime import datetime
            analysis_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return (
                APIResponse.error(
                    message="日期格式错误，应为 YYYY-MM-DD",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        try:
            result = LimitUpAnalysisService.analyze_stock(stock_code, analysis_date, force)
            
            if result.get("status") == "error":
                return (
                    APIResponse.error(
                        message=result.get("message", "分析失败"),
                        code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                        http_status=400,
                    ),
                    400,
                )
            
            return APIResponse.success(
                result.get("data"),
                message=result.get("message", "分析完成")
            )
            
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"分析失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@limit_up_ns.route("/analysis/<string:stock_code>")
class GetLimitUpAnalysisCompat(Resource):
    """获取分析结果（兼容路由）"""
    @limit_up_ns.param("date", "分析日期 YYYY-MM-DD", required=True)
    def get(self, stock_code: str):
        """获取涨停股分析结果"""
        from app.services.limit_up_analysis_service import LimitUpAnalysisService
        
        args = request.args
        date_str = args.get("date")
        
        if not date_str:
            return (
                APIResponse.error(
                    message="date 参数必填",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        try:
            from datetime import datetime
            analysis_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return (
                APIResponse.error(
                    message="日期格式错误，应为 YYYY-MM-DD",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        
        result = LimitUpAnalysisService.get_analysis(stock_code, analysis_date)
        
        if not result:
            return (
                APIResponse.error(
                    message="未找到分析记录，请先执行分析",
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        
        return APIResponse.success(result)
