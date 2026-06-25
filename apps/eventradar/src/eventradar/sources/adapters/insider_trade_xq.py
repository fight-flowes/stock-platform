"""雪球 - 沪深股市 - 内部交易 (``stock_inner_trade_xq``).

The first 雪球 source — and the first "insider behavior" signal in
eventradar. 董监高增减持 are strong price precursors: insiders often trade
ahead of news the market hasn't priced in yet.

Upstream contract (verified akshare 1.18.49):
    - No params, no token required (unlike the *_basic_info_xq family).
    - Returns ~22000 rows of insider trades across all A-shares, rolling
      ~18 months back.
    - Columns: 股票代码 (SH600519 / SZ000001 / sometimes NaN), 股票名称,
      变动日期, 变动人, 变动股数 (signed: +增持 / -减持), 成交均价,
      变动后持股数, 与董监高关系, 董监高职务.

Honest data note:
    These are **disclosed-after-the-fact** events (变动日期 is the trade
    date, all in the past). They aren't "expected_at = future" the way WSC
    macro events are. Their value is as a *signal*: a cluster of insider
    sells at a stock often precedes a drawdown; insider buys are a
    credibility vote. So even though the dates are past, surfacing them
    alongside forward-looking events gives the user "what insiders just
    did" context for the stocks they're watching.

Event granularity:
    One row → one ExpectedEvent. Same stock + same day can have several
    rows (different 变动人) — each is its own event. Fingerprint =
    (code, 变动日期, 变动人, 变动股数) so re-pulls update in place and
    distinct insiders on the same day stay distinct.

Stock code normalization:
    雪球 returns "SH600519" / "SZ000001". stock_meta (and our events'
    stock_codes JSON) keys on the bare numeric code "600519". We strip
    the exchange prefix on the way in. Rows where 股票代码 is NaN (雪球
    occasionally emits name-only rows for obscure tickers) are skipped
    with a debug log — we can't map them to industries/leaders without a
    code, so they'd be unenrichable noise.

event_type = "insider_trade" (single type; direction 增/减 lives in
event_name + payload). Keeps the type enum small and lets the frontend
tag-color all insider activity uniformly; users who want only sells can
keyword-filter "减持".
"""

from __future__ import annotations

import logging
from datetime import date, datetime

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

SOURCE = "xq_insider"
AKSHARE_FN = "stock_inner_trade_xq"

_REQUIRED_COLUMNS: tuple[str, ...] = (
    "股票代码", "股票名称", "变动日期", "变动人",
    "变动股数", "成交均价", "变动后持股数", "与董监高关系", "董监高职务",
)


def _coerce_date(value) -> date | None:
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


def _strip_exchange_prefix(code: str) -> str:
    """雪球 'SH600519' / 'SZ000001' → bare '600519'."""
    text = (code or "").strip().upper()
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and len(text) > len(prefix):
            return text[len(prefix):]
    return text


