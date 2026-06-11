import os
import sys
from datetime import date, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import session_scope
from app.models import CalendarDay, CalendarEvent, Stock
from app.services.calendar_service import CalendarService


def _find_first_workday(start: date, end: date):
    from lunar_python.util import HolidayUtil

    d = start
    while d <= end:
        h = HolidayUtil.getHoliday(d.year, d.month, d.day)
        if h and h.isWork():
            return d
        d += timedelta(days=1)
    return None


def seed():
    CalendarService.list_days("2026-02-01", "2026-03-31", ensure=True)

    with session_scope() as session:
        stock_items = [
            ("600519", "贵州茅台", "SH"),
            ("000001", "平安银行", "SZ"),
            ("000333", "美的集团", "SZ"),
            ("601318", "中国平安", "SH"),
        ]
        for code, name, exchange in stock_items:
            existing = session.query(Stock).filter(Stock.code == code).first()
            if existing:
                existing.name = name
                existing.exchange = exchange
            else:
                session.add(Stock(code=code, name=name, exchange=exchange))

        has_any_event = bool(session.query(CalendarEvent.id).limit(1).first())
        if not has_any_event:
            normal_day = date(2026, 2, 12)
            holiday_day = date(2026, 2, 17)
            work_day = _find_first_workday(date(2026, 2, 1), date(2026, 3, 31)) or date(2026, 2, 28)

            session.add_all(
                [
                    CalendarEvent(
                        event_date=normal_day,
                        title="普通日示例：关注公告",
                        importance=3,
                        event_type="other",
                        source="seed",
                        description="用于联调展示普通日期",
                        stock_list=["000001"],
                    ),
                    CalendarEvent(
                        event_date=holiday_day,
                        title="节假日示例：春节期间提醒",
                        importance=4,
                        event_type="other",
                        source="seed",
                        description="用于联调展示节假日日期",
                        stock_list=["600519"],
                    ),
                    CalendarEvent(
                        event_date=work_day,
                        title="调休上班示例：盘前复盘",
                        importance=2,
                        event_type="other",
                        source="seed",
                        description="用于联调展示调休上班日期",
                        stock_list=["601318"],
                    ),
                ]
            )

        missing_day = session.query(CalendarDay).filter(CalendarDay.day == date(2026, 2, 17)).first()
        if not missing_day:
            CalendarService.list_days("2026-02-17", "2026-02-17", ensure=True)


if __name__ == "__main__":
    seed()

