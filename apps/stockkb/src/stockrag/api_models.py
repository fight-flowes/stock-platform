from __future__ import annotations

from pydantic import BaseModel, Field


class MarketEventListFiltersModel(BaseModel):
    date_from: str = ""
    date_to: str = ""
    keyword: str = ""
    industry: str = ""
    theme: str = ""
    event_type: str = ""
    favorites_only: bool | None = None
    is_cross_stock: bool | None = None
    min_affected_stock_count: int | None = None
    is_active: bool | None = None


class MarketEventStockModel(BaseModel):
    stock_code: str
    stock_name: str = ""


class MarketEventSourceReportModel(BaseModel):
    report_id: str
    report_title: str
    stock_code: str
    stock_name: str
    report_date: str
    source_name: str = ""
    source_url: str = ""
    source_path: str = ""


class MarketEventListItemModel(BaseModel):
    event_key: str
    event_name: str
    event_time_text: str
    primary_industry: str = ""
    primary_theme: str = ""
    affected_stock_count: int = 0
    affected_stocks_preview: list[MarketEventStockModel] = Field(default_factory=list)
    source_report_count: int = 0
    first_seen_date: str = ""
    latest_active_date: str = ""
    active_dates: list[str] = Field(default_factory=list)
    is_cross_stock: bool = False
    is_active: bool = False
    is_favorite: bool = False


class MarketEventDetailModel(BaseModel):
    event_key: str
    event_name: str
    event_time_text: str
    event_content: str
    primary_industry: str = ""
    primary_theme: str = ""
    risk_summary: str = ""
    first_seen_date: str = ""
    latest_active_date: str = ""
    active_dates: list[str] = Field(default_factory=list)
    affected_stocks: list[MarketEventStockModel] = Field(default_factory=list)
    source_reports: list[MarketEventSourceReportModel] = Field(default_factory=list)
    source_event_ids: list[str] = Field(default_factory=list)
    is_favorite: bool = False


class MarketEventTimelinePointModel(BaseModel):
    date: str
    affected_stock_count: int = 0
    stocks: list[MarketEventStockModel] = Field(default_factory=list)
    source_report_count: int = 0


class MarketEventFilterMetaModel(BaseModel):
    industries: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    date_min: str = ""
    date_max: str = ""


class MarketEventListRequestModel(BaseModel):
    page: int = 1
    page_size: int = 20
    sort_by: str = "latest_active_date"
    sort_order: str = "desc"
    filters: MarketEventListFiltersModel = Field(default_factory=MarketEventListFiltersModel)


class MarketEventListResponseModel(BaseModel):
    items: list[MarketEventListItemModel] = Field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False
    sort_by: str = "latest_active_date"
    sort_order: str = "desc"


class MarketEventDetailResponseModel(BaseModel):
    found: bool
    event: MarketEventDetailModel | None = None


class MarketEventTimelineResponseModel(BaseModel):
    event_key: str
    timeline: list[MarketEventTimelinePointModel] = Field(default_factory=list)


class MarketEventFilterMetaResponseModel(BaseModel):
    industries: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    date_min: str = ""
    date_max: str = ""
