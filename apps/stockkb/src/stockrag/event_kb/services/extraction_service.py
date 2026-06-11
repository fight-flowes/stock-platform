from __future__ import annotations

from pathlib import Path
from typing import Any

from ...config import Settings, get_settings
from ..config import EventKBSettings, get_event_kb_settings
from ..pipeline import build_simple_report_bundle
from ..storage import DuckDBBackend


class ExtractionService:
    def __init__(
        self,
        settings: Settings | None = None,
        kb_settings: EventKBSettings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.kb_settings = kb_settings or get_event_kb_settings(self.settings)
        self.duckdb = DuckDBBackend(self.kb_settings.duckdb_path, self.kb_settings)

    def extract_file(self, path: str) -> dict[str, Any]:
        return self.extract_file_with_source(path)

    def extract_file_with_source(
        self,
        path: str,
        *,
        source_path: str | None = None,
        source_name: str | None = None,
        parent_name: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        report_path = _resolve_path(path, expect_directory=False)
        bundle = build_simple_report_bundle(
            report_path,
            self.settings,
            kb_settings=self.kb_settings,
            source_path=source_path,
            source_name=source_name,
            parent_name=parent_name,
        )
        if source_metadata:
            for key, value in source_metadata.items():
                if hasattr(bundle.report, key):
                    setattr(bundle.report, key, str(value))
        self.duckdb.upsert_simple_bundle(bundle)
        return {
            "status": "success",
            "path": str(report_path),
            "report_id": bundle.report.report_id,
            "stock_code": bundle.report.stock_code,
            "stock_name": bundle.report.stock_name,
            "report_date": bundle.report.report_date,
            "simple_events": len(bundle.events),
            "risk_summary": bundle.report.risk_summary,
            "duckdb_path": str(self.kb_settings.duckdb_path),
        }

    def extract_folder(self, folder: str, pattern: str = "**/*.md") -> dict[str, Any]:
        root = _resolve_path(folder, expect_directory=True)
        results = []
        success = 0
        failed = 0
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            try:
                results.append(self.extract_file_with_source(str(path)))
                success += 1
            except Exception as exc:
                failed += 1
                results.append(
                    {
                        "status": "error",
                        "path": str(path),
                        "error": str(exc),
                    }
                )
        return {
            "success": success,
            "failed": failed,
            "results": results,
            "duckdb_path": str(self.kb_settings.duckdb_path),
        }

    def kb_stats(self) -> dict[str, Any]:
        return {
            "duckdb_path": str(self.kb_settings.duckdb_path),
            **self.duckdb.stats(),
        }

    def kb_query_simple_events(
        self,
        *,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "event_time_normalized",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        result = self.duckdb.query_simple_events(
            filters=filters or {},
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        result["duckdb_path"] = str(self.kb_settings.duckdb_path)
        return result

    def kb_query_simple_reports(
        self,
        *,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "report_date",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        result = self.duckdb.query_simple_reports(
            filters=filters or {},
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        result["duckdb_path"] = str(self.kb_settings.duckdb_path)
        return result

    def kb_query_simple_event_detail(self, event_id: str) -> dict[str, Any]:
        result = self.duckdb.query_simple_event_detail(event_id)
        result["duckdb_path"] = str(self.kb_settings.duckdb_path)
        return result

    def kb_set_simple_event_favorite(self, event_id: str, *, is_favorite: bool) -> dict[str, Any]:
        result = self.duckdb.set_simple_event_favorite(event_id, is_favorite=is_favorite)
        result["duckdb_path"] = str(self.kb_settings.duckdb_path)
        return result

    def kb_query_market_events(
        self,
        *,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "latest_active_date",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        result = self.duckdb.query_market_events(
            filters=filters or {},
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        result["duckdb_path"] = str(self.kb_settings.duckdb_path)
        return result

    def kb_query_market_event_detail(self, event_key: str) -> dict[str, Any]:
        result = self.duckdb.query_market_event_detail(event_key)
        result["duckdb_path"] = str(self.kb_settings.duckdb_path)
        return result

    def kb_query_market_event_timeline(self, event_key: str) -> dict[str, Any]:
        result = self.duckdb.query_market_event_timeline(event_key)
        result["duckdb_path"] = str(self.kb_settings.duckdb_path)
        return result

    def kb_query_market_event_filter_meta(self) -> dict[str, Any]:
        result = self.duckdb.query_market_event_filter_meta()
        result["duckdb_path"] = str(self.kb_settings.duckdb_path)
        return result


def _resolve_path(path: str, *, expect_directory: bool) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(resolved)
    if expect_directory and not resolved.is_dir():
        raise ValueError(f"Expected a directory path, got: {resolved}")
    if not expect_directory and not resolved.is_file():
        raise ValueError(f"Expected a file path, got: {resolved}")
    return resolved
