from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from dateutil.parser import isoparse

from app.db import session_scope
from app.models.calendar_day import CalendarDay
from app.services.tushare_sync_service import TushareSyncService


def _parse_day(s: str) -> date:
    return isoparse(s).date()


def _iter_days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d = d + timedelta(days=1)


class CalendarService:
    @staticmethod
    def _fallback_trading_days(start: date, end: date) -> List[str]:
        """
        在 Tushare 不可用时，使用工作日 + 非法定休假做近似交易日回退。
        注意：这里故意不把调休上班日（周末）视为交易日。
        """
        rows = CalendarService.list_days(start.isoformat(), end.isoformat(), ensure=True)
        trading_days = []
        for row in rows:
            current = _parse_day(row["date"])
            if current.weekday() < 5 and not row.get("is_rest", False):
                trading_days.append(row["date"])
        return trading_days

    @staticmethod
    def _compute_day(d: date) -> Tuple[str, Optional[str], bool, bool]:
        from lunar_python import Solar
        from lunar_python.util import HolidayUtil

        solar = Solar.fromYmd(d.year, d.month, d.day)
        lunar = solar.getLunar()
        lunar_day = lunar.getDayInChinese()

        holiday = HolidayUtil.getHoliday(d.year, d.month, d.day)
        if not holiday:
            return lunar_day, None, False, False

        if holiday.isWork():
            return lunar_day, None, False, True

        return lunar_day, holiday.getName(), True, False

    @staticmethod
    def list_days(start_date: str, end_date: str, ensure: bool = True) -> List[Dict]:
        start = _parse_day(start_date)
        end = _parse_day(end_date)
        if end < start:
            raise ValueError("end_date 不能早于 start_date")
        if (end - start).days > 400:
            raise ValueError("日期范围过大")

        with session_scope() as session:
            existing = (
                session.query(CalendarDay)
                .filter(CalendarDay.day >= start)
                .filter(CalendarDay.day <= end)
                .all()
            )
            by_day = {x.day: x for x in existing}

            if ensure:
                to_create = []
                for d in _iter_days(start, end):
                    if d in by_day:
                        continue
                    lunar_day, holiday_name, is_rest, is_work = CalendarService._compute_day(d)
                    obj = CalendarDay(
                        day=d,
                        lunar_day=lunar_day,
                        holiday_name=holiday_name,
                        is_rest=is_rest,
                        is_work=is_work,
                    )
                    to_create.append(obj)
                    by_day[d] = obj
                if to_create:
                    session.add_all(to_create)

            rows = [by_day[d].to_dict() for d in sorted(by_day.keys())]
            return rows

    @staticmethod
    def day_meta_map(start_date: str, end_date: str, ensure: bool = True) -> Dict[str, Dict]:
        rows = CalendarService.list_days(start_date, end_date, ensure=ensure)
        meta = {}
        for r in rows:
            status = "rest" if r.get("is_rest") else ("work" if r.get("is_work") else "none")
            meta[r["date"]] = {"lunar_day": r.get("lunar_day"), "holiday_name": r.get("holiday_name"), "status": status}
        return meta

    @staticmethod
    def trading_days(start_date: str, end_date: str) -> List[str]:
        start = _parse_day(start_date)
        end = _parse_day(end_date)
        if end < start:
            raise ValueError("end_date 不能早于 start_date")
        if (end - start).days > 400:
            raise ValueError("日期范围过大")

        try:
            days = TushareSyncService.get_trade_calendar(start.isoformat(), end.isoformat())
            normalized = []
            for day in days:
                day_str = str(day)
                if len(day_str) == 8 and day_str.isdigit():
                    normalized.append(f"{day_str[:4]}-{day_str[4:6]}-{day_str[6:8]}")
                else:
                    normalized.append(_parse_day(day_str).isoformat())
            return sorted(set(normalized))
        except Exception:
            return CalendarService._fallback_trading_days(start, end)
