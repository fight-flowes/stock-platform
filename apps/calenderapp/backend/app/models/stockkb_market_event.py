from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class StockkbMarketEventStock:
    stock_code: str
    stock_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StockkbMarketEventSourceReport:
    report_id: str
    report_title: str
    stock_code: str
    stock_name: str
    report_date: str
    source_name: str = ""
    source_url: str = ""
    source_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StockkbMarketEventListItem:
    event_key: str
    event_name: str
    event_time_text: str
    primary_industry: str = ""
    primary_theme: str = ""
    affected_stock_count: int = 0
    affected_stocks_preview: list[StockkbMarketEventStock] = field(default_factory=list)
    source_report_count: int = 0
    first_seen_date: str = ""
    latest_active_date: str = ""
    active_dates: list[str] = field(default_factory=list)
    is_cross_stock: bool = False
    # DEPRECATED — frozen False for new rows; historical rows preserve their
    # original 5-day-heuristic value. Frontend "发酵中" badge has been removed
    # and no UI consumes this field. Will be redefined later.
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["affected_stocks_preview"] = [item.to_dict() for item in self.affected_stocks_preview]
        return payload


@dataclass(slots=True)
class StockkbMarketEventDetail:
    event_key: str
    event_name: str
    event_time_text: str
    event_content: str
    primary_industry: str = ""
    primary_theme: str = ""
    risk_summary: str = ""
    first_seen_date: str = ""
    latest_active_date: str = ""
    active_dates: list[str] = field(default_factory=list)
    affected_stocks: list[StockkbMarketEventStock] = field(default_factory=list)
    source_reports: list[StockkbMarketEventSourceReport] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["affected_stocks"] = [item.to_dict() for item in self.affected_stocks]
        payload["source_reports"] = [item.to_dict() for item in self.source_reports]
        return payload


@dataclass(slots=True)
class StockkbMarketEventTimelinePoint:
    date: str
    affected_stock_count: int = 0
    stocks: list[StockkbMarketEventStock] = field(default_factory=list)
    source_report_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stocks"] = [item.to_dict() for item in self.stocks]
        return payload


@dataclass(slots=True)
class StockkbMarketEventFilterMeta:
    industries: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    date_min: str = ""
    date_max: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
