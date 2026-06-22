"""Enrichment helpers — pure functions that fill the four enrichment
dimensions (industries / leaders / importance / expected_at_end) for an
ExpectedEvent using the ``stock_meta`` cache + the event's own text.

None of these touch DuckDB or akshare. The orchestration (reading rows,
fetching the stock_meta slice, writing back) lives in
:meth:`eventradar.service.EventradarService.enrich_events`.
"""

from .future_date_parser import parse_future_date
from .importance_rules import HIGH_IMPACT_TYPES, IMMINENCE_WINDOW_DAYS, compute_importance
from .industry_mapper import map_industries
from .leader_scorer import score_leaders

__all__ = [
    "parse_future_date",
    "map_industries",
    "score_leaders",
    "compute_importance",
    "HIGH_IMPACT_TYPES",
    "IMMINENCE_WINDOW_DAYS",
]
