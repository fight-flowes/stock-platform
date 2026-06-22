"""Mark which of an event's stocks are market-cap 龙头 (leaders).

Leader signal = float market cap (流通市值) ≥ a configurable threshold
(default 500 亿). Source-agnostic — works identically for gsdt events and
any future M2 source. We deliberately do *not* reuse calenderapp's
``is_dragon_head`` (涨停龙虎) here: that signal is per-limit-up-date and
semantically different from "large-cap bellwether", and pulling it in would
couple eventradar to calenderapp's HTTP API. Market cap is the simpler,
self-contained choice; calenderapp dragon-head can be layered on later as
an additive signal if needed.

Like :mod:`industry_mapper` this is a pure lookup over the ``stock_meta``
cache — no network. Missing cache rows just don't get marked.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from ...config import get_settings


def score_leaders(
    stock_codes: Iterable[Mapping[str, str]],
    stock_meta: Mapping[str, Mapping[str, object]],
    *,
    threshold: float | None = None,
) -> tuple[list[dict[str, str]], bool]:
    """Return ``(leaders, has_leader)``.

    ``leaders`` is the subset of ``stock_codes`` whose float market cap is
    at or above ``threshold`` (defaults to ``settings.leader_float_mv_threshold``).
    ``has_leader`` is a convenience flag for the importance rules.

    A leader entry carries ``stock_code`` + ``stock_name`` so the API can
    render it without a second lookup.
    """
    if threshold is None:
        threshold = get_settings().leader_float_mv_threshold

    leaders: list[dict[str, str]] = []
    for stock in stock_codes:
        code = str(stock.get("stock_code") or "").strip()
        if not code:
            continue
        meta = stock_meta.get(code)
        if not meta:
            continue
        float_mv = meta.get("float_market_cap")
        if float_mv is None:
            continue
        try:
            if float(float_mv) >= threshold:
                leaders.append(
                    {
                        "stock_code": code,
                        "stock_name": str(stock.get("stock_name") or meta.get("stock_name") or ""),
                    }
                )
        except (TypeError, ValueError):
            continue
    return leaders, bool(leaders)
