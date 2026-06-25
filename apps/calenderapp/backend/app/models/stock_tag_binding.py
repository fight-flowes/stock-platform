from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.settings import PGSCHEMA


class StockTagBinding(Base):
    __tablename__ = "stock_tag_bindings"
    __table_args__ = (
        UniqueConstraint("stock_id", "tag_id", name="uq_stock_tag_bindings"),
        {"schema": PGSCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{PGSCHEMA}.stocks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{PGSCHEMA}.stock_tags.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
