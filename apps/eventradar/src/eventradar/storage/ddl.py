"""DuckDB DDL for eventradar.

The single source of truth for the schema. Both the writer (CLI ingestion
jobs) and the reader (FastAPI server) call :func:`apply_ddl` on connect, so
schema migrations are as simple as adding new statements here.

Field naming aligns with :class:`eventradar.normalize.schemas.ExpectedEvent`
and ``calenderapp``'s ``EventradarProxyService._normalize_announcement``.
Column types match upstream — JSON columns hold the nested lists so we don't
need a second table for stocks/industries/themes at this scale.
"""

from __future__ import annotations

import duckdb


# One statement per CREATE so a partial failure surfaces a clear error.
# DuckDB executes each independently; ``IF NOT EXISTS`` makes the call
# idempotent — safe to run on every connection.
DDL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS expected_events (
        event_id            VARCHAR PRIMARY KEY,
        source              VARCHAR NOT NULL,
        source_fingerprint  VARCHAR NOT NULL,
        event_type          VARCHAR NOT NULL,
        event_name          VARCHAR,
        event_scope         VARCHAR,
        scope_reason        VARCHAR,
        event_content       TEXT,
        expected_at         DATE,
        expected_at_end     DATE,
        time_certainty      VARCHAR,
        importance          INTEGER DEFAULT 1,
        stock_codes         JSON,
        industries          JSON,
        themes              JSON,
        leaders             JSON,
        source_url          VARCHAR,
        payload             JSON,
        status              VARCHAR DEFAULT 'expected',
        ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # The (source, fingerprint) pair must be unique — that's our cross-pull
    # dedupe key. Declared as a unique index instead of a column constraint
    # so it can be dropped/rebuilt without rewriting the table.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_expected_events_src_fp
        ON expected_events(source, source_fingerprint)
    """,
    "CREATE INDEX IF NOT EXISTS idx_ee_expected_at ON expected_events(expected_at)",
    "CREATE INDEX IF NOT EXISTS idx_ee_event_type  ON expected_events(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_ee_event_scope ON expected_events(event_scope)",
    "CREATE INDEX IF NOT EXISTS idx_ee_status      ON expected_events(status)",
)


def apply_ddl(conn: duckdb.DuckDBPyConnection) -> None:
    """Run every DDL statement on the given connection."""
    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)
