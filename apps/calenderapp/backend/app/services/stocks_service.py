from datetime import date, datetime, timedelta
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import aliased

from app.db import session_scope
from app.models.limit_up_stock import LimitUpStock
from app.models.stock import Stock
from app.config import get_tushare_pro


def _format_ts_code(code: str) -> str:
    """格式化股票代码为Tushare格式"""
    if '.' in code:
        return code
    if code.startswith('6'):
        return f"{code}.SH"
    elif code.startswith('0') or code.startswith('3'):
        return f"{code}.SZ"
    elif code.startswith('68'):
        return f"{code}.SH"
    else:
        return f"{code}.SH"


# 简单的内存缓存
_quotes_cache = {}
_cache_lock = threading.Lock()
_cache_time = None


class StocksService:
    @staticmethod
    def upsert_stock(code: str, name: str, exchange: Optional[str] = None):
        code = (code or "").strip()
        name = (name or "").strip()
        exchange = (exchange or "").strip() or None
        if not code or not name:
            raise ValueError("code 和 name 不能为空")

        with session_scope() as session:
            existing = session.execute(select(Stock).where(Stock.code == code)).scalars().first()
            if existing:
                existing.name = name
                existing.exchange = exchange
                session.flush()
                return existing.to_dict()

            stock = Stock(code=code, name=name, exchange=exchange)
            session.add(stock)
            session.flush()
            return stock.to_dict()

    @staticmethod
    def toggle_favorite(code: str):
        """切换收藏状态"""
        code = (code or "").strip()
        if not code:
            raise ValueError("code 不能为空")
        
        with session_scope() as session:
            stock = session.execute(select(Stock).where(Stock.code == code)).scalars().first()
            if not stock:
                raise ValueError("股票不存在")
            
            stock.is_favorite = not stock.is_favorite
            session.flush()
            return stock.to_dict()

    @staticmethod
    def delete_stock(code: str):
        """删除股票"""
        code = (code or "").strip()
        if not code:
            raise ValueError("code 不能为空")
        
        with session_scope() as session:
            stock = session.execute(select(Stock).where(Stock.code == code)).scalars().first()
            if not stock:
                raise ValueError("股票不存在")
            
            session.delete(stock)
            session.flush()
            return {"code": code, "deleted": True}

    @staticmethod
    def list_favorites():
        """获取收藏股票列表"""
        with session_scope() as session:
            stocks = session.execute(
                select(Stock).where(Stock.is_favorite == True).order_by(Stock.id.desc())
            ).scalars().all()
            return [s.to_dict() for s in stocks]

    @staticmethod
    def get_by_code(code: str):
        code = (code or "").strip()
        if not code:
            return None
        with session_scope() as session:
            stock = session.execute(select(Stock).where(Stock.code == code)).scalars().first()
            return stock.to_dict() if stock else None

    @staticmethod
    def search(query: str, limit: int = 10):
        query = (query or "").strip()
        if not query:
            return []
        limit = min(max(int(limit), 1), 50)
        like = f"%{query}%"
        with session_scope() as session:
            items = (
                session.execute(
                    select(Stock)
                    .where(or_(Stock.code.ilike(like), Stock.name.ilike(like)))
                    .order_by(Stock.id.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [s.to_dict() for s in items]

    @staticmethod
    def list_stocks(page: int, page_size: int, exchange: Optional[str] = None):
        """
        获取股票列表，按最新涨停日期排序（涨停过的股票优先）
        """
        page = max(int(page), 1)
        page_size = max(int(page_size), 1)
        exchange = (exchange or "").strip() or None

        with session_scope() as session:
            # 先获取所有股票（带涨停统计信息）
            q = select(Stock)
            if exchange:
                q = q.where(Stock.exchange == exchange)
            
            total_q = select(func.count(Stock.id))
            if exchange:
                total_q = total_q.where(Stock.exchange == exchange)
            total = session.execute(total_q).scalar()
            
            # 获取所有股票
            all_stocks = session.execute(q).scalars().all()
            
            # 为每只股票获取涨停信息
            stock_with_limit_up = []
            for stock in all_stocks:
                stock_dict = stock.to_dict()
                
                # 查询该股票的最新涨停记录
                latest_limit_up = session.execute(
                    select(LimitUpStock)
                    .where(LimitUpStock.stock_code == stock.code)
                    .order_by(LimitUpStock.limit_up_date.desc())
                    .limit(1)
                ).scalars().first()
                
                if latest_limit_up:
                    stock_dict['latest_limit_up_date'] = str(latest_limit_up.limit_up_date)
                    stock_dict['latest_consecutive_days'] = latest_limit_up.consecutive_days
                    stock_dict['latest_strength_level'] = latest_limit_up.strength_level
                    stock_dict['latest_first_limit_time'] = str(latest_limit_up.first_limit_time) if latest_limit_up.first_limit_time else None
                    stock_dict['latest_industry'] = latest_limit_up.industry
                else:
                    stock_dict['latest_limit_up_date'] = None
                    stock_dict['latest_consecutive_days'] = None
                    stock_dict['latest_strength_level'] = None
                    stock_dict['latest_first_limit_time'] = None
                    stock_dict['latest_industry'] = None
                
                limit_up_count = session.execute(
                    select(func.count(LimitUpStock.id))
                    .where(LimitUpStock.stock_code == stock.code)
                ).scalar()
                stock_dict['limit_up_count'] = limit_up_count or 0
                
                stock_with_limit_up.append(stock_dict)
            
            # 排序：按最新涨停日期倒序（涨停过的股票优先，最新涨停排最前）
            # 分成两组：有涨停的和无涨停的
            with_limit_up = [s for s in stock_with_limit_up if s['latest_limit_up_date']]
            without_limit_up = [s for s in stock_with_limit_up if not s['latest_limit_up_date']]
            
            # 有涨停的按日期倒序 + 连板数倒序（同日期时连板高的排前面）
            with_limit_up.sort(key=lambda x: (x['latest_limit_up_date'], x['latest_consecutive_days'] or 0), reverse=True)
            
            # 无涨停的按 id 倒序
            without_limit_up.sort(key=lambda x: x['id'], reverse=True)
            
            # 合并：有涨停的排前面
            stock_with_limit_up = with_limit_up + without_limit_up
            
            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            result_items = stock_with_limit_up[start:end]
            
            return {"items": result_items, "total": total}

    @staticmethod
    def update_quotes_cache(codes: list = None, max_workers: int = 5):
        """
        并发更新股票行情缓存到数据库
        :param codes: 股票代码列表，为空则更新所有
        :param max_workers: 并发线程数
        """
        import pandas as pd
        
        # 获取需要更新的股票列表
        if codes is None:
            with session_scope() as session:
                stocks = session.execute(select(Stock.code)).scalars().all()
                codes = [s for s in stocks]
        
        if not codes:
            return {"updated": 0, "failed": 0}
        
        def fetch_single_quote(code: str):
            """获取单只股票的行情数据"""
            try:
                pro = get_tushare_pro()
                
                ts_code = _format_ts_code(code)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=10)
                
                # 获取日行情
                df = pro.daily(
                    ts_code=ts_code,
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d')
                )
                
                if df is None or df.empty:
                    return None
                
                latest = df.sort_values('trade_date', ascending=False).iloc[0]
                result = {
                    'code': code,
                    'close': float(latest['close']) if pd.notna(latest['close']) else None,
                    'pct_chg': float(latest['pct_chg']) if pd.notna(latest['pct_chg']) else None,
                    'trade_date': str(latest['trade_date'])
                }
                
                # 获取市值数据
                df_basic = pro.daily_basic(
                    ts_code=ts_code,
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                    fields='trade_date,total_mv,circ_mv,turnover_rate'
                )
                
                if df_basic is not None and not df_basic.empty:
                    latest_basic = df_basic.sort_values('trade_date', ascending=False).iloc[0]
                    result['total_mv'] = float(latest_basic['total_mv']) if pd.notna(latest_basic['total_mv']) else None
                    result['circ_mv'] = float(latest_basic['circ_mv']) if pd.notna(latest_basic['circ_mv']) else None
                    result['turnover_rate'] = float(latest_basic['turnover_rate']) if pd.notna(latest_basic['turnover_rate']) else None
                else:
                    result['total_mv'] = None
                    result['circ_mv'] = None
                    result['turnover_rate'] = None
                
                # 获取股东人数（使用更宽的日期范围）
                try:
                    df_holder = pro.stk_holdernumber(
                        ts_code=ts_code,
                        start_date=(start_date - timedelta(days=180)).strftime('%Y%m%d'),
                        end_date=end_date.strftime('%Y%m%d')
                    )
                    if df_holder is not None and not df_holder.empty:
                        latest_holder = df_holder.sort_values('ann_date', ascending=False).iloc[0]
                        result['holder_num'] = int(latest_holder['holder_num']) if pd.notna(latest_holder['holder_num']) else None
                    else:
                        result['holder_num'] = None
                except Exception as e:
                    result['holder_num'] = None
                    print(f"获取 {code} 股东人数失败: {str(e)}")
                
                return result
                
            except Exception as e:
                print(f"获取 {code} 行情失败: {str(e)}")
                return None
        
        # 并发获取
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {executor.submit(fetch_single_quote, code): code for code in codes}
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    result = future.result()
                    if result:
                        results[code] = result
                except Exception as e:
                    print(f"处理 {code} 失败: {str(e)}")
        
        # 批量更新数据库
        updated = 0
        with session_scope() as session:
            for code, data in results.items():
                try:
                    trade_date = datetime.strptime(data['trade_date'], '%Y%m%d').date() if data.get('trade_date') else None
                    session.execute(
                        update(Stock)
                        .where(Stock.code == code)
                        .values(
                            cache_close=data.get('close'),
                            cache_pct_chg=data.get('pct_chg'),
                            cache_total_mv=data.get('total_mv'),
                            cache_circ_mv=data.get('circ_mv'),
                            cache_turnover_rate=data.get('turnover_rate'),
                            cache_holder_num=data.get('holder_num'),
                            cache_trade_date=trade_date
                        )
                    )
                    updated += 1
                except Exception as e:
                    print(f"更新 {code} 缓存失败: {str(e)}")
            session.flush()
        
        return {"updated": updated, "failed": len(codes) - updated}

    @staticmethod
    def get_realtime_quotes(codes: list):
        """
        批量获取股票实时行情数据（从缓存或 Tushare）
        优先返回缓存数据，快速响应
        """
        if not codes:
            return {}
        
        result = {}
        
        # 先从数据库缓存获取
        with session_scope() as session:
            stocks = session.execute(
                select(Stock).where(Stock.code.in_(codes))
            ).scalars().all()
            
            for stock in stocks:
                pure_code = stock.code.split('.')[0] if '.' in stock.code else stock.code
                if stock.cache_close:
                    result[pure_code] = {
                        'close': stock.cache_close,
                        'pct_chg': stock.cache_pct_chg,
                        'total_mv': stock.cache_total_mv,
                        'circ_mv': stock.cache_circ_mv,
                        'turnover_rate': stock.cache_turnover_rate,
                        'trade_date': str(stock.cache_trade_date) if stock.cache_trade_date else None
                    }
        
        return result