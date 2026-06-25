from datetime import datetime, date
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.settings import PGSCHEMA


class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = {"schema": PGSCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    exchange: Mapped[Optional[str]] = mapped_column(String(16), index=True, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    favorited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # 缓存的行情数据
    cache_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cache_pct_chg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cache_total_mv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cache_circ_mv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cache_turnover_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cache_holder_num: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cache_trade_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "exchange": self.exchange,
            "is_favorite": self.is_favorite,
            "favorited_at": self.favorited_at.isoformat() if self.favorited_at else None,
            "cache_close": self.cache_close,
            "cache_pct_chg": self.cache_pct_chg,
            "cache_total_mv": self.cache_total_mv,
            "cache_circ_mv": self.cache_circ_mv,
            "cache_turnover_rate": self.cache_turnover_rate,
            "cache_holder_num": self.cache_holder_num,
            "cache_trade_date": str(self.cache_trade_date) if self.cache_trade_date else None
        }
