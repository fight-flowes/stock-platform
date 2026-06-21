"""东方财富 - 数据中心 - 股市日历 - 公司动态 (``stock_gsrl_gsdt_em``).

The single richest forward-looking endpoint exposed by `akshare` for A-share
companies — one call returns every company event scheduled on a given trade
date (limited to events that companies have publicly disclosed). Coverage
includes:

    * 限售解禁、股东大会、分红派息
    * 增发、配股、回购
    * 重大资产重组、对外担保、股份质押
    * 网上申购日 / 上市日 / 停复牌

Upstream columns (验证于 akshare 1.18.49):

    序号, 代码, 简称, 事件类型, 具体事项, 交易日

Mapping rules:
    - ``交易日``         → ``expected_at`` (DATE)
    - ``事件类型``       → ``event_name`` (display)  +  ``event_type``
                          (英文 enum, via ``map_event_type``)
    - ``具体事项``       → ``event_content``
    - ``代码`` + ``简称`` → ``stock_codes`` (single-element list)
    - ``event_scope``    → "stock" (the gsdt feed is per-company)
    - ``time_certainty`` → "confirmed_date" (上游字段就是日期)
    - ``source``         → "em_gsrl"
    - ``importance``     → 1  (M3 enricher 会重写这里)
    - ``payload``        → {"事件类型": ..., "具体事项": ...} 留作审计

Cross-pull dedupe:
    Fingerprint = (date, code, event_type, sha1(content)[:8]) —
    `具体事项` 文本太长，hash 一下既稳定又短。同一公司同一天可能有多条
    "对外担保"/"质押"，所以必须把内容也算进 fingerprint，否则后续条目会
    覆盖前一条。

This adapter does NOT touch DuckDB. It returns ``list[ExpectedEvent]`` and
lets ``service.run_adapter`` handle persistence.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timedelta
from typing import Iterable

import pandas as pd

from ..akshare_client import AkshareCallError, fetch_dataframe
from ...normalize import (
    ExpectedEvent,
    ExpectedEventStock,
    build_event_id,
    build_source_fingerprint,
    map_event_type,
)
from ...service import ADAPTERS, AdapterSpec

LOGGER = logging.getLogger(__name__)

SOURCE = "em_gsrl"
AKSHARE_FN = "stock_gsrl_gsdt_em"

# Names we expect from the upstream DataFrame. If akshare ever renames a
# column we want a clear error rather than silent KeyError-on-row-N.
_REQUIRED_COLUMNS: tuple[str, ...] = ("代码", "简称", "事件类型", "具体事项", "交易日")


def _coerce_date(value) -> date | None:
    """Tolerant date parser — accepts datetime, date, str, pandas.Timestamp.

    Note: bare ints are deliberately rejected. ``20260619`` looks like a
    YYYYMMDD but pandas would interpret it as a Unix nanosecond epoch and
    return 1970-01-01. Adapter authors should pass strings.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):  # bool subclasses int — exclude before the int check
        return None
    if isinstance(value, int):
        raise ValueError(
            f"date must be a string (YYYY-MM-DD or YYYYMMDD), not int {value!r}"
        )
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        ts = pd.to_datetime(value, errors="coerce")
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    return ts.date()


