from __future__ import annotations

import argparse
import json
import sys

from .config import get_settings
from .event_kb.config import get_event_kb_settings
from .event_kb.services import ExtractionService


def _print_minio_prefix_progress(update: dict[str, object]) -> None:
    phase = str(update.get("phase", "") or "")
    if phase == "listed":
        total = int(update.get("total", 0) or 0)
        bucket = str(update.get("bucket", "") or "")
        prefix = str(update.get("prefix", "") or "").strip("/")
        location = f"minio://{bucket}/{prefix}" if prefix else f"minio://{bucket}"
        print(f"[stockkb] listed {total} markdown objects from {location}", file=sys.stderr, flush=True)
        return
    if phase == "start":
        index = int(update.get("index", 0) or 0)
        total = int(update.get("total", 0) or 0)
        object_name = str(update.get("object_name", "") or "")
        print(f"[stockkb] [{index}/{total}] importing {object_name}", file=sys.stderr, flush=True)
        return
    if phase == "success":
        index = int(update.get("index", 0) or 0)
        total = int(update.get("total", 0) or 0)
        stock_code = str(update.get("stock_code", "") or "")
        stock_name = str(update.get("stock_name", "") or "")
        report_date = str(update.get("report_date", "") or "")
        events = int(update.get("simple_events", update.get("events", 0)) or 0)
        print(
            f"[stockkb] [{index}/{total}] success {stock_code} {stock_name} {report_date} events={events}",
            file=sys.stderr,
            flush=True,
        )
        return
    if phase == "error":
        index = int(update.get("index", 0) or 0)
        total = int(update.get("total", 0) or 0)
        object_name = str(update.get("object_name", "") or "")
        error = str(update.get("error", "") or "")
        print(f"[stockkb] [{index}/{total}] error {object_name}: {error}", file=sys.stderr, flush=True)
        return
    if phase == "done":
        total = int(update.get("total", 0) or 0)
        success = int(update.get("success", 0) or 0)
        failed = int(update.get("failed", 0) or 0)
        print(f"[stockkb] done total={total} success={success} failed={failed}", file=sys.stderr, flush=True)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="stockkb CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_file = subparsers.add_parser("import-file", aliases=["ingest-file"], help="Import one markdown report")
    import_file.add_argument("path")

    import_folder = subparsers.add_parser("import-folder", aliases=["ingest-folder"], help="Import a folder of reports")
    import_folder.add_argument("folder")
    import_folder.add_argument("--pattern", default="**/*.md")

    import_minio_object = subparsers.add_parser(
        "import-minio-object",
        aliases=["ingest-minio-object"],
        help="Import one markdown object from MinIO",
    )
    import_minio_object.add_argument("object_name")
    import_minio_object.add_argument("--bucket", default=settings.minio_default_bucket)

    import_minio_prefix = subparsers.add_parser(
        "import-minio-prefix",
        aliases=["ingest-minio-prefix"],
        help="Import markdown objects under a MinIO prefix",
    )
    import_minio_prefix.add_argument("--bucket", default=settings.minio_default_bucket)
    import_minio_prefix.add_argument("--prefix", default="")
    import_minio_prefix.add_argument("--quiet-progress", action="store_true")

    kb_query_simple_reports = subparsers.add_parser("kb-query-simple-reports", help="Query simple reports from DuckDB")
    kb_query_simple_reports.add_argument("--page", type=int, default=1)
    kb_query_simple_reports.add_argument("--page-size", type=int, default=20)
    kb_query_simple_reports.add_argument("--sort-by", default="report_date")
    kb_query_simple_reports.add_argument("--sort-order", choices=("asc", "desc"), default="desc")
    kb_query_simple_reports.add_argument("--stock-code", default="")
    kb_query_simple_reports.add_argument("--stock-name", default="")
    kb_query_simple_reports.add_argument("--report-date", default="")
    kb_query_simple_reports.add_argument("--report-title", default="")

    kb_query_simple_events = subparsers.add_parser("kb-query-simple-events", help="Query simple events from DuckDB")
    kb_query_simple_events.add_argument("--page", type=int, default=1)
    kb_query_simple_events.add_argument("--page-size", type=int, default=20)
    kb_query_simple_events.add_argument("--sort-by", default="event_time_normalized")
    kb_query_simple_events.add_argument("--sort-order", choices=("asc", "desc"), default="desc")
    kb_query_simple_events.add_argument("--stock-code", default="")
    kb_query_simple_events.add_argument("--stock-name", default="")
    kb_query_simple_events.add_argument("--report-date", default="")
    kb_query_simple_events.add_argument("--report-id", default="")
    kb_query_simple_events.add_argument("--event-name", default="")
    kb_query_simple_events.add_argument("--report-title", default="")

    kb_query_simple_event_detail = subparsers.add_parser(
        "kb-query-simple-event-detail",
        help="Query one simple event detail from DuckDB",
    )
    kb_query_simple_event_detail.add_argument("event_id")

    serve = subparsers.add_parser("serve", help="Run FastAPI service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8040)

    show_config = subparsers.add_parser("show-config", help="Show resolved config")
    kb_stats = subparsers.add_parser("kb-stats", help="Show DuckDB knowledge-base statistics")

    args = parser.parse_args()

    if args.command in {"import-file", "ingest-file"}:
        from .service import StockKBService

        service = StockKBService()
        print(json.dumps(service.import_file(args.path), indent=2, ensure_ascii=False))
        return

    if args.command in {"import-folder", "ingest-folder"}:
        try:
            from .service import StockKBService

            service = StockKBService()
            result = service.import_folder(args.folder, args.pattern)
        except (RuntimeError, FileNotFoundError, ValueError) as exc:
            result = {"status": "error", "error": str(exc)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.command in {"import-minio-object", "ingest-minio-object"}:
        from .service import StockKBService

        service = StockKBService()
        print(json.dumps(service.import_minio_object(args.bucket, args.object_name), indent=2, ensure_ascii=False))
        return

    if args.command in {"import-minio-prefix", "ingest-minio-prefix"}:
        from .service import StockKBService

        service = StockKBService()
        print(
            json.dumps(
                service.import_minio_prefix(
                    args.bucket,
                    prefix=args.prefix,
                    progress_callback=None if args.quiet_progress else _print_minio_prefix_progress,
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if args.command == "serve":
        from .api import create_app
        import uvicorn

        uvicorn.run(create_app(), host=args.host, port=args.port)
        return

    if args.command == "show-config":
        event_kb_settings = get_event_kb_settings(settings)
        print(
            json.dumps(
                {
                    "data_dir": str(settings.data_dir),
                    "duckdb_path": str(event_kb_settings.duckdb_path),
                    "llm_extract_enabled": event_kb_settings.llm_extract_enabled,
                    "llm_extract_base_url": event_kb_settings.llm_extract_base_url,
                    "llm_extract_model": event_kb_settings.llm_extract_model,
                    "llm_extract_temperature": event_kb_settings.llm_extract_temperature,
                    "llm_extract_timeout": event_kb_settings.llm_extract_timeout,
                    "llm_extract_max_blocks": event_kb_settings.llm_extract_max_blocks,
                    "minio_endpoint": settings.minio_endpoint,
                    "minio_default_bucket": settings.minio_default_bucket,
                    "minio_secure": settings.minio_secure,
                    "api_enable_local_ingest": settings.api_enable_local_ingest,
                    "local_ingest_allowed_roots": [str(path) for path in settings.local_ingest_allowed_roots],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    if args.command == "kb-stats":
        try:
            service = ExtractionService()
            result = service.kb_stats()
        except RuntimeError as exc:
            result = {"status": "error", "error": str(exc)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.command == "kb-query-simple-reports":
        filters = {}
        if args.stock_code:
            filters["stock_code"] = args.stock_code
        if args.stock_name:
            filters["stock_name"] = args.stock_name
        if args.report_date:
            filters["report_date"] = args.report_date
        if args.report_title:
            filters["report_title"] = args.report_title
        try:
            service = ExtractionService()
            result = service.kb_query_simple_reports(
                filters=filters,
                page=args.page,
                page_size=args.page_size,
                sort_by=args.sort_by,
                sort_order=args.sort_order,
            )
        except (RuntimeError, ValueError) as exc:
            result = {"status": "error", "error": str(exc)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.command == "kb-query-simple-events":
        filters = {}
        if args.stock_code:
            filters["stock_code"] = args.stock_code
        if args.stock_name:
            filters["stock_name"] = args.stock_name
        if args.report_date:
            filters["report_date"] = args.report_date
        if args.report_id:
            filters["report_id"] = args.report_id
        if args.event_name:
            filters["event_name"] = args.event_name
        if args.report_title:
            filters["report_title"] = args.report_title
        try:
            service = ExtractionService()
            result = service.kb_query_simple_events(
                filters=filters,
                page=args.page,
                page_size=args.page_size,
                sort_by=args.sort_by,
                sort_order=args.sort_order,
            )
        except (RuntimeError, ValueError) as exc:
            result = {"status": "error", "error": str(exc)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.command == "kb-query-simple-event-detail":
        try:
            service = ExtractionService()
            result = service.kb_query_simple_event_detail(args.event_id)
        except (RuntimeError, ValueError) as exc:
            result = {"status": "error", "error": str(exc)}
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
