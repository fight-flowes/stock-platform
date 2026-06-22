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
"""

from __future__ import annotations

import json
import logging
import shutil
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

import duckdb

from ..config import Settings, get_settings
from ..normalize import ExpectedEvent
from ..normalize.event_type_map import EVENT_TYPE_VALUES
from ..normalize.schemas import EVENT_SCOPE_VALUES
from .ddl import apply_ddl

LOGGER = logging.getLogger(__name__)

# Columns we read out of expected_events. Listing them explicitly keeps
# read paths stable even if the table grows new columns later.
_SELECT_COLUMNS = (
    "event_id, source, source_fingerprint, event_type, event_name, "
    "event_scope, scope_reason, event_content, expected_at, expected_at_end, "
    "time_certainty, importance, stock_codes, industries, themes, leaders, "
    "source_url, payload, status, ingested_at"
)

# Whitelist for ``sort_by`` to keep the ORDER BY clause injection-safe. If
# the API asks for an unlisted column we silently fall back to expected_at.
_SORTABLE_COLUMNS = {
    "expected_at",
    "ingested_at",
    "importance",
    "event_type",
    "event_scope",
}


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
        with open_primary(settings):
            pass  # apply_ddl runs and the file is created
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


# --- write path ------------------------------------------------------------


def _event_to_row(event: ExpectedEvent) -> tuple:
    """Flatten an ExpectedEvent into the parameter tuple for INSERT.

    Order MUST match the column list in ``upsert_events``'s SQL. Lists of
    nested dataclasses get JSON-serialized — DuckDB has a JSON type, and
    storing as JSON avoids needing a second table at this scale.
    """
    return (
        event.event_id,
        event.source,
        event.source_fingerprint,
        event.event_type,
        event.event_name,
        event.event_scope,
        event.scope_reason,
        event.event_content,
        event.expected_at,
        event.expected_at_end,
        event.time_certainty,
        int(event.importance),
        json.dumps([s.to_dict() for s in event.stock_codes], ensure_ascii=False),
        json.dumps(list(event.industries), ensure_ascii=False),
        json.dumps(list(event.themes), ensure_ascii=False),
        json.dumps([s.to_dict() for s in event.leaders], ensure_ascii=False),
        event.source_url,
        json.dumps(event.payload, ensure_ascii=False),
        event.status,
    )


def upsert_events(
    conn: duckdb.DuckDBPyConnection,
    events: Iterable[ExpectedEvent],
) -> int:
    """Upsert ExpectedEvent rows by ``(source, source_fingerprint)``.

    Two layers of safety:

    1. **Batch dedupe** — same (source, fp) appearing twice in one batch
       collapses to the last occurrence. This happens when adapters pull
       overlapping date windows and the upstream surfaces the same
       multi-day event in several days' responses.

    2. **ON CONFLICT DO UPDATE** — DuckDB-native upsert keyed by the
       unique index on (source, source_fingerprint). Avoids the
       DELETE-then-INSERT-in-one-transaction pattern, which DuckDB's
       constraint checker doesn't always see through (the DELETE's
       intra-transaction effect on the unique index isn't always visible
       to the immediately-following INSERT).

    ``ingested_at`` is set on each row from `CURRENT_TIMESTAMP` via
    `excluded.ingested_at` so re-pulling refreshes the timestamp.
    """
    events = list(events)
    if not events:
        return 0

    # Last-write-wins batch dedupe — see docstring.
    by_key: dict[tuple[str, str], ExpectedEvent] = {}
    for event in events:
        by_key[(event.source, event.source_fingerprint)] = event
    deduped = list(by_key.values())
    rows = [_event_to_row(event) for event in deduped]

    conn.executemany(
        """
        INSERT INTO expected_events (
            event_id, source, source_fingerprint, event_type, event_name,
            event_scope, scope_reason, event_content, expected_at, expected_at_end,
            time_certainty, importance, stock_codes, industries, themes, leaders,
            source_url, payload, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (source, source_fingerprint) DO UPDATE SET
            event_id        = excluded.event_id,
            event_type      = excluded.event_type,
            event_name      = excluded.event_name,
            event_scope     = excluded.event_scope,
            scope_reason    = excluded.scope_reason,
            event_content   = excluded.event_content,
            expected_at     = excluded.expected_at,
            expected_at_end = excluded.expected_at_end,
            time_certainty  = excluded.time_certainty,
            importance      = excluded.importance,
            stock_codes     = excluded.stock_codes,
            industries      = excluded.industries,
            themes          = excluded.themes,
            leaders         = excluded.leaders,
            source_url      = excluded.source_url,
            payload         = excluded.payload,
            status          = excluded.status,
            ingested_at     = now()
        """,
        rows,
    )
    return len(rows)


# --- read path -------------------------------------------------------------


def _parse_json_column(raw: Any) -> Any:
    """Tolerant JSON deserializer for columns we wrote as ``json.dumps``.

    DuckDB returns JSON columns as strings. We want lists/dicts back. Empty
    strings / NULL / non-JSON content all collapse to a sensible default
    (empty list) so downstream code never has to ``isinstance`` check.
    """
    if raw is None:
        return []
    if isinstance(raw, (list, dict)):
        return raw
    text = str(raw).strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


def _date_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _row_to_dict(row: tuple) -> dict[str, Any]:
    """Map a SELECT row back to the API-facing dict shape.

    Keys here line up with what
    :meth:`calenderapp.services.eventradar_proxy_service.EventradarProxyService._normalize_announcement`
    expects, so nothing in the proxy layer needs to translate.
    """
    (
        event_id, source, source_fingerprint, event_type, event_name,
        event_scope, scope_reason, event_content, expected_at, expected_at_end,
        time_certainty, importance, stock_codes, industries, themes, leaders,
        source_url, payload, status, ingested_at,
    ) = row

    stocks = _parse_json_column(stock_codes)
    leader_list = _parse_json_column(leaders)

    return {
        "event_id": event_id,
        "source": source,
        "source_fingerprint": source_fingerprint,
        "event_type": event_type or "",
        "event_name": event_name or "",
        "event_scope": event_scope or "",
        "scope_reason": scope_reason or "",
        "event_content": event_content or "",
        "expected_at": _date_to_str(expected_at),
        "expected_at_end": _date_to_str(expected_at_end),
        "time_certainty": time_certainty or "",
        "importance": int(importance or 0),
        # 双命名：``stock_codes`` 是 schema 原名，``affected_stocks`` 是
        # calenderapp proxy 期望的字段名。两个都返回，前端无须再做翻译。
        "stock_codes": stocks,
        "affected_stocks": stocks,
        "industries": _parse_json_column(industries),
        "affected_industries": _parse_json_column(industries),
        "themes": _parse_json_column(themes),
        "affected_themes": _parse_json_column(themes),
        "leaders": leader_list,
        "source_url": source_url or "",
        "source": source,
        "status": status or "",
    }


def _build_filters(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    """Translate the API filters dict into a SQL WHERE clause + params.

    Every clause is column-bound + parameterized — no user string ever
    enters the SQL text. Returns ("" or "WHERE ...", params).
    """
    clauses: list[str] = []
    params: list[Any] = []

    date_from = (filters.get("date_from") or "").strip()
    if date_from:
        clauses.append("expected_at >= ?")
        params.append(date_from)
    date_to = (filters.get("date_to") or "").strip()
    if date_to:
        clauses.append("expected_at <= ?")
        params.append(date_to)

    scope = (filters.get("scope") or "").strip().lower()
    if scope:
        clauses.append("event_scope = ?")
        params.append(scope)

    # `source` is the adapter-level identifier ("em_gsrl" / "em_yjyg" /
    # "wallstreet_macro"). Drives the platform/source two-tier tabs on the
    # frontend. Accepts a single value or a comma-separated list (so the
    # "东方财富" platform tab can pass `em_gsrl,em_yjyg` to union the two
    # sources without two round-trips).
    source = (filters.get("source") or "").strip()
    if source:
        items = [s.strip() for s in source.split(",") if s.strip()]
        if items:
            placeholders = ",".join("?" * len(items))
            clauses.append(f"source IN ({placeholders})")
            params.extend(items)

    event_type = (filters.get("event_type") or "").strip().lower()
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)

    importance_min = filters.get("importance_min")
    if importance_min not in (None, "", 0):
        try:
            clauses.append("importance >= ?")
            params.append(int(importance_min))
        except (TypeError, ValueError):
            pass  # silently drop a bogus value rather than 500ing

    # has_leader: true → only events that touched a leader stock (leaders
    # JSON array non-empty). The enricher writes "[]" for the no-leader case
    # rather than NULL, so we test inequality with a JSON string literal.
    # false explicitly excludes leader events; None / unset = no filter.
    has_leader = filters.get("has_leader")
    if has_leader is True:
        clauses.append("leaders IS NOT NULL AND leaders != '[]'")
    elif has_leader is False:
        clauses.append("(leaders IS NULL OR leaders = '[]')")

    keyword = (filters.get("keyword") or "").strip()
    if keyword:
        # OR across the human-readable columns. ``ILIKE`` is DuckDB's
        # case-insensitive match.
        clauses.append("(event_name ILIKE ? OR event_content ILIKE ?)")
        params.extend([f"%{keyword}%"] * 2)

    industry = (filters.get("industry") or "").strip()
    if industry:
        # JSON column LIKE — wrap in quotes so we match the JSON-serialized
        # string element (``"半导体"``) rather than substrings.
        clauses.append("CAST(industries AS VARCHAR) LIKE ?")
        params.append(f'%"{industry}"%')

    theme = (filters.get("theme") or "").strip()
    if theme:
        clauses.append("CAST(themes AS VARCHAR) LIKE ?")
        params.append(f'%"{theme}"%')

    stock_code = (filters.get("stock_code") or "").strip().upper()
    if stock_code:
        clauses.append('CAST(stock_codes AS VARCHAR) LIKE ?')
        params.append(f'%"{stock_code}"%')

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


def list_events(
    conn: duckdb.DuckDBPyConnection,
    *,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    filters: dict[str, Any],
) -> dict[str, Any]:
    """Paginated read for ``POST /events/expected``."""
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 200))
    sort_column = sort_by if sort_by in _SORTABLE_COLUMNS else "expected_at"
    sort_dir = "DESC" if str(sort_order).lower() == "desc" else "ASC"
    where_clause, params = _build_filters(filters)

    total_count = conn.execute(
        f"SELECT COUNT(*) FROM expected_events {where_clause}",
        params,
    ).fetchone()[0]

    offset = (page - 1) * page_size
    rows = conn.execute(
        # Secondary sort on event_id keeps pagination stable when the
        # primary sort column has ties (e.g. many rows on the same date).
        f"""
        SELECT {_SELECT_COLUMNS}
        FROM expected_events
        {where_clause}
        ORDER BY {sort_column} {sort_dir} NULLS LAST, event_id ASC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    ).fetchall()

    items = [_row_to_dict(row) for row in rows]
    return {
        "items": items,
        "count": len(items),
        "total_count": int(total_count or 0),
        "page": page,
        "page_size": page_size,
        "sort_by": sort_column,
        "sort_order": sort_dir.lower(),
        "has_more": offset + len(items) < int(total_count or 0),
    }