def _yyyymmdd(value: str | date) -> str:
    """Normalize a date-ish input to ``YYYYMMDD`` for akshare."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    # Accept "2026-06-20" or "20260620"; reject anything else early.
    if "-" in text:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y%m%d")
    if len(text) == 8 and text.isdigit():
        # Validate parseability — raises ValueError if month/day bogus.
        datetime.strptime(text, "%Y%m%d")
        return text
    raise ValueError(f"unrecognized date: {value!r}; want YYYY-MM-DD or YYYYMMDD")


def _row_to_event(row: pd.Series, fetched_for: date) -> ExpectedEvent | None:
    """Map one DataFrame row to an ExpectedEvent.

    Returns None for rows we can't usefully store (missing date / code).
    Logs a warning so silent drops never happen.
    """
    code = str(row.get("代码") or "").strip()
    name = str(row.get("简称") or "").strip()
    raw_type = str(row.get("事件类型") or "").strip()
    content = str(row.get("具体事项") or "").strip()
    expected_at = _coerce_date(row.get("交易日")) or fetched_for

    if not code:
        LOGGER.warning("eventradar.gsrl_skip_row reason=no_code row=%s", dict(row))
        return None
    if not raw_type:
        LOGGER.warning("eventradar.gsrl_skip_row reason=no_event_type code=%s", code)
        return None

    # Hash the content into the fingerprint so multi-row days for the same
    # (code, type) don't collide on upsert. SHA-1 truncated to 8 hex chars
    # is plenty — collisions across the same (date, code, type) pair are
    # not a realistic concern.
    content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()[:8]
    fingerprint = build_source_fingerprint(
        (expected_at.isoformat(), code, raw_type, content_hash)
    )
    event_id = build_event_id(SOURCE, fingerprint)

    return ExpectedEvent(
        event_id=event_id,
        source=SOURCE,
        source_fingerprint=fingerprint,
        event_type=map_event_type(raw_type),
        event_name=raw_type,                # 原始中文给 UI 显示
        event_scope="stock",
        scope_reason="",
        event_content=content,
        expected_at=expected_at,
        expected_at_end=None,
        time_certainty="confirmed_date",
        stock_codes=[ExpectedEventStock(stock_code=code, stock_name=name)],
        industries=[],
        themes=[],
        leaders=[],
        importance=1,                       # M3 enricher 会重写
        status="expected",
        source_url="https://data.eastmoney.com/gsrl/gsdt.html",
        payload={"事件类型": raw_type, "具体事项": content},
        ingested_at=None,                   # storage 层落库时盖上 CURRENT_TIMESTAMP
    )


def _iter_target_dates(start: date, days: int) -> Iterable[date]:
    """Yield each calendar date in [start, start + days). Calendar days, not
    trade days — gsdt returns empty rows on weekends, which is harmless and
    saves us from pulling a trade-day calendar just for this."""
    if days <= 0:
        raise ValueError("days must be > 0")
    for offset in range(days):
        yield start + timedelta(days=offset)


def run(
    *,
    date: str | None = None,
    days: int = 7,
    **_unused,
) -> list[ExpectedEvent]:
    """Pull ``[date, date+days)`` from the gsdt endpoint.

    Args:
        date:  YYYYMMDD or YYYY-MM-DD; default = today (local).
        days:  how many calendar days to fetch starting from ``date``. The
               adapter calls akshare once per day.

    Caller (service.run_adapter) handles persistence and replica swap.
    """
    start = _coerce_date(date) if date else _coerce_date(datetime.today().date())
    if start is None:
        raise ValueError(f"could not parse date={date!r}")

    events: list[ExpectedEvent] = []
    for target in _iter_target_dates(start, int(days)):
        ymd = _yyyymmdd(target)
        LOGGER.info("eventradar.gsrl_pull date=%s", ymd)
        try:
            df = fetch_dataframe(
                AKSHARE_FN,
                date=ymd,
                cache_key=f"{SOURCE}_{ymd}",
            )
        except AkshareCallError as exc:
            # Two real-world failure modes: (1) the upstream API returns
            # ``data: null`` on weekends / holidays / dates with zero
            # disclosures, which crashes akshare's ``data_json["result"]
            # ["data"]`` indexing — looks like ``'NoneType' object is not
            # subscriptable``; (2) actual network or rate-limit failures.
            # In both cases the right move is "skip this day, keep the
            # rest of the run going". Log the cause so weekends-vs-real-
            # outages stay debuggable.
            LOGGER.warning(
                "eventradar.gsrl_skip_day date=%s reason=%s", ymd, exc
            )
            continue

        if df is None or df.empty:
            LOGGER.info("eventradar.gsrl_empty date=%s", ymd)
            continue

        missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            # Adapter contract is "never silently drop" — this is the kind
            # of upstream change we want to scream about.
            raise RuntimeError(
                f"akshare {AKSHARE_FN} 缺少预期列 {missing}; got {list(df.columns)}"
            )

        before = len(events)
        for _, row in df.iterrows():
            event = _row_to_event(row, target)
            if event is not None:
                events.append(event)
        LOGGER.info(
            "eventradar.gsrl_parsed date=%s rows=%d kept=%d",
            ymd, len(df), len(events) - before,
        )

    return events


# Self-register into the global adapter table. Importing this module makes
# `eventradar pull company_calendar_em` work.
ADAPTERS["company_calendar_em"] = AdapterSpec(
    name="company_calendar_em",
    description="东方财富股市日历-公司动态 (stock_gsrl_gsdt_em)",
    run=run,
)
