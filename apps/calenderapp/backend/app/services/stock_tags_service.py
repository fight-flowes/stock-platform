from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import func, select

from app.db import session_scope
from app.models.stock import Stock
from app.models.stock_tag import StockTag
from app.models.stock_tag_binding import StockTagBinding


def _normalize_color(value: Any) -> str | None:
    color = ("" if value is None else str(value)).strip()
    return color or None


class StockTagsService:
    @staticmethod
    def list_tags() -> list[dict[str, Any]]:
        with session_scope() as session:
            count_rows = session.execute(
                select(
                    StockTagBinding.tag_id,
                    func.count(StockTagBinding.id).label("stock_count"),
                ).group_by(StockTagBinding.tag_id)
            ).all()
            count_map = {int(tag_id): int(stock_count or 0) for tag_id, stock_count in count_rows}

            tags = session.execute(
                select(StockTag).order_by(StockTag.sort_order.asc(), StockTag.id.asc())
            ).scalars().all()
            return [
                {
                    **tag.to_dict(),
                    "stock_count": count_map.get(tag.id, 0),
                }
                for tag in tags
            ]

    @staticmethod
    def create_tag(name: str, color: str | None = None) -> dict[str, Any]:
        name = (name or "").strip()
        if not name:
            raise ValueError("标签名称不能为空")

        with session_scope() as session:
            existing = session.execute(select(StockTag).where(StockTag.name == name)).scalars().first()
            if existing:
                raise ValueError("标签名称已存在")

            tag = StockTag(name=name, color=_normalize_color(color))
            session.add(tag)
            session.flush()
            return {
                **tag.to_dict(),
                "stock_count": 0,
            }

    @staticmethod
    def delete_tag(tag_id: int) -> dict[str, Any]:
        with session_scope() as session:
            tag = session.execute(select(StockTag).where(StockTag.id == int(tag_id))).scalars().first()
            if not tag:
                raise ValueError("标签不存在")
            payload = {"id": tag.id, "name": tag.name, "deleted": True}
            session.delete(tag)
            session.flush()
            return payload

    @staticmethod
    def add_bindings(tag_id: int, stock_codes: Iterable[str]) -> dict[str, Any]:
        codes = [str(code).strip() for code in stock_codes if str(code).strip()]
        if not codes:
            raise ValueError("stock_codes 不能为空")

        with session_scope() as session:
            tag = session.execute(select(StockTag).where(StockTag.id == int(tag_id))).scalars().first()
            if not tag:
                raise ValueError("标签不存在")

            stocks = session.execute(select(Stock).where(Stock.code.in_(codes))).scalars().all()
            if not stocks:
                raise ValueError("未找到股票")

            stock_map = {stock.code: stock for stock in stocks}
            missing_codes = [code for code in codes if code not in stock_map]
            if missing_codes:
                raise ValueError(f"股票不存在: {', '.join(missing_codes[:5])}")

            existing_ids = set(
                session.execute(
                    select(StockTagBinding.stock_id).where(
                        StockTagBinding.tag_id == tag.id,
                        StockTagBinding.stock_id.in_([stock.id for stock in stocks]),
                    )
                ).scalars().all()
            )

            added_count = 0
            for stock in stocks:
                stock.is_favorite = True
                if stock.id in existing_ids:
                    continue
                session.add(StockTagBinding(stock_id=stock.id, tag_id=tag.id))
                added_count += 1

            session.flush()
            return {
                "tag_id": tag.id,
                "tag_name": tag.name,
                "added_count": added_count,
            }