def get_event(conn: duckdb.DuckDBPyConnection, event_id: str) -> dict[str, Any] | None:
    """Single-row fetch for ``GET /events/expected/{event_id}``."""
    event_id = (event_id or "").strip()
    if not event_id:
        return None
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM expected_events WHERE event_id = ?",
        [event_id],
    ).fetchone()
    return _row_to_dict(row) if row else None


def filter_meta(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Distinct facet values for ``GET /events/expected/filters/meta``.

    ``industries`` / ``themes`` come from JSON columns — DuckDB's
    ``json_each`` flattens them into rows we can DISTINCT over. When the DB
    is empty (fresh install / first boot before any pull) every list comes
    back empty rather than the call erroring.
    """
    # event_types & scopes seen in the data (might be subset of the static
    # enum tuples — return the union so the UI can pre-populate dropdowns).
    seen_event_types = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT event_type FROM expected_events WHERE event_type IS NOT NULL"
        ).fetchall()
        if row[0]
    }
    seen_scopes = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT event_scope FROM expected_events WHERE event_scope IS NOT NULL"
        ).fetchall()
        if row[0]
    }

    # JSON list columns — flatten with json_each. Use json_each.value->>'$'
    # to get the scalar string; bare json_each.value returns the JSON-encoded
    # token (i.e. '"化学制品"' with quotes) for string elements, which would
    # leak quote characters into the filter dropdown values.
    industries = sorted(
        {
            row[0]
            for row in conn.execute(
                """
                SELECT DISTINCT json_each.value->>'$'
                FROM expected_events,
                     json_each(industries)
                """
            ).fetchall()
            if row[0]
        }
    )
    themes = sorted(
        {
            row[0]
            for row in conn.execute(
                """
                SELECT DISTINCT json_each.value->>'$'
                FROM expected_events,
                     json_each(themes)
                """
            ).fetchall()
            if row[0]
        }
    )

    # Date bounds let the UI initialize its date-range picker sensibly.
    bounds = conn.execute(
        "SELECT MIN(expected_at), MAX(expected_at) FROM expected_events"
    ).fetchone()
    date_min = _date_to_str(bounds[0]) if bounds and bounds[0] else ""
    date_max = _date_to_str(bounds[1]) if bounds and bounds[1] else ""

    return {
        "industries": industries,
        "themes": themes,
        # 静态枚举（提供完整 UI 选项）∪ 数据中已出现的（保险，防止未来扩枚举忘改这边）
        "event_types": sorted(set(EVENT_TYPE_VALUES) | seen_event_types),
        "scopes": sorted(set(EVENT_SCOPE_VALUES) | seen_scopes),
        "date_min": date_min,
        "date_max": date_max,
    }


def source_counts(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Event count per ``source`` — drives the platform/source tabs.

    Returns ``{source_id: count}`` for every source that has rows. Sources
    with zero rows aren't returned; the frontend layers them in as
    placeholders from its own static platform registry. Done as a single
    GROUP BY to avoid N queries from the UI.
    """
    return {
        str(row[0]): int(row[1])
        for row in conn.execute(
            "SELECT source, COUNT(*) FROM expected_events "
            "WHERE source IS NOT NULL GROUP BY 1"
        ).fetchall()
        if row[0]
    }


# --- enrichment path (M3) --------------------------------------------------
#
# These are partial updates by event_id — unlike upsert_events (which
# delete-then-inserts whole rows), the enrich pass only rewrites the four
# enrichment columns + enriched_at, leaving ingested_at / payload / the
# adapter-supplied fields untouched. That keeps the adapter and enricher
# cleanly separable: re-running enrich never loses the original ingest.


# Columns the enrich pass is allowed to rewrite. Kept in one place so the
# UPDATE statement and the row tuple stay in lock-step.
_ENRICH_COLUMNS = (
    "industries",
    "leaders",
    "importance",
    "expected_at_end",
    "time_certainty",
    "enriched_at",
)


def update_enrichment(
    conn: duckdb.DuckDBPyConnection,
    rows: Iterable[tuple],
) -> int:
    """Batch-update enrichment columns by ``event_id``.

    Each row is ``(event_id, industries_json, leaders_json, importance,
    expected_at_end, time_certainty, enriched_at)`` — order matches
    :data:`_ENRICH_COLUMNS` plus the key. industries/leaders are already
    JSON strings (caller serializes) so DuckDB stores them verbatim into the
    JSON columns. Single transaction; 0 rows → no-op.
    """
    rows = list(rows)
    if not rows:
        return 0
    conn.execute("BEGIN")
    try:
        conn.executemany(
            """
            UPDATE expected_events
            SET industries = ?,
                leaders = ?,
                importance = ?,
                expected_at_end = ?,
                time_certainty = ?,
                enriched_at = ?
            WHERE event_id = ?
            """,
            # SQL binds columns first, then the WHERE key — reorder the
            # tuple so the key comes last.
            [(r[1], r[2], r[3], r[4], r[5], r[6], r[0]) for r in rows],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return len(rows)


def upsert_stock_meta(
    conn: duckdb.DuckDBPyConnection,
    rows: Iterable[tuple],
) -> int:
    """Insert-or-replace ``stock_meta`` rows.

    Each row: ``(stock_code, stock_name, industry, total_market_cap,
    float_market_cap, updated_at)``. ``updated_at`` may be None — DuckDB's
    column default (CURRENT_TIMESTAMP) only fires on INSERT without a value,
    and INSERT OR REPLACE supplies all columns, so pass an explicit
    timestamp from the caller when you want freshness tracking.
    """
    rows = list(rows)
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT OR REPLACE INTO stock_meta
            (stock_code, stock_name, industry, total_market_cap,
             float_market_cap, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def get_stock_meta_map(
    conn: duckdb.DuckDBPyConnection,
    stock_codes: Iterable[str],
) -> dict[str, dict[str, Any]]:
    """Bulk-fetch ``stock_meta`` for the given codes → ``{code: {field: val}}``.

    Unknown codes are simply absent from the result — callers handle the miss
    (graceful degradation, not an error). Market-cap values come back as
    floats so leader_scorer can compare against the threshold directly.
    """
    codes = [str(c).strip() for c in stock_codes if str(c).strip()]
    if not codes:
        return {}
    # IN-list with placeholders — DuckDB handles the binding.
    placeholders = ",".join("?" * len(codes))
    rows = conn.execute(
        f"""
        SELECT stock_code, stock_name, industry, total_market_cap,
               float_market_cap
        FROM stock_meta
        WHERE stock_code IN ({placeholders})
        """,
        codes,
    ).fetchall()
    return {
        str(row[0]): {
            "stock_code": str(row[0]),
            "stock_name": str(row[1] or ""),
            "industry": str(row[2] or ""),
            "total_market_cap": float(row[3]) if row[3] is not None else None,
            "float_market_cap": float(row[4]) if row[4] is not None else None,
        }
        for row in rows
    }


def list_stock_codes_needing_meta(
    conn: duckdb.DuckDBPyConnection,
) -> list[str]:
    """Stock codes referenced by expected_events but absent from stock_meta.

    Drives ``refresh_stock_meta`` so we only fetch metadata for stocks we
    actually have events for, and only the ones not yet cached. Returns
    distinct codes, stripped, sorted for deterministic fetch order.

    Flattens *every* code in each event's ``stock_codes`` JSON array (not
    just the first) so multi-stock events from future M2 sources are fully
    covered.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT je.value->>'$.stock_code' AS code
        FROM expected_events,
             json_each(stock_codes) AS je
        WHERE je.value->>'$.stock_code' IS NOT NULL
          AND (je.value->>'$.stock_code') NOT IN
              (SELECT stock_code FROM stock_meta)
        """
    ).fetchall()
    codes: list[str] = []
    for (raw,) in rows:
        if raw is None:
            continue
        text = str(raw).strip().strip('"')
        if text:
            codes.append(text)
    return sorted(set(codes))
