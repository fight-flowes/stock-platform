"""
涨停股模型 - 支持按月分区

注意：PostgreSQL 分区表要求主键必须包含分区键
因此主键从单字段 id 改为复合主键 (id, limit_up_date)
"""
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, Time, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.settings import PGSCHEMA


class LimitUpStock(Base):
    __tablename__ = "limit_up_stocks"
    __table_args__ = {"schema": PGSCHEMA}

    # === 主键（复合主键：id + limit_up_date 分区键） ===
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    limit_up_date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False, index=True)

    # === 基本信息 ===
    stock_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    stock_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # === 涨停特征 ===
    consecutive_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    limit_up_type: Mapped[str] = mapped_column(String(32), nullable=False, default="first_board")
    close: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # 收盘价（涨停价）
    seal_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    seal_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    turnover_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 量比

    # === 时间信息 ===
    first_limit_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    last_limit_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # === 板块概念 ===
    industry: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    concept_tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # === 资金动向 ===
    institution_net_buy: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    hot_money_net_buy: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    north_net_buy: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_net_buy: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # === 涨停原因 ===
    reason_category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reason_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # === 强度评级 ===
    strength_level: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    strength_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # === 龙头判断 ===
    is_dragon_head: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dragon_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # === 元数据 ===
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
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
            "limit_up_date": self.limit_up_date.isoformat(),
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "consecutive_days": self.consecutive_days,
            "limit_up_type": self.limit_up_type,
            "close": self.close,  # 收盘价
            "seal_amount": self.seal_amount,
            "seal_ratio": self.seal_ratio,
            "turnover_rate": self.turnover_rate,
            "volume_ratio": self.volume_ratio,  # 量比
            "first_limit_time": str(self.first_limit_time) if self.first_limit_time else None,
            "last_limit_time": str(self.last_limit_time) if self.last_limit_time else None,
            "open_count": self.open_count,
            "industry": self.industry,
            "concept_tags": self.concept_tags or [],
            "institution_net_buy": self.institution_net_buy,
            "hot_money_net_buy": self.hot_money_net_buy,
            "north_net_buy": self.north_net_buy,
            "total_net_buy": self.total_net_buy,
            "reason_category": self.reason_category,
            "reason_detail": self.reason_detail,
            "strength_level": self.strength_level,
            "strength_score": self.strength_score,
            "is_dragon_head": self.is_dragon_head,
            "dragon_rank": self.dragon_rank,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }