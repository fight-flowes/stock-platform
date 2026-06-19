"""DuckDB persistence — primary writer + read-only replica publisher.

Concurrency model: the CLI ingestion jobs open the primary file in
read-write mode, do their upserts, and then call :func:`publish_replica`
which atomically swaps the read-only file the FastAPI server is serving
from. Readers never see a half-written DB; writers never block readers.
This is the "方案 A 只读副本" we agreed on.

DuckDB itself is not multi-writer-safe; if you ever run two CLI jobs at the
same time they'll race on the primary file. For now the cron schedule is
sparse enough (one ingestion per source per day) that we don't need a file
lock — add :mod:`portalocker` here if that changes.

This module is **placeholder-grade**: ``upsert_events`` and ``list_events``
are signatures-only so the rest of the skeleton compiles. Wire up the real
SQL in M1 alongside the first adapter.
"""

from __future__ import annotations

import logging
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

import duckdb

from ..config import Settings, get_settings
from ..normalize import ExpectedEvent
from .ddl import apply_ddl

LOGGER = logging.getLogger(__name__)


@contextmanager
def open_primary(settings: Settings | None = None) -> Iterator[duckdb.DuckDBPyConnection]:
    """Read-write connection to the primary DuckDB file.

    Used by the CLI / ingestion jobs. ``apply_ddl`` is called on every
    connect, so schema is always at HEAD. The connection is closed on exit
    even when the caller raises.
    """
    settings = settings or get_settings()
    settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(settings.duckdb_path), read_only=False)
    try:
        apply_ddl(conn)
        yield conn
    finally:
        conn.close()


@contextmanager
def open_replica(settings: Settings | None = None) -> Iterator[duckdb.DuckDBPyConnection]:
    """Read-only connection to the replica file the API serves from.

    If the replica hasn't been published yet (first boot) we fall back to
    the primary in read-only mode. That keeps ``eventradar serve`` usable
    on a fresh install — empty rows but not a crash.
    """
    settings = settings or get_settings()
    target = settings.duckdb_read_path
    if not target.exists():
        target = settings.duckdb_path
    if not target.exists():
        # Bootstrap an empty primary so the API has something to open.
        target.parent.mkdir(parents=True, exist_ok=True)
        with open_primary(settings) as bootstrap:
            del bootstrap  # apply_ddl runs and the file is created
        target = settings.duckdb_path
    conn = duckdb.connect(str(target), read_only=True)
    try:
        yield conn
    finally:
        conn.close()


def publish_replica(settings: Settings | None = None) -> Path:
    """Swap the read-only replica with a fresh copy of the primary.

    Strategy: copy primary → ``<read_path>.tmp`` → rename onto ``<read_path>``.
    POSIX rename is atomic on the same filesystem, so an API reader either
    sees the old file or the new file, never a torn one. DuckDB does not
    cache file handles across connections, so the next ``open_replica``
    call picks up the new file automatically.

    Returns the path that was published (for logging).
    """
    settings = settings or get_settings()
    src = settings.duckdb_path
    dst = settings.duckdb_read_path
    if not src.exists():
        raise FileNotFoundError(f"primary duckdb not found: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(src, tmp)
    tmp.replace(dst)
    LOGGER.info("eventradar.publish_replica src=%s dst=%s", src, dst)
    return dst


# --- placeholder write/read API --------------------------------------------
#
# Real implementations land alongside the first adapter. Keeping the
# signatures stable now means the API and CLI layers don't need to change
# again later.


def upsert_events(
    conn: duckdb.DuckDBPyConnection,
    events: Iterable[ExpectedEvent],
) -> int:
    """Upsert ExpectedEvent rows by (source, source_fingerprint).

    Returns the number of rows written. Placeholder for M1 — adapter PR
    will fill this in with the actual ``INSERT ... ON CONFLICT`` SQL.
    """
    raise NotImplementedError("upsert_events lands with the first adapter (M1)")


def list_events(
    conn: duckdb.DuckDBPyConnection,
    *,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    filters: dict[str, Any],
) -> dict[str, Any]:
    """Paginated read for ``POST /events/expected``.

    Returns the same shape ``EventradarProxyService._normalize_announcement``
    expects: ``{items, count, total_count, page, page_size, sort_by, sort_order, has_more}``.
    """
    raise NotImplementedError("list_events lands with the API wiring (M1)")


def get_event(conn: duckdb.DuckDBPyConnection, event_id: str) -> dict[str, Any] | None:
    """Single-row fetch for ``GET /events/expected/{event_id}``."""
    raise NotImplementedError("get_event lands with the API wiring (M1)")


def filter_meta(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Distinct facet values for ``GET /events/expected/filters/meta``."""
    raise NotImplementedError("filter_meta lands with the API wiring (M1)")
