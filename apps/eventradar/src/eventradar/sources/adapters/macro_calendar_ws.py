"""华尔街见闻 - 财经日历 - 宏观 (``macro_info_ws``).

The first macro-scope source in eventradar — gives users actual
forward-looking economic events (LPR/CPI/PMI/央行会议/美联储议息 …) with
the upstream's own importance rating (1-4 stars). All entries carry a
specific UTC datetime, so this is the cleanest "expected event" source we
have so far: ``expected_at`` is literally when the event is scheduled.

Upstream contract (verified with akshare 1.18.49):
    - akshare's ``date=YYYYMMDD`` param represents a *single calendar day*
      window (it builds [date, date+1d) internally). So a multi-day pull
      means iterating dates the way the gsdt adapter already does.
    - Columns: 时间 (datetime str), 地区, 事件, 重要性 (1-4), 今值, 预期,
      前值, 链接. ``今值`` only populated after the event happens.
    - Empty days (weekends, holidays) make akshare crash with
      ``KeyError 'public_date'`` — its empty-response handling is missing.
      We catch and skip.

Field mapping:
    - ``expected_at``     = 时间 (just the date — DuckDB DATE column doesn't
                            store wall-clock time; the full timestamp lives
                            in ``payload['scheduled_at']`` for hour-level
                            sorting if anything ever needs it)
    - ``expected_at_end`` = same as ``expected_at`` (point-in-time events;
                            keeping end=None would make future-date filters
                            quietly miss them)
    - ``event_type``      = ``macro_data``
    - ``event_scope``     = ``macro``
    - ``event_name``      = ``"{地区} {事件}"`` (e.g. "中国 6月一年期LPR")
    - ``importance``      = upstream 重要性 (1-4) mapped to schema's (0-3)
                            via ``min(3, raw - 1)``. So 4-star events land
                            at importance=3 directly from the source — no
                            enricher needs to escalate them.
    - ``stock_codes``     = ``[]`` (macro events don't bind to stocks; the
                            enricher's leader/industry passes silently
                            no-op on these rows)

Fingerprint = (timestamp, 地区, 事件) — the wall-clock time and the event
title together uniquely identify a scheduled release; the upstream may
update 今值 after the fact and we want that to UPDATE the row, not
INSERT a duplicate. Re-pulling the same date is idempotent.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Iterable

import pandas as pd

from ..akshare_client import AkshareCallError, fetch_dataframe
from ...normalize import (
    ExpectedEvent,
    build_event_id,
    build_source_fingerprint,
)
from ...service import ADAPTERS, AdapterSpec

LOGGER = logging.getLogger(__name__)

SOURCE = "wallstreet_macro"
AKSHARE_FN = "macro_info_ws"

_REQUIRED_COLUMNS: tuple[str, ...] = ("时间", "地区", "事件", "重要性")


def _coerce_date(value) -> date | None:
    """Parse date-ish values; reject bare ints (same defensive logic as gsdt)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
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


def _yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _map_importance(raw) -> int:
    """Map upstream 重要性 (1-4) to our 0-3 schema.

    Upstream uses 1=lowest, 4=highest; we keep relative ordering by
    subtracting 1 and clamping. NaN / unknown → 1 (a neutral baseline that
    keeps the row visible).
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return 1
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 1
    return max(0, min(3, v - 1))


def _fmt_value(v) -> str:
    """Render an economic data point — keep numeric precision but strip
    trailing zeros that pandas adds when comparing to NaN."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        # Match the upstream's display: 1-2 decimals usually
        formatted = f"{v:.2f}".rstrip("0").rstrip(".")
        return formatted or "0"
    return str(v).strip()


