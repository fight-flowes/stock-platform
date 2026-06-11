from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.settings import PGSCHEMA


class CalendarDay(Base):
    __tablename__ = "calendar_days"
    __table_args__ = {"schema": PGSCHEMA}

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    lunar_day: Mapped[str] = mapped_column(String(32), nullable=False)
    holiday_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_rest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_work: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_dict(self):
        return {
            "date": self.day.isoformat(),
            "lunar_day": self.lunar_day,
            "holiday_name": self.holiday_name,
            "is_rest": bool(self.is_rest),
            "is_work": bool(self.is_work),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
