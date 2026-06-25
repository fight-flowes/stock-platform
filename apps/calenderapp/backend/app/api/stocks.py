from flask import make_response, request
from flask_restx import Namespace, Resource, fields

from app.api.params import parse_bool, parse_int
from app.services.csv_import_service import CsvImportService
from app.services.stocks_service import StocksService
from config.api_config import APIConstants, APIResponse
from app.config import get_tushare_pro


stocks_ns = Namespace("stocks", description="股票信息")

stock_model = stocks_ns.model(
    "Stock",
    {
        "id": fields.Integer(readonly=True),
        "code": fields.String(required=True),
        "name": fields.String(required=True),
        "exchange": fields.String,
    },
)


def _parse_int_list_param(raw: str | None) -> list[int]:
    if raw is None or str(raw).strip() == "":
        return []
    result: list[int] = []
    for part in str(raw).split(","):
        text = part.strip()
        if not text:
            continue
        result.append(int(text))
    return result


@stocks_ns.route("/")
class Stocks(Resource):
    @stocks_ns.param("page", "页码", type=int, default=APIConstants.DEFAULT_PAGE)
    @stocks_ns.param("page_size", "每页数量", type=int, default=APIConstants.DEFAULT_PAGE_SIZE)
    @stocks_ns.param("exchange", "交易所筛选")
    @stocks_ns.param("is_favorite", "仅返回收藏 / 仅返回未收藏，true / false")
    @stocks_ns.param("group_id", "按单个分组筛选", type=int)
    @stocks_ns.param("tag_ids", "按标签筛选，逗号分隔")
    @stocks_ns.param("ungrouped_only", "仅显示未分组股票，true / false")
    def get(self):
        args = request.args
        page = parse_int(args.get("page"), default=APIConstants.DEFAULT_PAGE, minimum=1)
        page_size = parse_int(
            args.get("page_size"),
            default=APIConstants.DEFAULT_PAGE_SIZE,
            minimum=1,
            maximum=APIConstants.MAX_PAGE_SIZE,
        )
        exchange = args.get("exchange")

        # ``is_favorite`` is intentionally tri-valued — None means "no filter",
        # True/False discriminate. Strings 'true'/'false'/'1'/'0' are accepted
        # so query-string callers don't have to canonicalise.
        raw_fav = args.get("is_favorite")
        is_favorite: bool | None
        if raw_fav is None or raw_fav == "":
            is_favorite = None
        elif str(raw_fav).strip().lower() in {"true", "1", "yes"}:
            is_favorite = True
        elif str(raw_fav).strip().lower() in {"false", "0", "no"}:
            is_favorite = False
        else:
            is_favorite = None
        group_id = parse_int(args.get("group_id"), default=None, minimum=1) if args.get("group_id") not in (None, "") else None
        tag_ids = _parse_int_list_param(args.get("tag_ids"))
        ungrouped_only = parse_bool(args.get("ungrouped_only"), default=False)

        result = StocksService.list_stocks(
            page=page,
            page_size=page_size,
            exchange=exchange,
            is_favorite=is_favorite,
            group_id=group_id,
            tag_ids=tag_ids,
            ungrouped_only=ungrouped_only,
        )
        return APIResponse.paginated(data=result["items"], total=result["total"], page=page, page_size=page_size)

    @stocks_ns.expect(stock_model, validate=False)
    def post(self):
        try:
            payload = request.get_json(force=True, silent=True) or {}
            created = StocksService.upsert_stock(
                code=payload.get("code"),
                name=payload.get("name"),
                exchange=payload.get("exchange"),
            )
            return APIResponse.success(created, message="创建/更新成功"), 201
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )


