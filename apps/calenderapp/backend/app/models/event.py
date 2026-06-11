from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.settings import PGSCHEMA


class CalendarEvent(Base):
    __tablename__ = "events"
    __table_args__ = {"schema": PGSCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    importance: Mapped[int] = mapped_column(Integer, index=True, nullable=False, default=1)
    event_type: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # 新增：来源 URL
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stock_list: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    credibility: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # 新增：可信度星级（⭐⭐⭐⭐⭐）

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
            "event_date": self.event_date.isoformat(),
            "title": self.title,
            "importance": self.importance,
            "event_type": self.event_type,
            "source": self.source,
            "source_url": self.source_url,  # 新增
            "description": self.description,
            "stock_list": self.stock_list or [],
            "credibility": self.credibility,  # 新增
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