def _row_to_event(row: pd.Series) -> ExpectedEvent | None:
    raw_code = row.get("股票代码")
    # 雪球 occasionally emits name-only rows (code is NaN). Without a code
    # we can't enrich industry/leader, and the detail dialog would show a
    # blank ticker — skip these. Debug-level because they're routine.
    if raw_code is None or (isinstance(raw_code, float) and pd.isna(raw_code)):
        return None

    code = _strip_exchange_prefix(str(raw_code))
    name = str(row.get("股票名称") or "").strip()
    if not code:
        return None

    trade_date = _coerce_date(row.get("变动日期"))
    if trade_date is None:
        return None

    trader = str(row.get("变动人") or "").strip()
    shares = row.get("变动股数")
    price = row.get("成交均价")
    after_holding = row.get("变动后持股数")
    relation = str(row.get("与董监高关系") or "").strip()
    title = str(row.get("董监高职务") or "").strip()

    # Direction from sign of 变动股数. NaN shares → skip (can't classify).
    if shares is None or (isinstance(shares, float) and pd.isna(shares)):
        return None
    try:
        shares_int = int(shares)
    except (TypeError, ValueError):
        return None
    direction = "增持" if shares_int > 0 else "减持" if shares_int < 0 else "变动"

    fingerprint = build_source_fingerprint(
        (code, trade_date.isoformat(), trader, str(shares_int))
    )
    event_id = build_event_id(SOURCE, fingerprint)

    event_name = f"{direction}-{name} {trader}".strip()

    content_parts = [
        f"股票: {name} ({code})",
        f"变动日期: {trade_date}",
        f"变动人: {trader}" + (f"（{title}）" if title else ""),
        f"变动方向: {direction}",
        f"变动股数: {abs(shares_int):,}",
    ]
    if price is not None and not (isinstance(price, float) and pd.isna(price)):
        content_parts.append(f"成交均价: {float(price):.2f}")
    if after_holding is not None and not (isinstance(after_holding, float) and pd.isna(after_holding)):
        content_parts.append(f"变动后持股: {float(after_holding):,.0f}")
    if relation:
        content_parts.append(f"与董监高关系: {relation}")
    event_content = "\n".join(content_parts)

    return ExpectedEvent(
        event_id=event_id,
        source=SOURCE,
        source_fingerprint=fingerprint,
        event_type="insider_trade",
        event_name=event_name,
        event_scope="stock",
        scope_reason="董监高增减持",
        event_content=event_content,
        expected_at=trade_date,
        expected_at_end=None,
        time_certainty="confirmed_date",
        stock_codes=[ExpectedEventStock(stock_code=code, stock_name=name)],
        industries=[],
        themes=[],
        leaders=[],
        # 增持 is mildly positive, 减持 mildly negative — but importance is
        # about visibility, not direction. Base 1; the enricher may bump
        # if the stock is a leader (large insider moves at bellwethers
        # move sectors). Keep adapter neutral on direction.
        importance=1,
        status="expected",
        source_url="https://xueqiu.com/snowman/S/" + str(raw_code).upper(),
        payload={
            "stock_code": code,
            "stock_name": name,
            "变动日期": trade_date.isoformat(),
            "变动人": trader,
            "变动方向": direction,
            "变动股数": shares_int,
            "成交均价": None if (price is None or (isinstance(price, float) and pd.isna(price))) else float(price),
            "变动后持股数": None if (after_holding is None or (isinstance(after_holding, float) and pd.isna(after_holding))) else float(after_holding),
            "与董监高关系": relation,
            "董监高职务": title,
        },
        ingested_at=None,
    )


def run(**_unused) -> list[ExpectedEvent]:
    """Pull the full insider-trade feed from 雪球.

    No params. Returns ~22000 rows covering the last ~18 months. Re-pulls
    are idempotent — same (code, date, trader, shares) fingerprints update
    in place. The upstream rolls old rows off as new ones come in, so
    re-running periodically keeps the window fresh without manual cleanup.
    """
    LOGGER.info("eventradar.insider_xq_pull start")
    try:
        df = fetch_dataframe(
            AKSHARE_FN,
            cache_key=f"{SOURCE}_latest",
        )
    except AkshareCallError as exc:
        LOGGER.warning("eventradar.insider_xq_fail reason=%s", exc)
        return []

    if df is None or df.empty:
        LOGGER.info("eventradar.insider_xq_empty")
        return []

    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise RuntimeError(
            f"akshare {AKSHARE_FN} 缺少预期列 {missing}; got {list(df.columns)}"
        )

    events: list[ExpectedEvent] = []
    skipped_nan_code = 0
    for _, row in df.iterrows():
        event = _row_to_event(row)
        if event is not None:
            events.append(event)
        else:
            skipped_nan_code += 1
    LOGGER.info(
        "eventradar.insider_xq_parsed rows=%d kept=%d skipped=%d",
        len(df), len(events), skipped_nan_code,
    )
    return events


ADAPTERS["insider_trade_xq"] = AdapterSpec(
    name="insider_trade_xq",
    description="雪球-内部交易 (stock_inner_trade_xq, 董监高增减持)",
    run=run,
)
