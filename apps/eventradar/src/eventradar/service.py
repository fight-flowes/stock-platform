"""Top-level orchestration — composes config, storage, and adapters.

Anything that needs more than one layer (e.g. "run an adapter and persist
its output") goes here, so neither the CLI nor the API has to know about
the internals. Adapters register themselves into :data:`ADAPTERS` once
they're written; today the registry is empty and every method that touches
adapters raises :class:`NotImplementedError` clearly.

This file is small on purpose. Resist the temptation to put adapter glue
here — adapters belong in :mod:`eventradar.sources.adapters` so each is
independently testable.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from .config import Settings, get_settings
from .normalize import ExpectedEvent
from .normalize.enrichers import (
    compute_importance,
    map_industries,
    parse_future_date,
    score_leaders,
)
from .sources.akshare_client import AkshareCallError, fetch_dataframe
from .storage import (
    filter_meta as _filter_meta,
    get_event as _get_event,
    get_stock_meta_map,
    list_events as _list_events,
    list_stock_codes_needing_meta,
    open_primary,
    open_replica,
    publish_replica,
    source_counts as _source_counts,
    update_enrichment,
    upsert_events,
    upsert_stock_meta,
)

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AdapterSpec:
    """Metadata for an adapter the CLI can dispatch to.

    ``run`` takes a kwargs dict (CLI arguments, e.g. ``date``, ``days``)
    and returns a list of :class:`ExpectedEvent`. The CLI handles
    persistence and the read-replica swap — adapters stay pure.
    """

    name: str
    description: str
    run: Callable[..., list[ExpectedEvent]]


# Adapter registry. Populated by adapters at import time.
# Today empty — first entry lands in M1 with the company-calendar adapter.
ADAPTERS: dict[str, AdapterSpec] = {}


class EventradarService:
    """Bundles the read-side helpers used by :mod:`eventradar.api`.

    Construct once per FastAPI process. The class holds no state — every
    public method opens its own short-lived read connection so we never
    pin a DuckDB handle across requests.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # --- read-side ---------------------------------------------------------

    def list_announcements(
        self,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        with open_replica(self.settings) as conn:
            return _list_events(
                conn,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
                filters=filters,
            )

    def get_announcement(self, event_id: str) -> dict[str, Any] | None:
        with open_replica(self.settings) as conn:
            return _get_event(conn, event_id)

    def get_filter_meta(self) -> dict[str, Any]:
        with open_replica(self.settings) as conn:
            return _filter_meta(conn)

    def get_source_counts(self) -> dict[str, int]:
        """Event count per source — feeds the frontend's platform tab badges."""
        with open_replica(self.settings) as conn:
            return _source_counts(conn)

    # --- write-side --------------------------------------------------------

    def run_adapter(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Execute one registered adapter, persist its output, refresh replica.

        Returns a small summary the CLI prints. Order of operations:
            1. Adapter pulls + normalizes — pure, no DuckDB.
            2. Open primary, upsert, close.
            3. Publish read replica so the API picks up the new rows.

        If step 1 raises, nothing was written. If step 2 raises, the primary
        may have partial new data but the replica is unchanged — readers
        keep seeing the previous snapshot, which is the safer failure mode.
        """
        spec = ADAPTERS.get(name)
        if spec is None:
            raise KeyError(f"unknown adapter: {name!r} (registered: {sorted(ADAPTERS)})")

        events = list(spec.run(**kwargs))
        LOGGER.info("eventradar.adapter_run name=%s produced=%d", name, len(events))

        with open_primary(self.settings) as conn:
            written = upsert_events(conn, events)

        published = publish_replica(self.settings)

        return {
            "adapter": name,
            "produced": len(events),
            "written": written,
            "replica_path": str(published),
        }

    # --- enrichment (M3) ---------------------------------------------------

    def refresh_stock_meta(self, stock_codes: list[str] | None = None) -> dict[str, Any]:
        """Populate the ``stock_meta`` cache from akshare.

        With no args, fetches every stock referenced by expected_events that
        isn't already cached (idempotent — re-running only fills gaps). With
        an explicit ``stock_codes`` list, fetches exactly those (used by
        ``--codes`` for forced refresh).

        Per-stock failures are logged and skipped — a flaky push2 endpoint
        for one ticker must not abort the whole run. Returns a summary the
        CLI prints.
        """
        with open_primary(self.settings) as conn:
            targets = (
                list(dict.fromkeys(c.strip() for c in stock_codes if c and c.strip()))
                if stock_codes
                else list_stock_codes_needing_meta(conn)
            )

        LOGGER.info("eventradar.refresh_stock_meta targets=%d", len(targets))
        rows: list[tuple] = []
        fetched = 0
        failed: list[str] = []
        for code in targets:
            try:
                df = fetch_dataframe(
                    "stock_individual_info_em",
                    symbol=code,
                    cache_key=f"stock_meta_{code}",
                )
            except AkshareCallError as exc:
                LOGGER.warning("eventradar.stock_meta_fail code=%s reason=%s", code, exc)
                failed.append(code)
                continue
            if df is None or df.empty:
                LOGGER.warning("eventradar.stock_meta_empty code=%s", code)
                failed.append(code)
                continue
            # akshare returns a 2-col (item, value) frame; pivot to a dict.
            info = dict(zip(df["item"].astype(str), df["value"]))
            rows.append(
                (
                    code,
                    str(info.get("股票简称") or ""),
                    str(info.get("行业") or ""),
                    _to_float(info.get("总市值")),
                    _to_float(info.get("流通市值")),
                    datetime.now(timezone.utc),
                )
            )
            fetched += 1

        written = 0
        if rows:
            with open_primary(self.settings) as conn:
                written = upsert_stock_meta(conn, rows)

        return {
            "targets": len(targets),
            "fetched": fetched,
            "failed": failed,
            "written": written,
        }

    def refresh_stock_meta_via_tushare(
        self,
        *,
        trade_date: str | None = None,
    ) -> dict[str, Any]:
        """Bulk-populate ``stock_meta`` using calenderapp's tushare proxy.

        This is the A1 path — one ``stock_basic`` call gives us every listed
        A-share's industry + name (~5500 rows), and one ``daily_basic`` call
        gives us their float / total market cap for ``trade_date``. Joining
        the two and upserting fills the gap that
        :meth:`refresh_stock_meta` (per-stock akshare push2 calls) is too
        slow / fragile to cover.

        Reuses calenderapp's ``get_tushare_pro`` rather than re-encoding the
        token here. Adding calenderapp's backend path + .env is configurable
        in :class:`Settings`; missing calenderapp = clear error, not crash.

        Units note: tushare returns ``total_mv``/``circ_mv`` in **万元**;
        ``stock_meta.*_market_cap`` is stored in **元** so the
        500亿 threshold check in leader_scorer works without a units
        conversion at read time. We multiply by 10000 on the way in.

        Args:
            trade_date: YYYYMMDD for daily_basic; defaults to the most
                recent trade date with data (walks back up to 7 days from
                today to handle weekends / holidays).
        """
        try:
            pro = _load_tushare_pro(self.settings)
        except _TushareUnavailable as exc:
            return {
                "status": "unavailable",
                "reason": str(exc),
                "fetched": 0,
                "written": 0,
            }

        import pandas as pd

        # stock_basic: every listed A-share, with industry. Doesn't take a
        # date — it's a roster snapshot.
        LOGGER.info("eventradar.tushare_stock_basic start")
        basic = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,industry,market",
        )
        if basic is None or basic.empty:
            return {
                "status": "empty_basic",
                "fetched": 0,
                "written": 0,
            }
        LOGGER.info("eventradar.tushare_stock_basic rows=%d", len(basic))

        # daily_basic: today's market caps. Walk back through recent dates
        # if the requested one was a non-trade day.
        candidates = (
            [str(trade_date).strip().replace("-", "")]
            if trade_date
            else _recent_trade_date_candidates(today=date.today(), days_back=7)
        )
        daily: pd.DataFrame | None = None
        chosen_date = ""
        for candidate in candidates:
            LOGGER.info("eventradar.tushare_daily_basic try=%s", candidate)
            df = pro.daily_basic(
                trade_date=candidate,
                fields="ts_code,total_mv,circ_mv",
            )
            if df is not None and not df.empty:
                daily = df
                chosen_date = candidate
                break
        if daily is None:
            return {
                "status": "no_daily_basic",
                "reason": f"no daily_basic data in candidates {candidates}",
                "fetched": 0,
                "written": 0,
            }
        LOGGER.info("eventradar.tushare_daily_basic date=%s rows=%d", chosen_date, len(daily))

        # Merge: left join basic onto daily. A stock missing from daily
        # (newly listed / suspended) still gets industry — its market cap
        # is just left as NULL, leader_scorer naturally treats NULL as
        # "not a leader". No silent drops.
        merged = basic.merge(daily, on="ts_code", how="left")

        now = datetime.now(timezone.utc)
        rows = []
        for _, r in merged.iterrows():
            # ts_code is like "600519.SH" — stock_meta keys on the bare
            # numeric code so it matches stock_codes JSON in events.
            ts_code = str(r.get("ts_code") or "")
            code = ts_code.split(".", 1)[0] if "." in ts_code else ts_code
            if not code:
                continue
            total_mv = r.get("total_mv")
            circ_mv = r.get("circ_mv")
            # pandas turns missing strings into the float NaN, which then
            # str()-ifies to "nan" — that leaks into industry filter
            # dropdowns. Coerce to empty string explicitly.
            industry_raw = r.get("industry")
            industry = "" if (industry_raw is None or pd.isna(industry_raw)) else str(industry_raw).strip()
            name_raw = r.get("name")
            stock_name = "" if (name_raw is None or pd.isna(name_raw)) else str(name_raw).strip()
            rows.append(
                (
                    code,
                    stock_name,
                    industry,
                    # 万元 → 元
                    None if pd.isna(total_mv) else float(total_mv) * 10000,
                    None if pd.isna(circ_mv) else float(circ_mv) * 10000,
                    now,
                )
            )

        with open_primary(self.settings) as conn:
            written = upsert_stock_meta(conn, rows)

        return {
            "status": "ok",
            "trade_date": chosen_date,
            "basic_rows": int(len(basic)),
            "daily_rows": int(len(daily)),
            "written": written,
        }

    def enrich_events(self, *, all_rows: bool = False) -> dict[str, Any]:
        """Run the four enrichers over expected_events and write back.

        By default only rows with ``enriched_at IS NULL`` are processed
        (idempotent incremental). ``all_rows=True`` re-enriches everything —
        use after a stock_meta refresh or a threshold change.

        Enrichment is a partial UPDATE (see ``update_enrichment``) — it
        never touches the adapter-supplied fields, so re-running is always
        safe. The stock_meta cache is consulted in one bulk fetch per batch
        so we don't round-trip per event.

        Degradation: if stock_meta is empty (push2 unreachable, cache cold),
        industries/leaders stay empty and importance falls back to type +
        future-date only. The run still completes and rows get
        ``enriched_at`` set so they aren't retried pointlessly.
        """
        update_rows: list[tuple] = []
        processed = 0
        with_enrichment = 0  # rows where at least one dimension got filled
        today = date.today()

        with open_primary(self.settings) as conn:
            where = "" if all_rows else "WHERE enriched_at IS NULL"
            event_rows = conn.execute(
                f"""
                SELECT event_id, event_type, expected_at, event_content,
                       stock_codes, time_certainty, importance
                FROM expected_events
                {where}
                """
            ).fetchall()

            # Bulk-fetch stock_meta for every code referenced in this batch.
            all_codes: set[str] = set()
            for row in event_rows:
                for code in _codes_from_json(row[4]):  # stock_codes is col 4
                    all_codes.add(code)
            meta_map = get_stock_meta_map(conn, all_codes) if all_codes else {}

            for (
                event_id,
                event_type,
                expected_at,
                event_content,
                stock_codes_json,
                existing_certainty,
                adapter_importance,
            ) in event_rows:
                processed += 1
                codes = _codes_from_json(stock_codes_json)
                stocks = [{"stock_code": c, "stock_name": _name_from_meta(meta_map, c)} for c in codes]

                disclosure = expected_at if isinstance(expected_at, date) else today
                expected_at_end, parsed_certainty = parse_future_date(
                    event_content, disclosure_date=disclosure
                )
                industries = map_industries(stocks, meta_map)
                leaders, has_leader = score_leaders(stocks, meta_map)
                rule_importance = compute_importance(
                    event_type=event_type or "",
                    has_leader=has_leader,
                    expected_at_end=expected_at_end,
                    today=today,
                )
                # Take the max of adapter-supplied importance and rule-derived
                # importance. Adapters that get an upstream importance signal
                # (e.g. wallstreet_macro maps WSC's 1-4 rating to our 0-3)
                # would otherwise be overwritten by the generic rule, which
                # has no way to know "美联储议息会议" is a 3-star event.
                # max() preserves the stronger of the two signals without
                # forcing adapters to know about the rule logic.
                importance = max(int(adapter_importance or 1), rule_importance)

                # Only rewrite time_certainty when the parser found a future
                # date (it may downgrade confirmed_date→month for a month-only
                # match). Otherwise preserve whatever the adapter set so we
                # don't NULL out a valid "confirmed_date".
                final_certainty = parsed_certainty if expected_at_end else (existing_certainty or "")

                update_rows.append(
                    (
                        event_id,
                        json.dumps(industries, ensure_ascii=False),
                        json.dumps(leaders, ensure_ascii=False),
                        importance,
                        expected_at_end,
                        final_certainty,
                        datetime.now(timezone.utc),
                    )
                )
                if industries or leaders or expected_at_end or importance != 1:
                    with_enrichment += 1

            written = update_enrichment(conn, update_rows) if update_rows else 0

        published = publish_replica(self.settings)
        return {
            "processed": processed,
            "with_enrichment": with_enrichment,
            "written": written,
            "replica_path": str(published),
        }


# --- helpers used by enrich_events (module-level to keep the method readable)


def _to_float(value: Any) -> float | None:
    """Coerce akshare's market-cap values (strings with units, or numbers)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _codes_from_json(stock_codes_json: Any) -> list[str]:
    """Parse the ``stock_codes`` JSON column into a list of code strings."""
    if not stock_codes_json:
        return []
    if isinstance(stock_codes_json, str):
        try:
            data = json.loads(stock_codes_json)
        except json.JSONDecodeError:
            return []
    else:
        data = stock_codes_json
    if not isinstance(data, list):
        return []
    codes: list[str] = []
    for item in data:
        if isinstance(item, dict):
            code = str(item.get("stock_code") or "").strip()
            if code:
                codes.append(code)
    return codes


def _name_from_meta(meta_map: dict[str, dict[str, Any]], code: str) -> str:
    meta = meta_map.get(code)
    return str(meta.get("stock_name") or "") if meta else ""


# --- A1 helpers: tushare integration via calenderapp's config ----------------


class _TushareUnavailable(RuntimeError):
    """Raised when refresh_stock_meta_via_tushare can't reach the proxy.

    Caught at the service boundary and translated into a structured
    summary dict — the CLI surfaces it as an actionable error rather than
    a traceback. Reasons include: calenderapp source not on disk, missing
    TUSHARE_TOKEN, or the tushare/pandas dependency failing to import.
    """


def _load_tushare_pro(settings: Settings):
    """Import calenderapp's ``get_tushare_pro`` and construct an instance.

    eventradar deliberately does not re-encode the token here. calenderapp
    has been the source of truth for the internal-proxy URL + token; we
    just temporarily put its backend on sys.path, import the config
    helper, and call it.

    Side-effect: also loads calenderapp's .env via python-dotenv so the
    TUSHARE_TOKEN / TUSHARE_API_URL env vars are populated in this
    process. Without that, calenderapp's config module reads empty
    strings and raises ValueError.

    Proxy hygiene: tushare's internal proxy lives at a non-standard IP
    + port (typically inside a corp/VPC network). If the running env has
    an HTTP_PROXY set, requests will try to route through it and time
    out. We extract the host from TUSHARE_API_URL and add it to NO_PROXY
    so requests' inheritance from env keeps the call direct.
    """
    backend_path = (settings.calenderapp_backend_path or "").strip()
    if not backend_path:
        raise _TushareUnavailable(
            "EVENTRADAR_CALENDERAPP_BACKEND_PATH not set"
        )
    backend = Path(backend_path)
    if not backend.is_dir():
        raise _TushareUnavailable(
            f"calenderapp backend not found at {backend}"
        )

    # Load calenderapp's .env so TUSHARE_TOKEN / TUSHARE_API_URL are
    # visible to the config module's os.environ lookups. dotenv leaves
    # already-set vars alone, so an explicit eventradar override still wins.
    env_path = Path(settings.calenderapp_env_path or "")
    if env_path.is_file():
        load_dotenv(env_path, override=False)

    # Make calenderapp's `app` package importable. sys.path manipulation
    # is normally a smell, but here it's the price of cross-app reuse
    # without coupling at the package level. Inserted at front so
    # `app` resolves to calenderapp, not anything else.
    import sys
    sys_path_str = str(backend)
    if sys_path_str not in sys.path:
        sys.path.insert(0, sys_path_str)

    # Bypass any HTTP_PROXY for the tushare host. The internal proxy is
    # typically reached over a private route; passing through 7890 (or
    # whatever public proxy is set) won't have a route to the private
    # subnet and the call hangs until ReadTimeout.
    tushare_url = os.environ.get("TUSHARE_API_URL", "")
    if tushare_url:
        from urllib.parse import urlparse
        host = urlparse(tushare_url).hostname
        if host:
            existing = os.environ.get("NO_PROXY", "")
            if host not in existing:
                os.environ["NO_PROXY"] = f"{existing},{host}" if existing else host
                # Lowercase variant — requests reads both spellings.
                os.environ["no_proxy"] = os.environ["NO_PROXY"]

    try:
        from app.config import get_tushare_pro  # type: ignore
    except Exception as exc:  # noqa: BLE001 — import surface is wide
        raise _TushareUnavailable(
            f"failed to import calenderapp's get_tushare_pro: {exc}"
        ) from exc

    try:
        return get_tushare_pro()
    except Exception as exc:  # noqa: BLE001 — token / network / SDK errors
        raise _TushareUnavailable(
            f"get_tushare_pro() failed: {exc}"
        ) from exc


def _recent_trade_date_candidates(today: date, days_back: int) -> list[str]:
    """Yield YYYYMMDD candidates walking back from ``today``.

    Tushare's ``daily_basic`` is keyed by trade date — a Sunday lookup
    returns empty. We don't fetch a trade calendar just for this; the
    refresher walks back day-by-day and uses the first one with rows.
    """
    from datetime import timedelta as _td
    return [(today - _td(days=i)).strftime("%Y%m%d") for i in range(days_back + 1)]

