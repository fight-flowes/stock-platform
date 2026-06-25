from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.settings import PGSCHEMA


class StockGroupMember(Base):
    __tablename__ = "stock_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "stock_id", name="uq_stock_group_members"),
        {"schema": PGSCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{PGSCHEMA}.stock_groups.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stock_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{PGSCHEMA}.stocks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
