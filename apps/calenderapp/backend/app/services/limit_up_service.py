from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select

from app.db import session_scope
from app.models.limit_up_stock import LimitUpStock
from app.utils.cache import api_cache, CACHE_SHORT, CACHE_MEDIUM


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_time(value: Optional[str]) -> Optional[time]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M:%S").time()
    except ValueError:
        try:
            return datetime.strptime(value, "%H%M%S").time()
        except ValueError:
            return None


def _calculate_strength(
    first_time: Optional[time],
    consecutive_days: int,
    seal_amount: float,
    open_count: int,
    institution_net: float,
    hot_money_net: float,
) -> tuple[int, float]:
    """计算涨停强度评分"""
    # 1. 封板时间评分 (0-25分)
    if first_time:
        time_str = first_time.strftime("%H%M%S")
        if time_str < "100000":
            time_score = 25
        elif time_str < "110000":
            time_score = 20
        elif time_str < "130000":
            time_score = 15
        elif time_str < "140000":
            time_score = 10
        else:
            time_score = 5
    else:
        time_score = 10

    # 2. 连板高度评分 (0-20分)
    if consecutive_days >= 5:
        consecutive_score = 20
    elif consecutive_days >= 4:
        consecutive_score = 18
    elif consecutive_days >= 3:
        consecutive_score = 15
    elif consecutive_days >= 2:
        consecutive_score = 12
    else:
        consecutive_score = 8

    # 3. 封单金额评分 (0-20分) - 亿元为单位换算
    seal_amount_yi = seal_amount / 100000000  # 万元转亿元
    if seal_amount_yi >= 3:
        seal_score = 20
    elif seal_amount_yi >= 1:
        seal_score = 15
    elif seal_amount_yi >= 0.5:
        seal_score = 10
    elif seal_amount_yi >= 0.1:
        seal_score = 5
    else:
        seal_score = 3

    # 4. 开板次数评分 (0-15分)
    if open_count == 0:
        open_score = 15
    elif open_count == 1:
        open_score = 12
    elif open_count == 2:
        open_score = 8
    else:
        open_score = 5

    # 5. 资金动向评分 (0-20分)
    net_buy = institution_net + hot_money_net  # 万元
    if net_buy >= 100000:
        fund_score = 20
    elif net_buy >= 50000:
        fund_score = 15
    elif net_buy >= 10000:
        fund_score = 10
    elif net_buy >= 0:
        fund_score = 5
    else:
        fund_score = 0

    total_score = time_score + consecutive_score + seal_score + open_score + fund_score

    # 转换为星级 (1-5)
    if total_score >= 80:
        strength_level = 5
    elif total_score >= 60:
        strength_level = 4
    elif total_score >= 40:
        strength_level = 3
    elif total_score >= 20:
        strength_level = 2
    else:
        strength_level = 1

    return strength_level, total_score


