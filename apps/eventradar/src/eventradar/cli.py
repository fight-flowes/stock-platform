"""eventradar CLI entry point.

Available subcommands:

    show-config     Print the resolved settings (paths + env). Useful to
                    sanity-check before scheduling cron jobs.
    serve           Run the FastAPI server (uvicorn). Read-only — never
                    triggers an ingestion.
    list-adapters   Show which adapters are registered. Empty in M1.
    pull            Run one adapter and persist its output, then publish
                    the read-replica. ``eventradar pull <name> [--kw=val ...]``.
                    The name comes from :data:`eventradar.service.ADAPTERS`.
    publish-replica Manually republish ``eventradar.read.duckdb`` from the
                    primary file. Useful after ad-hoc edits.

Cron usage (the agreed scheduling model):

    # Daily at 06:31 — pull next 30 days of company calendar events.
    31 6 * * *  cd /path/to/apps/eventradar && \
        ./manage.sh pull company_calendar_em --days=30 \
        >> logs/cron.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from .config import get_settings
from .service import ADAPTERS, EventradarService
# Importing this package registers every adapter into ``ADAPTERS`` via
# side-effect (each adapter module appends itself at import time). Doing
# the import here, at the CLI entrypoint, keeps ``service.py`` itself
# free of cross-module imports — which would otherwise become circular
# (adapters → sources → service).
from .sources import adapters as _adapters  # noqa: F401

LOGGER = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _coerce_kv(raw: str) -> tuple[str, Any]:
    """Parse ``--key=value`` into a Python value.

    Type coercion is intentionally conservative:
        - bool words (``true``/``false``) become bool
        - JSON-shaped values (``[...]`` / ``{...}``) get json.loads
        - everything else stays a string

    We deliberately do NOT auto-convert all-digit values to int —
    YYYYMMDD dates would otherwise lose their leading zeros and silently
    parse as 8-digit ints, which then look like Unix epoch seconds to
    downstream date parsers. Adapters that expect an int kwarg should
    cast inside themselves; CLI strings stay strings.
    """
    if "=" not in raw:
        raise argparse.ArgumentTypeError(f"expected key=value, got {raw!r}")
    key, value = raw.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        raise argparse.ArgumentTypeError(f"empty key in {raw!r}")
    if value.lower() in {"true", "false"}:
        return key, value.lower() == "true"
    if value.startswith(("[", "{")):
        try:
            return key, json.loads(value)
        except json.JSONDecodeError:
            pass
    return key, value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eventradar", description="eventradar CLI")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show-config", help="print resolved settings")

    serve = sub.add_parser("serve", help="run the FastAPI server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    sub.add_parser("list-adapters", help="show registered ingestion adapters")

    pull = sub.add_parser("pull", help="run one adapter and persist its output")
    pull.add_argument("adapter", help="adapter name (see `eventradar list-adapters`)")
    pull.add_argument(
        "kv",
        nargs="*",
        type=_coerce_kv,
        help="adapter kwargs as key=value (e.g. date=20260620 days=30)",
    )

    sub.add_parser("publish-replica", help="copy primary duckdb onto the read replica")

    refresh_meta = sub.add_parser(
        "refresh-stock-meta",
        help="populate the stock_meta cache (industry + market cap) from akshare",
    )
    refresh_meta.add_argument(
        "--codes",
        default="",
        help="comma-separated stock codes to fetch (default: all codes with events but no cached meta)",
    )

    refresh_meta_tushare = sub.add_parser(
        "refresh-stock-meta-tushare",
        help="bulk-populate stock_meta via calenderapp's tushare proxy (A股 ~5500 stocks in ~2 calls)",
    )
    refresh_meta_tushare.add_argument(
        "--trade-date",
        default="",
        help="YYYYMMDD for daily_basic (default: walk back from today until a trade day with data)",
    )

    enrich = sub.add_parser(
        "enrich",
        help="fill industries / leaders / importance / expected_at_end for expected events",
    )
    enrich.add_argument(
        "--all",
        action="store_true",
        help="re-enrich every row (default: only rows where enriched_at IS NULL)",
    )

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    if args.command == "show-config":
        return _cmd_show_config()
    if args.command == "serve":
        return _cmd_serve(args.host, args.port)
    if args.command == "list-adapters":
        return _cmd_list_adapters()
    if args.command == "pull":
        return _cmd_pull(args.adapter, dict(args.kv))
    if args.command == "publish-replica":
        return _cmd_publish_replica()
    if args.command == "refresh-stock-meta":
        codes = [c for c in (args.codes.split(",") if args.codes else []) if c.strip()]
        return _cmd_refresh_stock_meta(codes or None)
    if args.command == "refresh-stock-meta-tushare":
        return _cmd_refresh_stock_meta_tushare(args.trade_date.strip() or None)
    if args.command == "enrich":
        return _cmd_enrich(all_rows=args.all)

    parser.error(f"unknown command: {args.command}")
    return 2


# --- subcommands -----------------------------------------------------------


def _cmd_show_config() -> int:
    settings = get_settings()
    payload = {
        "root_dir": str(settings.root_dir),
        "data_dir": str(settings.data_dir),
        "duckdb_path": str(settings.duckdb_path),
        "duckdb_read_path": str(settings.duckdb_read_path),
        "raw_cache_dir": str(settings.raw_cache_dir),
        "raw_cache_enabled": settings.raw_cache_enabled,
        "http_timeout": settings.http_timeout,
        "http_max_retries": settings.http_max_retries,
        "http_proxy": settings.http_proxy,
        "api_host": settings.api_host,
        "api_port": settings.api_port,
        "registered_adapters": sorted(ADAPTERS),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_serve(host: str | None, port: int | None) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed; run `pip install -e .[serve]`", file=sys.stderr)
        return 2

    settings = get_settings()
    host = host or settings.api_host
    port = port or settings.api_port
    LOGGER.info("eventradar.serve host=%s port=%d", host, port)
    uvicorn.run("eventradar.api:create_app", host=host, port=port, factory=True)
    return 0


def _cmd_list_adapters() -> int:
    if not ADAPTERS:
        print("(no adapters registered yet — see eventradar.sources.adapters)")
        return 0
    for name, spec in sorted(ADAPTERS.items()):
        print(f"{name:30s}  {spec.description}")
    return 0


def _cmd_pull(adapter: str, kwargs: dict[str, Any]) -> int:
    service = EventradarService()
    try:
        summary = service.run_adapter(adapter, **kwargs)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except NotImplementedError as exc:
        # Most likely the storage upsert path is still a stub. Surface a
        # clear actionable message — this is the expected state pre-M1.
        print(f"adapter {adapter!r} can't run yet: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_publish_replica() -> int:
    from .storage import publish_replica

    target = publish_replica()
    print(f"replica published: {target}")
    return 0


def _cmd_refresh_stock_meta(codes: list[str] | None) -> int:
    service = EventradarService()
    summary = service.refresh_stock_meta(codes)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_refresh_stock_meta_tushare(trade_date: str | None) -> int:
    service = EventradarService()
    summary = service.refresh_stock_meta_via_tushare(trade_date=trade_date)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    # A non-zero exit when the tushare path is unavailable makes CI / cron
    # fail visibly rather than silently skipping the refresh.
    return 0 if summary.get("status") == "ok" else 2


def _cmd_enrich(*, all_rows: bool) -> int:
    service = EventradarService()
    summary = service.enrich_events(all_rows=all_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