def _row_to_event(row: pd.Series) -> ExpectedEvent | None:
    raw_time = row.get("时间")
    region = str(row.get("地区") or "").strip()
    title = str(row.get("事件") or "").strip()
    importance_raw = row.get("重要性")
    now_val = row.get("今值")
    expected_val = row.get("预期")
    prev_val = row.get("前值")
    link = str(row.get("链接") or "").strip()

    if not title or not region:
        # Row has no usable identity — skip without warning (akshare occasionally
        # emits header-noise rows; a per-row warning would flood the log).
        return None

    # Parse the timestamp to both a wall-clock string (for payload) and a
    # bare date (for the DATE column). The wall-clock part is what makes
    # this source genuinely point-in-time.
    try:
        ts = pd.to_datetime(raw_time, errors="raise")
    except (TypeError, ValueError):
        LOGGER.warning("eventradar.ws_skip_row reason=bad_time time=%r event=%s", raw_time, title)
        return None
    event_date = ts.date()
    scheduled_at = ts.strftime("%Y-%m-%d %H:%M:%S")

    fingerprint = build_source_fingerprint((scheduled_at, region, title))
    event_id = build_event_id(SOURCE, fingerprint)

    event_name = f"{region} {title}"

    content_parts = [
        f"时间: {scheduled_at}",
        f"地区: {region}",
        f"事件: {title}",
    ]
    fmt_now, fmt_exp, fmt_prev = _fmt_value(now_val), _fmt_value(expected_val), _fmt_value(prev_val)
    if fmt_now:
        content_parts.append(f"今值: {fmt_now}")
    if fmt_exp:
        content_parts.append(f"预期: {fmt_exp}")
    if fmt_prev:
        content_parts.append(f"前值: {fmt_prev}")
    event_content = "\n".join(content_parts)

    return ExpectedEvent(
        event_id=event_id,
        source=SOURCE,
        source_fingerprint=fingerprint,
        event_type="macro_data",
        event_name=event_name,
        event_scope="macro",
        scope_reason="宏观数据/事件",
        event_content=event_content,
        expected_at=event_date,
        # Point-in-time events: end == start so any future-window query that
        # uses expected_at_end's presence as "has a known end" sees them.
        expected_at_end=event_date,
        time_certainty="confirmed_date",
        # Macro events don't bind to stocks. The enricher's industry_mapper
        # and leader_scorer iterate an empty list and produce []/[] — exactly
        # what we want for scope=macro.
        stock_codes=[],
        industries=[],
        themes=[],
        leaders=[],
        importance=_map_importance(importance_raw),
        status="expected",
        source_url=link or "https://wallstreetcn.com/calendar",
        payload={
            "时间": raw_time if isinstance(raw_time, str) else scheduled_at,
            "scheduled_at": scheduled_at,
            "地区": region,
            "事件": title,
            "重要性": None if pd.isna(importance_raw) else int(importance_raw),
            "今值": None if pd.isna(now_val) else float(now_val),
            "预期": None if pd.isna(expected_val) else float(expected_val),
            "前值": None if pd.isna(prev_val) else float(prev_val),
            "链接": link,
        },
        ingested_at=None,
    )


def _iter_dates(start: date, days: int) -> Iterable[date]:
    if days <= 0:
        raise ValueError("days must be > 0")
    for offset in range(days):
        yield start + timedelta(days=offset)


def run(
    *,
    date: str | None = None,
    days: int = 14,
    **_unused,
) -> list[ExpectedEvent]:
    """Pull ``[date, date+days)`` from the wallstreetcn macro calendar.

    Args:
        date:  YYYYMMDD or YYYY-MM-DD; default = today (local). Each call
               to akshare is one calendar day, so a window of N days = N
               calls (each ~100ms in practice).
        days:  how many calendar days to pull. Default 14 — covers two
               weeks, which captures the next central-bank meeting at most
               markets and the next CPI/PMI release for the major economies.

    Caller (service.run_adapter) handles persistence and replica swap.
    """
    start = _coerce_date(date) if date else datetime.today().date()
    if start is None:
        raise ValueError(f"could not parse date={date!r}")

    events: list[ExpectedEvent] = []
    seen_event_ids: set[str] = set()
    for target in _iter_dates(start, int(days)):
        ymd = _yyyymmdd(target)
        LOGGER.info("eventradar.ws_pull date=%s", ymd)
        try:
            df = fetch_dataframe(
                AKSHARE_FN,
                date=ymd,
                cache_key=f"{SOURCE}_{ymd}",
            )
        except AkshareCallError as exc:
            # Upstream empty-response → akshare KeyError → wrapped in
            # AkshareCallError. Same failure mode as gsdt's weekend rows.
            # Skip the day, keep going.
            LOGGER.warning("eventradar.ws_skip_day date=%s reason=%s", ymd, exc)
            continue

        if df is None or df.empty:
            LOGGER.info("eventradar.ws_empty date=%s", ymd)
            continue

        missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise RuntimeError(
                f"akshare {AKSHARE_FN} 缺少预期列 {missing}; got {list(df.columns)}"
            )

        before = len(events)
        for _, row in df.iterrows():
            event = _row_to_event(row)
            if event is None:
                continue
            # Cross-day dedupe — WSC returns multi-day events ("全周事件",
            # forward-looking entries like "美联储下周决议") inside every
            # neighboring date's response. The fingerprint catches all of
            # them, but DuckDB would reject the batch on the duplicate
            # PK; dedupe in-memory before handing the batch off.
            if event.event_id in seen_event_ids:
                continue
            seen_event_ids.add(event.event_id)
            events.append(event)
        LOGGER.info(
            "eventradar.ws_parsed date=%s rows=%d kept=%d",
            ymd, len(df), len(events) - before,
        )

    return events


ADAPTERS["macro_calendar_ws"] = AdapterSpec(
    name="macro_calendar_ws",
    description="华尔街见闻宏观日历 (macro_info_ws)",
    run=run,
)
