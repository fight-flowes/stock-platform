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

The list below is the M1+M2 target. Files are placeholder-only at this
stage — each one lands with its own PR.
"""

# Adapters will register themselves here as they land. Today the package is
# empty on purpose; importing eventradar.sources.adapters is a no-op.

__all__: list[str] = []