@stocks_ns.route("/<string:code>")
class StockByCode(Resource):
    def get(self, code: str):
        stock = StocksService.get_by_code(code)
        if not stock:
            return (
                APIResponse.error(
                    message="股票不存在",
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        return APIResponse.success(stock)


@stocks_ns.route("/favorites")
class StockFavorites(Resource):
    def get(self):
        """获取收藏股票列表"""
        try:
            favorites = StocksService.list_favorites()
            return APIResponse.success(favorites)
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"获取收藏列表失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@stocks_ns.route("/<string:code>")
class StockByCode(Resource):
    def get(self, code: str):
        stock = StocksService.get_by_code(code)
        if not stock:
            return (
                APIResponse.error(
                    message="股票不存在",
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        return APIResponse.success(stock)

    def delete(self, code: str):
        """删除股票"""
        try:
            result = StocksService.delete_stock(code)
            return APIResponse.success(result, message="删除成功")
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"删除失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@stocks_ns.route("/cache/update")
class StockCacheUpdate(Resource):
    @stocks_ns.param("codes", "股票代码列表，逗号分隔（可选，为空则更新所有）")
    def post(self):
        """更新行情缓存（并发执行）"""
        codes_str = request.args.get("codes", "")
        codes = [c.strip() for c in codes_str.split(",") if c.strip()] if codes_str else None
        
        try:
            result = StocksService.update_quotes_cache(codes=codes, max_workers=5)
            return APIResponse.success(result, message=f"更新完成: {result['updated']}条成功")
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"更新缓存失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@stocks_ns.route("/<string:code>/favorite")
class StockFavorite(Resource):
    def post(self, code: str):
        """切换收藏状态"""
        try:
            result = StocksService.toggle_favorite(code)
            action = "已收藏" if result["is_favorite"] else "已取消收藏"
            return APIResponse.success(result, message=action)
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"操作失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@stocks_ns.route("/<string:code>/organizer")
class StockOrganizer(Resource):
    def get(self, code: str):
        try:
            result = StocksService.get_organizer(code)
            return APIResponse.success(result)
        except ValueError as e:
            return (
                APIResponse.error(
                    message=str(e),
                    code=APIConstants.ERROR_CODES["NOT_FOUND"],
                    http_status=404,
                ),
                404,
            )

    def put(self, code: str):
        payload = request.get_json(force=True, silent=True) or {}
        group_ids = payload.get("group_ids") or []
        tag_ids = payload.get("tag_ids") or []
        if not isinstance(group_ids, list) or not isinstance(tag_ids, list):
            return (
                APIResponse.error(
                    message="group_ids 和 tag_ids 必须为数组",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        try:
            result = StocksService.update_organizer(code, group_ids=group_ids, tag_ids=tag_ids)
            return APIResponse.success(result, message="更新成功")
        except ValueError as e:
            message = str(e)
            status = 404 if "不存在" in message else 400
            error_code = APIConstants.ERROR_CODES["NOT_FOUND"] if status == 404 else APIConstants.ERROR_CODES["VALIDATION_ERROR"]
            return (
                APIResponse.error(
                    message=message,
                    code=error_code,
                    http_status=status,
                ),
                status,
            )


@stocks_ns.route("/<string:code>/note")
class StockNoteByCode(Resource):
    def put(self, code: str):
        payload = request.get_json(force=True, silent=True) or {}
        if "note" not in payload:
            return (
                APIResponse.error(
                    message="缺少 note 字段",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=400,
                ),
                400,
            )
        try:
            result = StocksService.update_note(code, payload.get("note"))
            return APIResponse.success(result, message="备注已更新")
        except ValueError as e:
            message = str(e)
            status = 404 if "不存在" in message else 400
            error_code = APIConstants.ERROR_CODES["NOT_FOUND"] if status == 404 else APIConstants.ERROR_CODES["VALIDATION_ERROR"]
            return (
                APIResponse.error(
                    message=message,
                    code=error_code,
                    http_status=status,
                ),
                status,
            )


@stocks_ns.route("/realtime")
class StocksRealtime(Resource):
    @stocks_ns.param("codes", "股票代码列表，逗号分隔", required=True)
    def get(self):
        """批量获取股票实时行情"""
        codes_str = request.args.get("codes", "")
        codes = [c.strip() for c in codes_str.split(",") if c.strip()]
        
        if not codes:
            return APIResponse.success({})
        
        # 限制最多50个股票
        codes = codes[:50]
        
        try:
            quotes = StocksService.get_realtime_quotes(codes)
            return APIResponse.success(quotes)
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"获取行情数据失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


def _format_ts_code(code: str) -> str:
    """格式化股票代码为Tushare格式"""
    if '.' in code:
        return code
    if code.startswith('6'):
        return f"{code}.SH"
    elif code.startswith('0') or code.startswith('3'):
        return f"{code}.SZ"
    elif code.startswith('68'):
        return f"{code}.SH"  # 科创板
    elif code.startswith('30'):
        return f"{code}.SZ"  # 创业板
    else:
        return f"{code}.SH"


@stocks_ns.route("/<string:code>/kline")
class StockKline(Resource):
    @stocks_ns.param("days", "查询天数", type=int, default=60)
    def get(self, code: str):
        """获取股票近N日K线数据"""
        from datetime import datetime, timedelta
        
        ts_code = _format_ts_code(code)
        days = parse_int(request.args.get('days'), default=60, minimum=1, maximum=120)
        
        # 计算日期范围（截止今日）
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 30)
        
        try:
            pro = get_tushare_pro()
            
            df = pro.daily(
                ts_code=ts_code,
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d')
            )
            
            if df is None or df.empty:
                return APIResponse.success([], message="无K线数据")
            
            df_basic = pro.daily_basic(
                ts_code=ts_code,
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d'),
                fields='trade_date,turnover_rate,total_mv,circ_mv'
            )
            
            turnover_map = {}
            mv_map = {}
            if df_basic is not None and not df_basic.empty:
                for _, row in df_basic.iterrows():
                    trade_date = str(row['trade_date'])  # 确保 trade_date 是字符串
                    turnover_map[trade_date] = float(row['turnover_rate']) if row['turnover_rate'] else 0
                    mv_map[trade_date] = {
                        'total_mv': float(row['total_mv']) if row['total_mv'] else 0,
                        'circ_mv': float(row['circ_mv']) if row['circ_mv'] else 0
                    }
            
            kline_data = []
            for _, row in df.sort_values('trade_date').iterrows():
                trade_date = str(row['trade_date'])  # 确保 trade_date 是字符串
                kline_data.append({
                    'date': trade_date,
                    'open': float(row['open']) if row['open'] else 0,
                    'high': float(row['high']) if row['high'] else 0,
                    'low': float(row['low']) if row['low'] else 0,
                    'close': float(row['close']) if row['close'] else 0,
                    'volume': float(row['vol']) if row['vol'] else 0,
                    'amount': float(row['amount']) if row['amount'] else 0,
                    'pct_chg': float(row['pct_chg']) if row['pct_chg'] else 0,
                    'turnover_rate': turnover_map.get(trade_date, 0),
                    'total_mv': mv_map.get(trade_date, {}).get('total_mv', 0),
                    'circ_mv': mv_map.get(trade_date, {}).get('circ_mv', 0)
                })
            
            return APIResponse.success({
                'stock_code': ts_code,
                'kline': kline_data[-days:]
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


@stocks_ns.route("/<string:code>/info")
class StockInfo(Resource):
    def get(self, code: str):
        """获取股票公司基本信息"""
        import pandas as pd
        
        ts_code = _format_ts_code(code)
        
        def _safe_get(row, key):
            """安全获取值，处理NaN和int64"""
            import numpy as np
            val = row.get(key) if key in row.index else None
            if pd.isna(val) or val is None:
                return None
            # 处理numpy int64/float64类型
            if isinstance(val, (np.integer, pd.Int64Dtype)):
                return int(val)
            if isinstance(val, (np.floating, pd.Float64Dtype)):
                return float(val)
            return str(val) if isinstance(val, str) else val
        
        try:
            pro = get_tushare_pro()
            
            # 获取公司基本信息
            df_basic = pro.stock_company(ts_code=ts_code, fields=[
                'ts_code', 'exchange', 'chairman', 'manager', 'secretary',
                'setup_date', 'list_date', 'province', 'city', 'introduction',
                'website', 'employees', 'main_business', 'business_scope'
            ])
            
            # 获取股票基本信息（行业、市场类型）
            df_stock = pro.stock_basic(ts_code=ts_code, fields=[
                'ts_code', 'symbol', 'name', 'area', 'industry', 'market',
                'list_date', 'is_hs', 'fullname'
            ])
            
            result = {
                'ts_code': ts_code,
                'name': None,
                'fullname': None,
                'industry': None,
                'market': None,
                'area': None,
                'list_date': None,
                'setup_date': None,
                'chairman': None,
                'manager': None,
                'secretary': None,
                'province': None,
                'city': None,
                'employees': None,
                'website': None,
                'main_business': None,
                'business_scope': None,
                'introduction': None,
                'is_hs': None
            }
            
            if df_stock is not None and not df_stock.empty:
                row = df_stock.iloc[0]
                result['name'] = _safe_get(row, 'name')
                result['fullname'] = _safe_get(row, 'fullname')
                result['industry'] = _safe_get(row, 'industry')
                result['market'] = _safe_get(row, 'market')
                result['area'] = _safe_get(row, 'area')
                result['list_date'] = _safe_get(row, 'list_date')
                result['is_hs'] = _safe_get(row, 'is_hs')
            
            if df_basic is not None and not df_basic.empty:
                row = df_basic.iloc[0]
                result['setup_date'] = _safe_get(row, 'setup_date')
                result['chairman'] = _safe_get(row, 'chairman')
                result['manager'] = _safe_get(row, 'manager')
                result['secretary'] = _safe_get(row, 'secretary')
                result['province'] = _safe_get(row, 'province')
                result['city'] = _safe_get(row, 'city')
                result['employees'] = _safe_get(row, 'employees')
                result['website'] = _safe_get(row, 'website')
                result['main_business'] = _safe_get(row, 'main_business')
                result['business_scope'] = _safe_get(row, 'business_scope')
                result['introduction'] = _safe_get(row, 'introduction')
            
            return APIResponse.success(result)
            
        except Exception as e:
            return (
                APIResponse.error(
                    message=f"获取公司信息失败: {str(e)}",
                    code=APIConstants.ERROR_CODES["INTERNAL_ERROR"],
                    http_status=500,
                ),
                500,
            )


@stocks_ns.route("/search")
class StockSearch(Resource):
    @stocks_ns.param("q", "搜索关键词", required=True)
    @stocks_ns.param("limit", "返回数量", type=int, default=10)
    def get(self):
        args = request.args
        q = args.get("q") or ""
        limit = parse_int(args.get("limit"), default=10, minimum=1, maximum=100)
        items = StocksService.search(q, limit=limit)
        return APIResponse.success(items)


@stocks_ns.route("/template.csv")
class StocksTemplate(Resource):
    def get(self):
        csv_text = CsvImportService.stocks_template_csv()
        resp = make_response(csv_text)
        resp.headers["Content-Type"] = "text/csv; charset=utf-8"
        resp.headers["Content-Disposition"] = "attachment; filename=stocks_template.csv"
        return resp


@stocks_ns.route("/import")
class StocksImport(Resource):
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
        filename = (file.filename or "stocks.csv").strip() or "stocks.csv"
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
        if len(raw) > 2 * 1024 * 1024:
            return (
                APIResponse.error(
                    message="文件过大",
                    code=APIConstants.ERROR_CODES["VALIDATION_ERROR"],
                    http_status=413,
                ),
                413,
            )
        try:
            result = CsvImportService.import_stocks_csv(raw, filename=filename)
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
