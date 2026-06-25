from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import func, select

from app.db import session_scope
from app.models.stock import Stock
from app.models.stock_group import StockGroup
from app.models.stock_group_member import StockGroupMember


def _normalize_color(value: Any) -> str | None:
    color = ("" if value is None else str(value)).strip()
    return color or None


class StockGroupsService:
    @staticmethod
    def list_groups() -> list[dict[str, Any]]:
        with session_scope() as session:
            count_rows = session.execute(
                select(
                    StockGroupMember.group_id,
                    func.count(StockGroupMember.id).label("stock_count"),
                ).group_by(StockGroupMember.group_id)
            ).all()
            count_map = {int(group_id): int(stock_count or 0) for group_id, stock_count in count_rows}

            groups = session.execute(
                select(StockGroup).order_by(StockGroup.sort_order.asc(), StockGroup.id.asc())
            ).scalars().all()

            return [
                {
                    **group.to_dict(),
                    "stock_count": count_map.get(group.id, 0),
                }
                for group in groups
            ]

    @staticmethod
    def create_group(name: str, description: str | None = None, color: str | None = None) -> dict[str, Any]:
        name = (name or "").strip()
        if not name:
            raise ValueError("分组名称不能为空")

        with session_scope() as session:
            existing = session.execute(select(StockGroup).where(StockGroup.name == name)).scalars().first()
            if existing:
                raise ValueError("分组名称已存在")

            max_sort_order = session.execute(select(func.max(StockGroup.sort_order))).scalar()

            group = StockGroup(
                name=name,
                description=(description or "").strip() or None,
                color=_normalize_color(color),
                sort_order=int(max_sort_order or 0) + 1,
            )
            session.add(group)
            session.flush()
            return {
                **group.to_dict(),
                "stock_count": 0,
            }

    @staticmethod
    def update_group(group_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        with session_scope() as session:
            group = session.execute(select(StockGroup).where(StockGroup.id == int(group_id))).scalars().first()
            if not group:
                raise ValueError("分组不存在")

            if "name" in payload:
                name = (payload.get("name") or "").strip()
                if not name:
                    raise ValueError("分组名称不能为空")
                existing = session.execute(
                    select(StockGroup).where(StockGroup.name == name, StockGroup.id != group.id)
                ).scalars().first()
                if existing:
                    raise ValueError("分组名称已存在")
                group.name = name

            if "description" in payload:
                group.description = (payload.get("description") or "").strip() or None

            if "color" in payload:
                group.color = _normalize_color(payload.get("color"))

            if "sort_order" in payload and payload.get("sort_order") is not None:
                group.sort_order = int(payload.get("sort_order"))

            session.flush()

            stock_count = session.execute(
                select(func.count(StockGroupMember.id)).where(StockGroupMember.group_id == group.id)
            ).scalar() or 0
            return {
                **group.to_dict(),
                "stock_count": int(stock_count),
            }

    @staticmethod
    def delete_group(group_id: int) -> dict[str, Any]:
        with session_scope() as session:
            group = session.execute(select(StockGroup).where(StockGroup.id == int(group_id))).scalars().first()
            if not group:
                raise ValueError("分组不存在")
            payload = {"id": group.id, "name": group.name, "deleted": True}
            session.delete(group)
            session.flush()
            return payload

    @staticmethod
    def add_members(group_id: int, stock_codes: Iterable[str]) -> dict[str, Any]:
        codes = [str(code).strip() for code in stock_codes if str(code).strip()]
        if not codes:
            raise ValueError("stock_codes 不能为空")

        with session_scope() as session:
            group = session.execute(select(StockGroup).where(StockGroup.id == int(group_id))).scalars().first()
            if not group:
                raise ValueError("分组不存在")

            stocks = session.execute(select(Stock).where(Stock.code.in_(codes))).scalars().all()
            if not stocks:
                raise ValueError("未找到股票")

            stock_map = {stock.code: stock for stock in stocks}
            missing_codes = [code for code in codes if code not in stock_map]
            if missing_codes:
                raise ValueError(f"股票不存在: {', '.join(missing_codes[:5])}")

            existing_ids = set(
                session.execute(
                    select(StockGroupMember.stock_id).where(
                        StockGroupMember.group_id == group.id,
                        StockGroupMember.stock_id.in_([stock.id for stock in stocks]),
                    )
                ).scalars().all()
            )

            added_count = 0
            for stock in stocks:
                if not stock.is_favorite:
                    stock.is_favorite = True
                    stock.favorited_at = datetime.now()
                if stock.id in existing_ids:
                    continue
                session.add(StockGroupMember(group_id=group.id, stock_id=stock.id))
                added_count += 1

            session.flush()
            return {
                "group_id": group.id,
                "group_name": group.name,
                "added_count": added_count,
            }
