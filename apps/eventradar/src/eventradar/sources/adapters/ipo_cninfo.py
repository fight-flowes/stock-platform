"""巨潮资讯 - 新股申购 (``stock_new_ipo_cninfo``).

The first 巨潮 source in eventradar — and the first source whose events are
genuinely *point-in-time future* for IPOs in their申购→中签→缴款→上市 pipeline.

Upstream contract (verified with akshare 1.18.49):
    - No params — returns the current IPO pipeline as one DataFrame (~440 rows).
    - Columns: 证劵代码, 证券简称, 上市日期, 申购日期, 发行价, 总发行数量,
      发行市盈率, 上网发行中签率, 摇号结果公告日, 中签公告日, 中签缴款日,
      网上申购上限, 上网发行数量.
    - Dates are mixed past/future: an IPO in mid-pipeline has 申购日期 past
      but 中签缴款日 / 上市日期 still future. The adapter keeps ALL of them —
      past dates are useful for "this IPO's timeline so far", future dates
      are the actual forward-looking events.

Event expansion strategy:
    One新股 row → up to 4 ExpectedEvent rows, one per meaningful date:
        申购日期      → event_type="ipo_subscribe"
        中签公告日    → event_type="ipo_lottery"   (中签公布)
        中签缴款日    → event_type="ipo_payment"   (缴款)
        上市日期      → event_type="ipo_listing"
    摇号结果公告日 is skipped — it's almost always the same day as 中签公告日
    and adds noise. If you ever want it, add a 5th tuple below.

Each event carries the full IPO context (发行价/市盈率/中签率) in
``payload`` so the detail dialog can show the whole picture, even though
the row itself is one milestone.

Fingerprint = (stock_code, milestone_type) — stable across re-pulls. When
巨潮 updates a date (e.g. 上市日期 gets filled in after 申购), the upsert's
ON CONFLICT updates ``expected_at`` in place.

expected_at = the milestone's date. ``event_scope="stock"`` (each IPO binds
to one ticker). ``importance=1`` base — IPO 上市 gets +1 from importance_rules
because ipo_listing isn't currently in HIGH_IMPACT_TYPES but 申购/缴款 are
low-impact individually; the enricher's type-bonus handles calibration.
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

SOURCE = "cninfo_ipo"
AKSHARE_FN = "stock_new_ipo_cninfo"

# One新股 row expands into one event per milestone in this list. Order is
# the natural IPO timeline. Tuple = (column_name, event_type, event_name).
# Skipping 摇号结果公告日 — overlaps with 中签公告日.
_MILESTONES: tuple[tuple[str, str, str], ...] = (
    ("申购日期", "ipo_subscribe", "新股申购"),
    ("中签公告日", "ipo_lottery", "中签公告"),
    ("中签缴款日", "ipo_payment", "中签缴款"),
    ("上市日期", "ipo_listing", "新股上市"),
)

_REQUIRED_COLUMNS: tuple[str, ...] = ("证劵代码", "证券简称") + tuple(m[0] for m in _MILESTONES)


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


def _fmt_num(value, fmt="{:,.2f}") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        return fmt.format(float(value))
    except (TypeError, ValueError):
        return str(value)


def _row_to_events(row: pd.Series) -> list[ExpectedEvent]:
    """Expand one新股 row into 0-4 milestone events.

    Returns fewer than 4 when some dates are NaT (e.g. 上市日期 not yet
    announced for an IPO still in申购 phase).
    """
    code = str(row.get("证劵代码") or "").strip()
    name = str(row.get("证券简称") or "").strip()
    if not code:
        return []

    # Shared context — same for every milestone of this IPO.
    price = row.get("发行价")
    pe = row.get("发行市盈率")
    lottery_rate = row.get("上网发行中签率")
    total_qty = row.get("总发行数量")
    context_lines = [
        f"证券简称: {name}",
        f"发行价: {_fmt_num(price)} 元" if pd.notna(price) else "",
        f"发行市盈率: {_fmt_num(pe)}" if pd.notna(pe) else "",
        f"上网发行中签率: {_fmt_num(lottery_rate, '{:.4%}')}" if pd.notna(lottery_rate) else "",
        f"总发行数量: {_fmt_num(total_qty, '{:,.0f}')}" if pd.notna(total_qty) else "",
    ]
    context = "\n".join(line for line in context_lines if line)
    payload = {
        "stock_code": code,
        "stock_name": name,
        "发行价": None if pd.isna(price) else float(price),
        "发行市盈率": None if pd.isna(pe) else float(pe),
        "中签率": None if pd.isna(lottery_rate) else float(lottery_rate),
        "总发行数量": None if pd.isna(total_qty) else float(total_qty),
    }

    events: list[ExpectedEvent] = []
    for col, event_type, event_name in _MILESTONES:
        milestone_date = _coerce_date(row.get(col))
        if milestone_date is None:
            # Milestone not yet scheduled — skip. Will appear on a future
            # pull once巨潮 fills the date in.
            continue
        fingerprint = build_source_fingerprint((code, event_type))
        event_id = build_event_id(SOURCE, fingerprint)
        events.append(
            ExpectedEvent(
                event_id=event_id,
                source=SOURCE,
                source_fingerprint=fingerprint,
                event_type=event_type,
                event_name=f"{event_name}-{name}",
                event_scope="stock",
                scope_reason="新股申购流程",
                event_content=context,
                expected_at=milestone_date,
                expected_at_end=None,
                time_certainty="confirmed_date",
                stock_codes=[ExpectedEventStock(stock_code=code, stock_name=name)],
                industries=[],
                themes=[],
                leaders=[],
                importance=1,
                status="expected",
                source_url="http://www.cninfo.com.cn/new/disclosure/stock?stockCode=" + code,
                payload=payload,
                ingested_at=None,
            )
        )
    return events


def run(**_unused) -> list[ExpectedEvent]:
    """Pull the current新股 pipeline from巨潮 and expand into milestone events.

    No params — the upstream takes none. Re-pulling is idempotent: same
    (stock_code, milestone_type) fingerprints update in place; new IPOs
    enter the pipeline, completed IPOs drop their past milestones (the
    upstream rolls them off after上市).
    """
    LOGGER.info("eventradar.ipo_cninfo_pull start")
    try:
        df = fetch_dataframe(
            AKSHARE_FN,
            cache_key=f"{SOURCE}_latest",
        )
    except AkshareCallError as exc:
        LOGGER.warning("eventradar.ipo_cninfo_fail reason=%s", exc)
        return []

    if df is None or df.empty:
        LOGGER.info("eventradar.ipo_cninfo_empty")
        return []

    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise RuntimeError(
            f"akshare {AKSHARE_FN} 缺少预期列 {missing}; got {list(df.columns)}"
        )

    events: list[ExpectedEvent] = []
    for _, row in df.iterrows():
        events.extend(_row_to_events(row))
    LOGGER.info(
        "eventradar.ipo_cninfo_parsed ipos=%d events=%d", len(df), len(events)
    )
    return events


ADAPTERS["ipo_cninfo"] = AdapterSpec(
    name="ipo_cninfo",
    description="巨潮资讯-新股申购 (stock_new_ipo_cninfo)",
    run=run,
)
