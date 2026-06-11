from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import and_, func, or_, select

from app.db import session_scope
from app.models.event import CalendarEvent


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


class EventsService:
    @staticmethod
    def get_event(event_id: int) -> Optional[Dict[str, Any]]:
        event_id = int(event_id)
        with session_scope() as session:
            event = session.get(CalendarEvent, event_id)
            return event.to_dict() if event else None

    @staticmethod
    def create_event(payload: Dict[str, Any]) -> Dict[str, Any]:
        event_date = _parse_date(payload.get("event_date"))
        title = (payload.get("title") or "").strip()
        if not event_date or not title:
            raise ValueError("event_date 和 title 不能为空")

        importance = int(payload.get("importance", 1))
        if importance < 1 or importance > 5:
            raise ValueError("importance 必须在 1~5 之间")

        stock_list = payload.get("stock_list") or []
        if isinstance(stock_list, str):
            stock_list = [s.strip() for s in stock_list.split(",") if s.strip()]
        if not isinstance(stock_list, list):
            raise ValueError("stock_list 必须为数组或逗号分隔字符串")

        event_type = (payload.get("event_type") or "").strip() or None
        source = (payload.get("source") or "").strip() or None
        source_url = (payload.get("source_url") or "").strip() or None  # 新增
        description = payload.get("description")
        credibility = (payload.get("credibility") or "").strip() or None  # 新增

        with session_scope() as session:
            event = CalendarEvent(
                event_date=event_date,
                title=title,
                importance=importance,
                event_type=event_type,
                source=source,
                source_url=source_url,  # 新增
                description=description,
                stock_list=stock_list,
                credibility=credibility,  # 新增
            )
            session.add(event)
            session.flush()
            return event.to_dict()

    @staticmethod
    def update_event(event_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_id = int(event_id)
        with session_scope() as session:
            event = session.get(CalendarEvent, event_id)
            if not event:
                return None

            if "event_date" in payload:
                event_date = _parse_date(payload.get("event_date"))
                if not event_date:
                    raise ValueError("event_date 无效")
                event.event_date = event_date

            if "title" in payload:
                title = (payload.get("title") or "").strip()
                if not title:
                    raise ValueError("title 不能为空")
                event.title = title

            if "importance" in payload:
                importance = int(payload.get("importance"))
                if importance < 1 or importance > 5:
                    raise ValueError("importance 必须在 1~5 之间")
                event.importance = importance

            if "event_type" in payload:
                event.event_type = (payload.get("event_type") or "").strip() or None

            if "source" in payload:
                event.source = (payload.get("source") or "").strip() or None

            if "source_url" in payload:  # 新增
                event.source_url = (payload.get("source_url") or "").strip() or None

            if "description" in payload:
                event.description = payload.get("description")

            if "stock_list" in payload:
                stock_list = payload.get("stock_list") or []
                if isinstance(stock_list, str):
                    stock_list = [s.strip() for s in stock_list.split(",") if s.strip()]
                if not isinstance(stock_list, list):
                    raise ValueError("stock_list 必须为数组或逗号分隔字符串")
                event.stock_list = stock_list

            if "credibility" in payload:  # 新增
                event.credibility = (payload.get("credibility") or "").strip() or None

            session.flush()
            return event.to_dict()

    @staticmethod
    def delete_event(event_id: int) -> bool:
        event_id = int(event_id)
        with session_scope() as session:
            event = session.get(CalendarEvent, event_id)
            if not event:
                return False
            session.delete(event)
            return True

    @staticmethod
    def list_events(
        page: int,
        page_size: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        q: Optional[str] = None,
        importance_min: Optional[int] = None,
        importance_max: Optional[int] = None,
        event_type: Optional[str] = None,
        stock_code: Optional[str] = None,
    ):
        page = max(int(page), 1)
        page_size = max(int(page_size), 1)

        sd = _parse_date(start_date)
        ed = _parse_date(end_date)
        q = (q or "").strip() or None
        event_type = (event_type or "").strip() or None
        stock_code = (stock_code or "").strip() or None

        where = []
        if sd:
            where.append(CalendarEvent.event_date >= sd)
        if ed:
            where.append(CalendarEvent.event_date <= ed)
        if q:
            like = f"%{q}%"
            where.append(or_(CalendarEvent.title.ilike(like), CalendarEvent.description.ilike(like)))
        if importance_min is not None:
            where.append(CalendarEvent.importance >= int(importance_min))
        if importance_max is not None:
            where.append(CalendarEvent.importance <= int(importance_max))
        if event_type:
            where.append(CalendarEvent.event_type == event_type)
        if stock_code:
            where.append(CalendarEvent.stock_list.contains([stock_code]))

        with session_scope() as session:
            base = select(CalendarEvent)
            if where:
                base = base.where(and_(*where))

            total = session.execute(base.with_only_columns(CalendarEvent.id).order_by(None)).all()
            items = (
                session.execute(
                    base.order_by(CalendarEvent.event_date.asc(), CalendarEvent.importance.desc(), CalendarEvent.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
                .scalars()
                .all()
            )
            return {"items": [e.to_dict() for e in items], "total": len(total)}

    @staticmethod
    def upcoming(days: int = 7, importance_min: int = 3):
        days = max(int(days), 1)
        importance_min = max(int(importance_min), 1)
        today = date.today()
        end = today + timedelta(days=days)
        with session_scope() as session:
            items = (
                session.execute(
                    select(CalendarEvent)
                    .where(
                        and_(
                            CalendarEvent.event_date >= today,
                            CalendarEvent.event_date <= end,
                            CalendarEvent.importance >= importance_min,
                        )
                    )
                    .order_by(CalendarEvent.event_date.asc(), CalendarEvent.importance.desc())
                    .limit(500)
                )
                .scalars()
                .all()
            )
            return [e.to_dict() for e in items]

    @staticmethod
    def statistics(start_date: Optional[str] = None, end_date: Optional[str] = None):
        sd = _parse_date(start_date)
        ed = _parse_date(end_date)
        where = []
        if sd:
            where.append(CalendarEvent.event_date >= sd)
        if ed:
            where.append(CalendarEvent.event_date <= ed)

        with session_scope() as session:
            base = select(CalendarEvent)
            if where:
                base = base.where(and_(*where))

            total = session.execute(base.with_only_columns(func.count()).order_by(None)).scalar_one()
            by_importance_stmt = select(CalendarEvent.importance, func.count()).select_from(CalendarEvent)
            if where:
                by_importance_stmt = by_importance_stmt.where(and_(*where))
            by_importance_stmt = by_importance_stmt.group_by(CalendarEvent.importance).order_by(
                CalendarEvent.importance.desc()
            )
            by_importance = session.execute(by_importance_stmt).all()

            by_type_stmt = select(CalendarEvent.event_type, func.count()).select_from(CalendarEvent)
            if where:
                by_type_stmt = by_type_stmt.where(and_(*where))
            by_type_stmt = by_type_stmt.group_by(CalendarEvent.event_type).order_by(func.count().desc())
            by_type = session.execute(by_type_stmt).all()
            return {
                "total": int(total),
                "by_importance": {str(k): int(v) for k, v in by_importance},
                "by_type": {str(k) if k is not None else "null": int(v) for k, v in by_type},
            }
