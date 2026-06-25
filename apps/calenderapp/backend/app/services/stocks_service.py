from datetime import date, datetime, timedelta
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from sqlalchemy import func, or_, select, update

from app.db import session_scope
from app.models.limit_up_stock import LimitUpStock
from app.models.stock import Stock
from app.models.stock_note import StockNote
from app.models.stock_group import StockGroup
from app.models.stock_group_member import StockGroupMember
from app.models.stock_tag import StockTag
from app.models.stock_tag_binding import StockTagBinding
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


def _parse_int_list(values: list[int] | tuple[int, ...] | set[int] | None) -> list[int]:
    result: list[int] = []
    for value in values or []:
        try:
            result.append(int(value))
        except Exception:
            continue
    return sorted(set(result))


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
            stock.favorited_at = datetime.now() if stock.is_favorite else None
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
                select(Stock)
                .where(Stock.is_favorite == True)
                .order_by(Stock.favorited_at.desc().nullslast(), Stock.id.desc())
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
    def list_stocks(
        page: int,
        page_size: int,
        exchange: Optional[str] = None,
        is_favorite: Optional[bool] = None,
        group_id: Optional[int] = None,
        tag_ids: Optional[list[int]] = None,
        ungrouped_only: bool = False,
    ):
        """
        获取股票列表，按最新涨停日期排序（涨停过的股票优先）

        ``is_favorite`` (None | True | False) — when not None, narrows the
        result to favourited / non-favourited stocks. The new /stocks page
        treats favourites as the primary working set, so this filter lets
        the same endpoint power both the legacy "all stocks" view and the
        new "my watchlist" view without splitting handlers.
        """
        page = max(int(page), 1)
        page_size = max(int(page_size), 1)
        exchange = (exchange or "").strip() or None
        parsed_tag_ids = _parse_int_list(tag_ids)

        latest_limit_up_subquery = (
            select(
                LimitUpStock.stock_code.label("stock_code"),
                func.max(LimitUpStock.limit_up_date).label("latest_limit_up_date"),
            )
            .group_by(LimitUpStock.stock_code)
            .subquery()
        )

        with session_scope() as session:
            q = (
                select(Stock, latest_limit_up_subquery.c.latest_limit_up_date)
                .outerjoin(latest_limit_up_subquery, latest_limit_up_subquery.c.stock_code == Stock.code)
            )
            if exchange:
                q = q.where(Stock.exchange == exchange)
            if is_favorite is not None:
                q = q.where(Stock.is_favorite == bool(is_favorite))
            if group_id is not None:
                q = q.where(
                    Stock.id.in_(
                        select(StockGroupMember.stock_id).where(StockGroupMember.group_id == int(group_id))
                    )
                )
            if parsed_tag_ids:
                q = q.where(
                    Stock.id.in_(
                        select(StockTagBinding.stock_id).where(StockTagBinding.tag_id.in_(parsed_tag_ids))
                    )
                )
            if ungrouped_only:
                q = q.where(
                    ~Stock.id.in_(select(StockGroupMember.stock_id))
                )

            total_q = select(func.count()).select_from(q.with_only_columns(Stock.id).order_by(None).subquery())
            total = int(session.execute(total_q).scalar() or 0)

            if is_favorite is True:
                q = q.order_by(
                    Stock.favorited_at.desc().nullslast(),
                    Stock.id.desc(),
                )
            else:
                q = q.order_by(
                    latest_limit_up_subquery.c.latest_limit_up_date.desc().nullslast(),
                    Stock.id.desc(),
                )
            q = q.offset((page - 1) * page_size).limit(page_size)

            rows = session.execute(q).all()
            page_stocks = [row[0] for row in rows]
            latest_date_map = {
                row[0].code: str(row[1]) if row[1] else None
                for row in rows
            }

            stock_ids = [stock.id for stock in page_stocks]
            stock_codes = [stock.code for stock in page_stocks]
            group_map = StocksService._group_map_for_stock_ids(session, stock_ids)
            tag_map = StocksService._tag_map_for_stock_ids(session, stock_ids)
            note_map = StocksService._note_map_for_stock_ids(session, stock_ids)
            latest_limit_up_map = StocksService._latest_limit_up_map_for_codes(session, stock_codes)
            limit_up_count_map = StocksService._limit_up_count_map_for_codes(session, stock_codes)

            stock_with_limit_up = []
            for stock in page_stocks:
                stock_dict = stock.to_dict()

                latest_limit_up = latest_limit_up_map.get(stock.code)

                if latest_limit_up:
                    stock_dict["latest_limit_up_date"] = latest_date_map.get(stock.code) or str(latest_limit_up.limit_up_date)
                    stock_dict["latest_consecutive_days"] = latest_limit_up.consecutive_days
                    stock_dict["latest_strength_level"] = latest_limit_up.strength_level
                    stock_dict["latest_first_limit_time"] = str(latest_limit_up.first_limit_time) if latest_limit_up.first_limit_time else None
                    stock_dict["latest_industry"] = latest_limit_up.industry
                else:
                    stock_dict["latest_limit_up_date"] = None
                    stock_dict["latest_consecutive_days"] = None
                    stock_dict["latest_strength_level"] = None
                    stock_dict["latest_first_limit_time"] = None
                    stock_dict["latest_industry"] = None

                stock_dict["limit_up_count"] = int(limit_up_count_map.get(stock.code, 0))
                stock_dict["groups"] = group_map.get(stock.id, [])
                stock_dict["tags"] = tag_map.get(stock.id, [])
                stock_dict["note"] = note_map.get(stock.id, "")
                stock_with_limit_up.append(stock_dict)

            return {"items": stock_with_limit_up, "total": total}

    @staticmethod
    def _group_map_for_stock_ids(session, stock_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        if not stock_ids:
            return {}
        rows = session.execute(
            select(
                StockGroupMember.stock_id,
                StockGroup.id,
                StockGroup.name,
                StockGroup.color,
            )
            .join(StockGroup, StockGroup.id == StockGroupMember.group_id)
            .where(StockGroupMember.stock_id.in_(stock_ids))
            .order_by(StockGroup.sort_order.asc(), StockGroup.id.asc())
        ).all()

        result: dict[int, list[dict[str, Any]]] = {}
        for stock_id, group_id, name, color in rows:
            result.setdefault(int(stock_id), []).append(
                {"id": int(group_id), "name": name, "color": color}
            )
        return result

    @staticmethod
    def _tag_map_for_stock_ids(session, stock_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        if not stock_ids:
            return {}
        rows = session.execute(
            select(
                StockTagBinding.stock_id,
                StockTag.id,
                StockTag.name,
                StockTag.color,
            )
            .join(StockTag, StockTag.id == StockTagBinding.tag_id)
            .where(StockTagBinding.stock_id.in_(stock_ids))
            .order_by(StockTag.sort_order.asc(), StockTag.id.asc())
        ).all()

        result: dict[int, list[dict[str, Any]]] = {}
        for stock_id, tag_id, name, color in rows:
            result.setdefault(int(stock_id), []).append(
                {"id": int(tag_id), "name": name, "color": color}
            )
        return result

    @staticmethod
    def _note_map_for_stock_ids(session, stock_ids: list[int]) -> dict[int, str]:
        if not stock_ids:
            return {}

        rows = session.execute(
            select(StockNote.stock_id, StockNote.note).where(StockNote.stock_id.in_(stock_ids))
        ).all()
        return {int(stock_id): (note or "") for stock_id, note in rows}

    @staticmethod
    def _latest_limit_up_map_for_codes(session, stock_codes: list[str]) -> dict[str, LimitUpStock]:
        if not stock_codes:
            return {}

        ranked_subquery = (
            select(
                LimitUpStock.id.label("id"),
                LimitUpStock.stock_code.label("stock_code"),
                func.row_number().over(
                    partition_by=LimitUpStock.stock_code,
                    order_by=(LimitUpStock.limit_up_date.desc(), LimitUpStock.id.desc()),
                ).label("rn"),
            )
            .where(LimitUpStock.stock_code.in_(stock_codes))
            .subquery()
        )

        rows = session.execute(
            select(LimitUpStock)
            .join(ranked_subquery, ranked_subquery.c.id == LimitUpStock.id)
            .where(ranked_subquery.c.rn == 1)
        ).scalars().all()

        return {row.stock_code: row for row in rows}

    @staticmethod
    def _limit_up_count_map_for_codes(session, stock_codes: list[str]) -> dict[str, int]:
        if not stock_codes:
            return {}

        rows = session.execute(
            select(
                LimitUpStock.stock_code,
                func.count(LimitUpStock.id).label("limit_up_count"),
            )
            .where(LimitUpStock.stock_code.in_(stock_codes))
            .group_by(LimitUpStock.stock_code)
        ).all()

        return {str(stock_code): int(limit_up_count or 0) for stock_code, limit_up_count in rows}

    @staticmethod
    def get_organizer(code: str) -> dict[str, Any]:
        code = (code or "").strip()
        if not code:
            raise ValueError("code 不能为空")

        with session_scope() as session:
            stock = session.execute(select(Stock).where(Stock.code == code)).scalars().first()
            if not stock:
                raise ValueError("股票不存在")

            group_ids = session.execute(
                select(StockGroupMember.group_id).where(StockGroupMember.stock_id == stock.id)
            ).scalars().all()
            tag_ids = session.execute(
                select(StockTagBinding.tag_id).where(StockTagBinding.stock_id == stock.id)
            ).scalars().all()
            groups = session.execute(
                select(StockGroup).order_by(StockGroup.sort_order.asc(), StockGroup.id.asc())
            ).scalars().all()
            tags = session.execute(
                select(StockTag).order_by(StockTag.sort_order.asc(), StockTag.id.asc())
            ).scalars().all()

            return {
                "stock": {"code": stock.code, "name": stock.name},
                "group_ids": [int(item) for item in group_ids],
                "tag_ids": [int(item) for item in tag_ids],
                "available_groups": [group.to_dict() for group in groups],
                "available_tags": [tag.to_dict() for tag in tags],
            }

    @staticmethod
    def update_organizer(code: str, group_ids: list[int] | None = None, tag_ids: list[int] | None = None) -> dict[str, Any]:
        code = (code or "").strip()
        if not code:
            raise ValueError("code 不能为空")

        parsed_group_ids = _parse_int_list(group_ids)
        parsed_tag_ids = _parse_int_list(tag_ids)

        with session_scope() as session:
            stock = session.execute(select(Stock).where(Stock.code == code)).scalars().first()
            if not stock:
                raise ValueError("股票不存在")

            if parsed_group_ids:
                found_group_ids = set(
                    session.execute(select(StockGroup.id).where(StockGroup.id.in_(parsed_group_ids))).scalars().all()
                )
                missing_group_ids = [gid for gid in parsed_group_ids if gid not in found_group_ids]
                if missing_group_ids:
                    raise ValueError(f"分组不存在: {', '.join(str(item) for item in missing_group_ids)}")

            if parsed_tag_ids:
                found_tag_ids = set(
                    session.execute(select(StockTag.id).where(StockTag.id.in_(parsed_tag_ids))).scalars().all()
                )
                missing_tag_ids = [tid for tid in parsed_tag_ids if tid not in found_tag_ids]
                if missing_tag_ids:
                    raise ValueError(f"标签不存在: {', '.join(str(item) for item in missing_tag_ids)}")

            if not stock.is_favorite:
                stock.is_favorite = True
                stock.favorited_at = datetime.now()

            existing_group_rows = session.execute(
                select(StockGroupMember).where(StockGroupMember.stock_id == stock.id)
            ).scalars().all()
            existing_group_map = {row.group_id: row for row in existing_group_rows}
            for group_id in list(existing_group_map):
                if group_id not in parsed_group_ids:
                    session.delete(existing_group_map[group_id])
            for group_id in parsed_group_ids:
                if group_id not in existing_group_map:
                    session.add(StockGroupMember(group_id=group_id, stock_id=stock.id))

            existing_tag_rows = session.execute(
                select(StockTagBinding).where(StockTagBinding.stock_id == stock.id)
            ).scalars().all()
            existing_tag_map = {row.tag_id: row for row in existing_tag_rows}
            for tag_id in list(existing_tag_map):
                if tag_id not in parsed_tag_ids:
                    session.delete(existing_tag_map[tag_id])
            for tag_id in parsed_tag_ids:
                if tag_id not in existing_tag_map:
                    session.add(StockTagBinding(stock_id=stock.id, tag_id=tag_id))

            session.flush()
            return {
                "code": stock.code,
                "group_ids": parsed_group_ids,
                "tag_ids": parsed_tag_ids,
            }

    @staticmethod
    def update_note(code: str, note: str | None) -> dict[str, Any]:
        code = (code or "").strip()
        if not code:
            raise ValueError("code 不能为空")

        normalized_note = (note or "").strip()
        if len(normalized_note) > 500:
            raise ValueError("备注最多 500 个字符")

        with session_scope() as session:
            stock = session.execute(select(Stock).where(Stock.code == code)).scalars().first()
            if not stock:
                raise ValueError("股票不存在")

            stock_note = session.execute(
                select(StockNote).where(StockNote.stock_id == stock.id)
            ).scalars().first()

            if normalized_note:
                if stock_note:
                    stock_note.note = normalized_note
                else:
                    stock_note = StockNote(stock_id=stock.id, note=normalized_note)
                    session.add(stock_note)
            elif stock_note:
                session.delete(stock_note)

            session.flush()
            return {
                "code": stock.code,
                "note": normalized_note,
            }

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
