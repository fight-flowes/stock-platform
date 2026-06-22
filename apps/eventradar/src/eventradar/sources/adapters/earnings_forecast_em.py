"""东方财富 - 数据中心 - 年报季报 - 业绩预告 (``stock_yjyg_em``).

The first genuinely *forward-looking* source in eventradar. Unlike the gsdt
feed (which discloses things that already happened), a 业绩预告 tells the
market what a company *expects* its results to be for a future reporting
period — pre-增/首亏/扭亏/续亏 are strong price catalysts.

Upstream semantics (verified akshare 1.18.49):
    - ``date`` param is the **report period** (报告期), e.g. "20251231" =
      the 2025 annual report. NOT a calendar window. One call returns every
      company that has issued a forecast for that report period.
    - A single (报告期, 股票代码) can yield several rows — one per
      预测指标 (归母净利润 / 扣非净利润 / 营业收入 / ...). Each is a
      distinct signal, so we keep them as separate events.

Field mapping decisions (confirmed with the user):
    - ``expected_at`` = **报告期** (the future date the forecast is about).
      This makes the event genuinely "expected" — it's the date whose
      results are being predicted. ``公告日期`` (when the company filed the
      forecast) goes into ``event_content`` / ``payload`` for context.
    - Because every event for a report period shares the same ``expected_at``,
      list sorting falls back to ``event_id`` (stable) — the API caller can
      also sort by ``importance`` to surface high-impact forecasts first.
    - ``time_certainty`` = ``confirmed_date`` (报告期 is a fixed calendar
      date, not a rumor).
    - ``event_type`` = ``earnings_forecast`` (already in the canonical enum).
    - ``event_name`` = ``f"{预告类型}-{预测指标}"`` (e.g. "预增-归母净利润")
      so the UI shows the catalyst type at a glance.
    - ``event_content`` = human-readable summary: 公告日期, 预告类型, 业绩变动,
      预测数值, 业绩变动幅度, 业绩变动原因.
    - ``importance`` base 1 here; the enricher bumps it because
      ``earnings_forecast`` is in HIGH_IMPACT_TYPES, and 首亏/扭亏/预增 with
      large 幅度 will read as high importance once an earnings-specific
      rule is added. For now the generic type-rule gives +1.

Fingerprint = (报告期, 股票代码, 预告类型, 预测指标, 业绩变动幅度) — wide
enough that re-pulling the same report period is idempotent, narrow enough
that the same stock's different 指标 rows stay distinct.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Iterable

import pandas as pd

from ..akshare_client import AkshareCallError, fetch_dataframe
from ...normalize import (
    ExpectedEvent,
    ExpectedEventStock,
    build_event_id,
    build_source_fingerprint,
)
from ...service import ADAPTERS, AdapterSpec

LOGGER = logging.getLogger(__name__)

SOURCE = "em_yjyg"
AKSHARE_FN = "stock_yjyg_em"

# akshare returns these columns after its own rename pass.
_REQUIRED_COLUMNS: tuple[str, ...] = (
    "股票代码",
    "股票简称",
    "预测指标",
    "业绩变动",
    "预测数值",
    "业绩变动幅度",
    "业绩变动原因",
    "预告类型",
    "公告日期",
)


def _coerce_date(value) -> date | None:
    """Parse akshare's 公告日期 (already coerced to date by akshare, but be
    defensive — accept str/datetime/Timestamp too)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
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


def _report_period_to_date(period: str) -> date:
    """Turn a report-period string like '20251231' into a date.

    Report periods are always quarter-ends (MMDD ∈ {0331,0630,0930,1231}),
    so YYYYMMDD is unambiguous. We validate strictly — a bogus period should
    fail loudly rather than silently land on the wrong date.
    """
    text = str(period).strip()
    if "-" in text:
        text = text.replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"report period must be YYYYMMDD, got {period!r}")
    return datetime.strptime(text, "%Y%m%d").date()


def _fmt_change幅度(幅度) -> str:
    """Render 业绩变动幅度 (a percentage like 93.51 or -317.575) for display."""
    if pd.isna(幅度):
        return ""
    try:
        return f"{float(幅度):+.1f}%"
    except (TypeError, ValueError):
        return str(幅度)


