"""Adapters convert one akshare endpoint's DataFrame into ExpectedEvent rows.

Each adapter is a single file with one public ``run(...)`` function that:

    1. Calls :func:`eventradar.sources.akshare_client.fetch_dataframe` for
       its endpoint.
    2. Iterates the rows, mapping each to an :class:`ExpectedEvent`.
    3. Returns the list. Persistence is the caller's job (CLI / pipeline).

Adapters MUST NOT touch DuckDB. Adapters MUST NOT silently drop rows — if
a row fails to parse, log it and skip just that row. Use
:func:`eventradar.normalize.event_type_map.map_event_type` for the type
column; never invent new enum values inline.

Importing this package side-effect-registers every adapter into
``eventradar.service.ADAPTERS``.
"""

# Importing the module is what registers the adapter into the global
# ADAPTERS table — see the bottom of each adapter file.
from . import company_calendar_em  # noqa: F401
from . import earnings_forecast_em  # noqa: F401
from . import macro_calendar_ws  # noqa: F401
from . import ipo_cninfo  # noqa: F401
from . import insider_trade_xq  # noqa: F401

__all__ = [
    "company_calendar_em",
    "earnings_forecast_em",
    "macro_calendar_ws",
    "ipo_cninfo",
    "insider_trade_xq",
]
