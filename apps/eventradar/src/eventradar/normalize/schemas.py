"""Stable in-memory schema for forward-looking events.

Field naming is deliberately aligned with stockkb's market_event contract
(see ``calenderapp/backend/app/services/eventradar_proxy_service.py`` —
``_normalize_announcement``) so the same UI components can render both data
families without translation. Keep the dataclass fields and the DuckDB DDL
(see :mod:`eventradar.storage.ddl`) in lock-step.

This module is intentionally dependency-light — only stdlib — so it can be
imported anywhere without dragging in adapters or DuckDB.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


# --- vocabularies -----------------------------------------------------------
#
# Kept as sets of literals rather than Enum so the JSON serialization stays
# trivial. Adapters validate against these tuples before persisting.

# Where the event was scraped from. Each adapter declares its own constant.
SOURCE_VALUES: tuple[str, ...] = (
    "em_gsrl",          # 东方财富-数据中心-股市日历-公司动态
    "em_yysj",          # 东方财富-年报季报-预约披露时间
    "em_yjyg",          # 东方财富-年报季报-业绩预告
    "em_yjkb",          # 东方财富-年报季报-业绩快报
    "em_ipo_declare",   # 东方财富-数据中心-新股申购-首发申报
    "em_repurchase",    # 东方财富-股票回购
    "cninfo_yypl",      # 巨潮资讯-预约披露
    "baidu_calendar",   # 百度股市通-财经日历
    "wallstreet_macro", # 华尔街见闻-日历-宏观
    "manual",           # 人工补录
)

# Coarse classification of the event's blast radius.
EVENT_SCOPE_VALUES: tuple[str, ...] = (
    "stock",      # 单只标的事件（解禁、股东大会、单股回购等）
    "industry",   # 影响一个或多个行业（华为发布会、车展、医保谈判）
    "theme",      # 题材级（AI/MR/算力等概念）
    "macro",      # 宏观（央行、CPI、PMI、政治局会议）
)

# Confidence in the date itself, NOT in the event content.
TIME_CERTAINTY_VALUES: tuple[str, ...] = (
    "confirmed_date",  # 上游给了精确日期
    "month",           # 只到月，例如 "2026-07 月内"
    "quarter",         # 只到季度
    "rumor",           # 来自电报/新闻的预告，未官宣
)

# Lifecycle of the row.
STATUS_VALUES: tuple[str, ...] = (
    "expected",      # 默认 — 事件尚未发生
    "materialized",  # 事件日期已过，已经物化为已发生事件
    "obsolete",      # 上游撤回 / 改期 / 重复
)


@dataclass(slots=True)
class ExpectedEventStock:
    """Light-weight (code, name) pair embedded in ``stock_codes`` / ``leaders``.

    Adapters populate ``stock_name`` when the upstream provides it; consumers
    must tolerate empty names.
    """

    stock_code: str
    stock_name: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class ExpectedEvent:
    """One forward-looking event, normalized.

    Identity:
        ``event_id`` is deterministic (see :mod:`eventradar.normalize.ids`).
        ``(source, source_fingerprint)`` is the cross-pull dedupe key — when
        the same upstream row is fetched twice, we update in place rather
        than insert a duplicate.

    Time:
        ``expected_at`` is the primary anchor (sortable). For interval
        events (e.g. "本周内"), set ``expected_at`` to the start and
        ``expected_at_end`` to the end. ``time_certainty`` annotates how
        precise the date is — UI badge candy.

    Targets:
        ``stock_codes``  — every stock the event explicitly names
        ``industries``   — industry tags inferred / declared
        ``themes``       — concept/题材 tags
        ``leaders``      — subset of stock_codes the enricher tagged as龙头
                          (importance >= some bar). Empty in M1; filled in M3.
    """

    # Identity & provenance
    event_id: str
    source: str
    source_fingerprint: str

    # Classification
    event_type: str                                  # 归一后的英文 enum，见 normalize.event_type_map
    event_name: str
    event_scope: str = "stock"
    scope_reason: str = ""
    event_content: str = ""

    # Time
    expected_at: date | None = None
    expected_at_end: date | None = None
    time_certainty: str = "confirmed_date"

    # Targeting
    stock_codes: list[ExpectedEventStock] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    leaders: list[ExpectedEventStock] = field(default_factory=list)

    # Importance & lifecycle
    importance: int = 1                              # 0..3
    status: str = "expected"

    # Tracing
    source_url: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict.

        Lists of nested dataclasses and date/datetime are flattened to
        ISO strings — both DuckDB JSON columns and the API layer expect
        this shape.
        """
        payload = asdict(self)
        payload["expected_at"] = self.expected_at.isoformat() if self.expected_at else ""
        payload["expected_at_end"] = self.expected_at_end.isoformat() if self.expected_at_end else ""
        payload["ingested_at"] = self.ingested_at.isoformat() if self.ingested_at else ""
        payload["stock_codes"] = [item.to_dict() for item in self.stock_codes]
        payload["leaders"] = [item.to_dict() for item in self.leaders]
        return payload