class LimitUpService:
    @staticmethod
    def _get_limit_up_item(session, limit_up_id: int, limit_up_date: Optional[str] = None) -> Optional[LimitUpStock]:
        query = select(LimitUpStock).where(LimitUpStock.id == int(limit_up_id))
        if limit_up_date:
            query = query.where(LimitUpStock.limit_up_date == _parse_date(limit_up_date))
        else:
            query = query.order_by(LimitUpStock.limit_up_date.desc())
        return session.execute(query).scalars().first()

    @staticmethod
    def _apply_update_payload(item: LimitUpStock, payload: Dict[str, Any]) -> None:
        if "stock_code" in payload:
            stock_code = (payload.get("stock_code") or "").strip()
            if not stock_code:
                raise ValueError("stock_code 不能为空")
            item.stock_code = stock_code

        if "stock_name" in payload:
            stock_name = (payload.get("stock_name") or "").strip()
            if not stock_name:
                raise ValueError("stock_name 不能为空")
            item.stock_name = stock_name

        if "limit_up_date" in payload:
            limit_up_date = _parse_date(payload.get("limit_up_date"))
            if not limit_up_date:
                raise ValueError("limit_up_date 无效")
            item.limit_up_date = limit_up_date

        if "consecutive_days" in payload:
            item.consecutive_days = int(payload.get("consecutive_days"))

        if "limit_up_type" in payload:
            item.limit_up_type = (payload.get("limit_up_type") or "").strip()

        if "seal_amount" in payload:
            item.seal_amount = float(payload.get("seal_amount"))

        if "seal_ratio" in payload:
            item.seal_ratio = float(payload.get("seal_ratio"))

        if "turnover_rate" in payload:
            item.turnover_rate = float(payload.get("turnover_rate"))

        if "volume_ratio" in payload:
            item.volume_ratio = float(payload.get("volume_ratio")) if payload.get("volume_ratio") else None

        if "first_limit_time" in payload:
            item.first_limit_time = _parse_time(payload.get("first_limit_time"))

        if "last_limit_time" in payload:
            item.last_limit_time = _parse_time(payload.get("last_limit_time"))

        if "open_count" in payload:
            item.open_count = int(payload.get("open_count"))

        if "industry" in payload:
            item.industry = (payload.get("industry") or "").strip() or None

        if "concept_tags" in payload:
            concept_tags = payload.get("concept_tags") or []
            if isinstance(concept_tags, str):
                concept_tags = [s.strip() for s in concept_tags.split(",") if s.strip()]
            if not isinstance(concept_tags, list):
                raise ValueError("concept_tags 必须为数组或逗号分隔字符串")
            item.concept_tags = concept_tags

        if "institution_net_buy" in payload:
            item.institution_net_buy = float(payload.get("institution_net_buy"))

        if "hot_money_net_buy" in payload:
            item.hot_money_net_buy = float(payload.get("hot_money_net_buy"))

        if "north_net_buy" in payload:
            item.north_net_buy = float(payload.get("north_net_buy"))

        if "total_net_buy" in payload:
            item.total_net_buy = float(payload.get("total_net_buy"))

        if "reason_category" in payload:
            item.reason_category = (payload.get("reason_category") or "").strip() or None

        if "reason_detail" in payload:
            item.reason_detail = payload.get("reason_detail")

        if "is_dragon_head" in payload:
            item.is_dragon_head = bool(payload.get("is_dragon_head"))

        if "dragon_rank" in payload:
            item.dragon_rank = int(payload.get("dragon_rank"))

        item.strength_level, item.strength_score = _calculate_strength(
            item.first_limit_time,
            item.consecutive_days,
            item.seal_amount,
            item.open_count,
            item.institution_net_buy,
            item.hot_money_net_buy,
        )

    @staticmethod
    def get_limit_up(limit_up_id: int, limit_up_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        limit_up_id = int(limit_up_id)
        with session_scope() as session:
            item = LimitUpService._get_limit_up_item(session, limit_up_id, limit_up_date=limit_up_date)
            return item.to_dict() if item else None

    @staticmethod
    def create_limit_up(payload: Dict[str, Any]) -> Dict[str, Any]:
        stock_code = (payload.get("stock_code") or "").strip()
        stock_name = (payload.get("stock_name") or "").strip()
        limit_up_date = _parse_date(payload.get("limit_up_date"))

        if not stock_code or not stock_name or not limit_up_date:
            raise ValueError("stock_code、stock_name、limit_up_date 不能为空")

        consecutive_days = int(payload.get("consecutive_days", 1))
        limit_up_type = (payload.get("limit_up_type") or "first_board").strip()
        seal_amount = float(payload.get("seal_amount", 0))
        seal_ratio = float(payload.get("seal_ratio", 0))
        turnover_rate = float(payload.get("turnover_rate", 0))
        volume_ratio = float(payload.get("volume_ratio")) if payload.get("volume_ratio") else None

        first_limit_time = _parse_time(payload.get("first_limit_time"))
        last_limit_time = _parse_time(payload.get("last_limit_time"))
        open_count = int(payload.get("open_count", 0))

        industry = (payload.get("industry") or "").strip() or None
        concept_tags = payload.get("concept_tags") or []
        if isinstance(concept_tags, str):
            concept_tags = [s.strip() for s in concept_tags.split(",") if s.strip()]
        if not isinstance(concept_tags, list):
            raise ValueError("concept_tags 必须为数组或逗号分隔字符串")

        institution_net_buy = float(payload.get("institution_net_buy", 0))
        hot_money_net_buy = float(payload.get("hot_money_net_buy", 0))
        north_net_buy = float(payload.get("north_net_buy", 0))
        total_net_buy = float(payload.get("total_net_buy", 0))

        reason_category = (payload.get("reason_category") or "").strip() or None
        reason_detail = payload.get("reason_detail")

        source = (payload.get("source") or "manual").strip()

        # 计算强度
        strength_level, strength_score = _calculate_strength(
            first_limit_time,
            consecutive_days,
            seal_amount,
            open_count,
            institution_net_buy,
            hot_money_net_buy,
        )

        with session_scope() as session:
            item = LimitUpStock(
                stock_code=stock_code,
                stock_name=stock_name,
                limit_up_date=limit_up_date,
                consecutive_days=consecutive_days,
                limit_up_type=limit_up_type,
                seal_amount=seal_amount,
                seal_ratio=seal_ratio,
                turnover_rate=turnover_rate,
                volume_ratio=volume_ratio,
                first_limit_time=first_limit_time,
                last_limit_time=last_limit_time,
                open_count=open_count,
                industry=industry,
                concept_tags=concept_tags,
                institution_net_buy=institution_net_buy,
                hot_money_net_buy=hot_money_net_buy,
                north_net_buy=north_net_buy,
                total_net_buy=total_net_buy,
                reason_category=reason_category,
                reason_detail=reason_detail,
                strength_level=strength_level,
                strength_score=strength_score,
                is_dragon_head=False,
                dragon_rank=0,
                source=source,
            )
            session.add(item)
            session.flush()
            return item.to_dict()

    @staticmethod
    def update_limit_up(limit_up_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        limit_up_id = int(limit_up_id)
        with session_scope() as session:
            item = LimitUpService._get_limit_up_item(session, limit_up_id)
            if not item:
                return None
            LimitUpService._apply_update_payload(item, payload)
            session.flush()
            return item.to_dict()

    @staticmethod
    def batch_update_limit_ups(items: List[Dict[str, Any]], updates: Dict[str, Any]) -> Dict[str, Any]:
        if not items:
            raise ValueError("请至少选择一条涨停记录")
        if not updates:
            raise ValueError("请至少填写一个更新字段")

        updated_items = []
        with session_scope() as session:
            for item_ref in items:
                item_id = item_ref.get("id")
                limit_up_date = item_ref.get("limit_up_date")
                if not item_id or not limit_up_date:
                    raise ValueError("批量更新参数缺少 id 或 limit_up_date")

                item = LimitUpService._get_limit_up_item(session, int(item_id), limit_up_date=limit_up_date)
                if not item:
                    raise ValueError(f"未找到涨停记录: {item_id} / {limit_up_date}")

                LimitUpService._apply_update_payload(item, updates)
                updated_items.append(item)

            session.flush()

            return {
                "updated": len(updated_items),
                "items": [item.to_dict() for item in updated_items],
            }

    @staticmethod
    def delete_limit_up(limit_up_id: int) -> bool:
        limit_up_id = int(limit_up_id)
        with session_scope() as session:
            # 分区表使用复合主键，需要用 query
            item = session.execute(
                select(LimitUpStock).where(LimitUpStock.id == limit_up_id)
            ).scalars().first()
            if not item:
                return False
            session.delete(item)
            return True

    @staticmethod
    def list_limit_ups(
        page: int,
        page_size: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        consecutive_min: Optional[int] = None,
        consecutive_max: Optional[int] = None,
        close_min: Optional[float] = None,
        close_max: Optional[float] = None,
        open_count_min: Optional[int] = None,
        open_count_max: Optional[int] = None,
        industry: Optional[str] = None,
        concept: Optional[str] = None,
        strength_min: Optional[int] = None,
        strength_max: Optional[int] = None,
        is_dragon_head: Optional[bool] = None,
        limit_up_type: Optional[str] = None,
        q: Optional[str] = None,
    ):
        page = max(int(page), 1)
        page_size = max(int(page_size), 1)

        sd = _parse_date(start_date)
        ed = _parse_date(end_date)
        q = (q or "").strip() or None
        industry = (industry or "").strip() or None
        concept = (concept or "").strip() or None
        limit_up_type = (limit_up_type or "").strip() or None

        where = []
        if sd:
            where.append(LimitUpStock.limit_up_date >= sd)
        if ed:
            where.append(LimitUpStock.limit_up_date <= ed)
        if consecutive_min is not None:
            where.append(LimitUpStock.consecutive_days >= int(consecutive_min))
        if consecutive_max is not None:
            where.append(LimitUpStock.consecutive_days <= int(consecutive_max))
        if close_min is not None and str(close_min).strip() != "":
            where.append(LimitUpStock.close > float(close_min))
        if close_max is not None and str(close_max).strip() != "":
            where.append(LimitUpStock.close <= float(close_max))
        if open_count_min is not None and str(open_count_min).strip() != "":
            where.append(LimitUpStock.open_count > int(open_count_min))
        if open_count_max is not None and str(open_count_max).strip() != "":
            where.append(LimitUpStock.open_count <= int(open_count_max))
        if industry:
            where.append(LimitUpStock.industry == industry)
        if concept:
            where.append(LimitUpStock.concept_tags.contains([concept]))
        if strength_min is not None:
            where.append(LimitUpStock.strength_level >= int(strength_min))
        if strength_max is not None:
            where.append(LimitUpStock.strength_level <= int(strength_max))
        if is_dragon_head is not None:
            where.append(LimitUpStock.is_dragon_head == bool(is_dragon_head))
        if limit_up_type:
            where.append(LimitUpStock.limit_up_type == limit_up_type)
        if q:
            like = f"%{q}%"
            where.append(or_(LimitUpStock.stock_name.ilike(like), LimitUpStock.stock_code.ilike(like)))

        with session_scope() as session:
            base = select(LimitUpStock)
            if where:
                base = base.where(and_(*where))

            total = session.execute(base.with_only_columns(LimitUpStock.id).order_by(None)).all()
            items = (
                session.execute(
                    base.order_by(
                        LimitUpStock.limit_up_date.desc(),
                        LimitUpStock.consecutive_days.desc(),
                        LimitUpStock.strength_level.desc(),
                        LimitUpStock.id.desc(),
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
                .scalars()
                .all()
            )
            from app.services.limit_up_analysis_service import LimitUpAnalysisService

            serialized_items = []
            for item in items:
                item_dict = item.to_dict()
                item_dict["has_analysis_report"] = LimitUpAnalysisService.has_external_report(
                    item.stock_code,
                    item.stock_name,
                    item.limit_up_date,
                )
                serialized_items.append(item_dict)

            return {"items": serialized_items, "total": len(total)}

    @staticmethod
    def consecutive_rank(trade_date: str) -> List[Dict[str, Any]]:
        """连板榜排名"""
        td = _parse_date(trade_date)
        if not td:
            raise ValueError("trade_date 无效")

        with session_scope() as session:
            items = (
                session.execute(
                    select(LimitUpStock)
                    .where(and_(LimitUpStock.limit_up_date == td, LimitUpStock.consecutive_days >= 2))
                    .order_by(LimitUpStock.consecutive_days.desc(), LimitUpStock.seal_amount.desc())
                    .limit(50)
                )
                .scalars()
                .all()
            )
            return [e.to_dict() for e in items]

    @staticmethod
    def dragon_heads(trade_date: str) -> List[Dict[str, Any]]:
        """龙头股列表"""
        td = _parse_date(trade_date)
        if not td:
            raise ValueError("trade_date 无效")

        with session_scope() as session:
            items = (
                session.execute(
                    select(LimitUpStock)
                    .where(and_(LimitUpStock.limit_up_date == td, LimitUpStock.is_dragon_head == True))
                    .order_by(LimitUpStock.dragon_rank.asc())
                    .limit(10)
                )
                .scalars()
                .all()
            )
            return [e.to_dict() for e in items]

    @staticmethod
    def statistics(start_date: Optional[str] = None, end_date: Optional[str] = None):
        """区间统计"""
        sd = _parse_date(start_date)
        ed = _parse_date(end_date)
        where = []
        if sd:
            where.append(LimitUpStock.limit_up_date >= sd)
        if ed:
            where.append(LimitUpStock.limit_up_date <= ed)

        with session_scope() as session:
            base = select(LimitUpStock)
            if where:
                base = base.where(and_(*where))

            total = session.execute(base.with_only_columns(func.count()).order_by(None)).scalar_one()

            by_consecutive_stmt = select(LimitUpStock.consecutive_days, func.count()).select_from(LimitUpStock)
            if where:
                by_consecutive_stmt = by_consecutive_stmt.where(and_(*where))
            by_consecutive_stmt = by_consecutive_stmt.group_by(LimitUpStock.consecutive_days).order_by(
                LimitUpStock.consecutive_days.desc()
            )
            by_consecutive = session.execute(by_consecutive_stmt).all()

            by_industry_stmt = select(LimitUpStock.industry, func.count()).select_from(LimitUpStock)
            if where:
                by_industry_stmt = by_industry_stmt.where(and_(*where))
            by_industry_stmt = by_industry_stmt.where(LimitUpStock.industry.isnot(None)).group_by(
                LimitUpStock.industry
            ).order_by(func.count().desc()).limit(10)
            by_industry = session.execute(by_industry_stmt).all()

            by_strength_stmt = select(LimitUpStock.strength_level, func.count()).select_from(LimitUpStock)
            if where:
                by_strength_stmt = by_strength_stmt.where(and_(*where))
            by_strength_stmt = by_strength_stmt.group_by(LimitUpStock.strength_level).order_by(
                LimitUpStock.strength_level.desc()
            )
            by_strength = session.execute(by_strength_stmt).all()

            return {
                "total": int(total),
                "by_consecutive": {str(k): int(v) for k, v in by_consecutive},
                "by_industry": {str(k): int(v) for k, v in by_industry},
                "by_strength": {str(k): int(v) for k, v in by_strength},
            }

    @staticmethod
    def fund_flow_rank(start_date: Optional[str] = None, end_date: Optional[str] = None, top: int = 20):
        """资金流向排行"""
        sd = _parse_date(start_date)
        ed = _parse_date(end_date)
        top = min(max(int(top), 1), 50)

        where = []
        if sd:
            where.append(LimitUpStock.limit_up_date >= sd)
        if ed:
            where.append(LimitUpStock.limit_up_date <= ed)

        with session_scope() as session:
            base = select(LimitUpStock)
            if where:
                base = base.where(and_(*where))

            inst_items = (
                session.execute(
                    base.order_by(LimitUpStock.institution_net_buy.desc()).limit(top)
                )
                .scalars()
                .all()
            )

            youzi_items = (
                session.execute(
                    base.order_by(LimitUpStock.hot_money_net_buy.desc()).limit(top)
                )
                .scalars()
                .all()
            )

            return {
                "institution_top": [e.to_dict() for e in inst_items],
                "hot_money_top": [e.to_dict() for e in youzi_items],
            }

    @staticmethod
    def concept_statistics(start_date: Optional[str] = None, end_date: Optional[str] = None, top: int = 20):
        """概念热度统计"""
        sd = _parse_date(start_date)
        ed = _parse_date(end_date)
        top = min(max(int(top), 1), 50)

        where = []
        if sd:
            where.append(LimitUpStock.limit_up_date >= sd)
        if ed:
            where.append(LimitUpStock.limit_up_date <= ed)

        with session_scope() as session:
            base = select(LimitUpStock.concept_tags)
            if where:
                base = base.where(and_(*where))

            items = session.execute(base).scalars().all()

            # 统计概念出现次数
            concept_count = {}
            for tags in items:
                if tags:
                    for tag in tags:
                        concept_count[tag] = concept_count.get(tag, 0) + 1

            # 排序
            sorted_concepts = sorted(concept_count.items(), key=lambda x: x[1], reverse=True)[:top]
            return {"concepts": dict(sorted_concepts)}
