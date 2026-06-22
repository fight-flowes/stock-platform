"""Map an event's stock codes → industry tags via the ``stock_meta`` cache.

Pure lookup — no akshare, no network. The cache is populated upstream by
``service.refresh_stock_meta`` (which calls ``stock_individual_info_em``).
If a stock isn't in the cache yet its industry is simply omitted; the
enrich pass degrades gracefully rather than blocking on a missing row.

For the gsdt feed every event is single-stock, so ``industries`` ends up
with 0 or 1 elements. The list shape is preserved so multi-stock events
(M2 macro/industry sources may attach several) dedupe correctly.
"""

from __future__ import annotations

from typing import Iterable, Mapping


def map_industries(
    stock_codes: Iterable[Mapping[str, str]],
    stock_meta: Mapping[str, Mapping[str, object]],
) -> list[str]:
    """Return a de-duplicated list of industry tags for the given stocks.

    Args:
        stock_codes: each item has ``stock_code`` (and maybe ``stock_name``).
        stock_meta: ``{stock_code: {"industry": str, ...}}`` — the cache slice
                    relevant to this event, pre-fetched by the caller.

    Industries are lower-cased? No — kept as-is from the upstream (东财行业名
    like "房地产开发", "半导体"), so filter values match exactly.
    """
    seen: set[str] = set()
    industries: list[str] = []
    for stock in stock_codes:
        code = str(stock.get("stock_code") or "").strip()
        if not code:
            continue
        meta = stock_meta.get(code)
        if not meta:
            continue
        industry = str(meta.get("industry") or "").strip()
        if not industry or industry in seen:
            continue
        seen.add(industry)
        industries.append(industry)
    return industries