def _row_to_event(row: pd.Series, report_date: date) -> ExpectedEvent | None:
    code = str(row.get("股票代码") or "").strip()
    name = str(row.get("股票简称") or "").strip()
    indicator = str(row.get("预测指标") or "").strip()
    forecast_type = str(row.get("预告类型") or "").strip()
    change = str(row.get("业绩变动") or "").strip()
    reason = str(row.get("业绩变动原因") or "").strip()
    幅度 = row.get("业绩变动幅度")
    predict_value = row.get("预测数值")
    notice_date = _coerce_date(row.get("公告日期"))

    if not code or not forecast_type:
        # Adapter contract: never silently drop, but a row with no code or
        # no type isn't a usable event. Log at debug — akshare occasionally
        # returns sparse rows and warning-per-row would flood the log.
        LOGGER.debug(
            "eventradar.yjyg_skip_row code=%s type=%s indicator=%s",
            code, forecast_type, indicator,
        )
        return None

    # Fingerprint includes 指标 + 幅度 so a stock's 归母净利 / 扣非 / 营收
    # rows stay distinct, and a re-issued forecast (same 指标, new 幅度)
    # updates the row rather than creating a duplicate.
    fingerprint = build_source_fingerprint(
        (report_date.isoformat(), code, forecast_type, indicator, _fmt_change幅度(幅度))
    )
    event_id = build_event_id(SOURCE, fingerprint)

    event_name = f"{forecast_type}-{indicator}" if indicator else forecast_type

    content_parts = [
        f"公告日期: {notice_date}" if notice_date else "",
        f"预告类型: {forecast_type}",
        f"预测指标: {indicator}" if indicator else "",
        f"业绩变动: {change}" if change else "",
        f"变动幅度: {_fmt_change幅度(幅度)}" if not pd.isna(幅度) else "",
        f"预测数值: {predict_value}" if not pd.isna(predict_value) else "",
        f"业绩变动原因: {reason}" if reason else "",
    ]
    event_content = "\n".join(p for p in content_parts if p)

    return ExpectedEvent(
        event_id=event_id,
        source=SOURCE,
        source_fingerprint=fingerprint,
        event_type="earnings_forecast",
        event_name=event_name,
        event_scope="stock",
        scope_reason="业绩预告-个股",
        event_content=event_content,
        expected_at=report_date,
        expected_at_end=None,
        time_certainty="confirmed_date",
        stock_codes=[ExpectedEventStock(stock_code=code, stock_name=name)],
        industries=[],
        themes=[],
        leaders=[],
        importance=1,  # enricher adds +1 because earnings_forecast is high-impact
        status="expected",
        source_url="https://data.eastmoney.com/bbsj/202512/yjyg.html",
        payload={
            "报告期": report_date.isoformat(),
            "公告日期": notice_date.isoformat() if notice_date else "",
            "预告类型": forecast_type,
            "预测指标": indicator,
            "业绩变动": change,
            "业绩变动幅度": None if pd.isna(幅度) else float(幅度),
            "预测数值": None if pd.isna(predict_value) else float(predict_value),
            "业绩变动原因": reason,
        },
        ingested_at=None,
    )


def _report_periods_for_lookback(quarters: int, today: date | None = None) -> list[str]:
    """Yield the most recent ``quarters`` report periods as YYYYMMDD strings.

    Report periods end on 03-31 / 06-30 / 09-30 / 12-31. We walk backwards
    from the current quarter so a cron run always pulls the periods that are
    *due to be forecast* right now (the just-ended quarter + the prior one,
    since companies pre-announce across a window).
    """
    today = today or datetime.today().date()
    quarter_ends = [(3, 31), (6, 30), (9, 30), (12, 31)]
    # Find the most recent quarter-end <= today.
    periods: list[str] = []
    year = today.year
    # Build a descending list of (year, month, day) quarter-ends from today.
    # Start from the quarter that contains today, walking back.
    idx = 0
    for i, (m, d) in enumerate(quarter_ends):
        if (today.month, today.day) >= (m, d):
            idx = i
    y, m, d = year, quarter_ends[idx][0], quarter_ends[idx][1]
    for _ in range(quarters):
        periods.append(f"{y:04d}{m:02d}{d:02d}")
        idx -= 1
        if idx < 0:
            idx = 3
            y -= 1
        m, d = quarter_ends[idx]
    return periods


def run(
    *,
    date: str | None = None,
    quarters: int = 2,
    **_unused,
) -> list[ExpectedEvent]:
    """Pull 业绩预告 for one or more report periods.

    Args:
        date:     a single report period YYYYMMDD (e.g. "20251231"). When
                  given, only that period is pulled.
        quarters: how many most-recent report periods to pull (default 2 —
                  the just-ended quarter plus the prior one, which covers
                  the active forecasting window). Ignored when ``date`` is
                  given.

    Caller (service.run_adapter) handles persistence and replica swap.
    """
    if date:
        periods = [str(date).strip()]
        report_dates = [_report_period_to_date(periods[0])]
    else:
        periods = _report_periods_for_lookback(int(quarters))
        report_dates = [_report_period_to_date(p) for p in periods]

    events: list[ExpectedEvent] = []
    for period, report_date in zip(periods, report_dates):
        LOGGER.info("eventradar.yjyg_pull period=%s", period)
        try:
            df = fetch_dataframe(
                AKSHARE_FN,
                date=period,
                cache_key=f"{SOURCE}_{period}",
            )
        except AkshareCallError as exc:
            LOGGER.warning("eventradar.yjyg_skip_period period=%s reason=%s", period, exc)
            continue

        if df is None or df.empty:
            LOGGER.info("eventradar.yjyg_empty period=%s", period)
            continue

        missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise RuntimeError(
                f"akshare {AKSHARE_FN} 缺少预期列 {missing}; got {list(df.columns)}"
            )

        before = len(events)
        for _, row in df.iterrows():
            event = _row_to_event(row, report_date)
            if event is not None:
                events.append(event)
        LOGGER.info(
            "eventradar.yjyg_parsed period=%s rows=%d kept=%d",
            period, len(df), len(events) - before,
        )

    return events


ADAPTERS["earnings_forecast_em"] = AdapterSpec(
    name="earnings_forecast_em",
    description="东方财富年报季报-业绩预告 (stock_yjyg_em)",
    run=run,
)
