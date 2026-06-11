from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from .config import Settings, get_settings
from .event_kb.services import ExtractionService
from .minio_backend import (
    MinioMarkdownBackend,
    MinioMarkdownObject,
    build_minio_source_path,
)


class StockKBService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.minio = MinioMarkdownBackend(self.settings)
        self.extraction = ExtractionService(self.settings)

    def import_file(
        self,
        path: str,
        metadata_override: dict[str, Any] | None = None,
        *,
        enforce_local_ingest_policy: bool = False,
    ) -> dict[str, Any]:
        report_path = _resolve_local_path(
            path,
            self.settings,
            enforce_local_ingest_policy=enforce_local_ingest_policy,
            expect_directory=False,
        )
        _reject_metadata_override(metadata_override)
        return self.extraction.extract_file(str(report_path))

    def import_folder(
        self,
        folder: str,
        pattern: str = "**/*.md",
        metadata_override: dict[str, Any] | None = None,
        *,
        enforce_local_ingest_policy: bool = False,
    ) -> dict[str, Any]:
        root = _resolve_local_path(
            folder,
            self.settings,
            enforce_local_ingest_policy=enforce_local_ingest_policy,
            expect_directory=True,
        )
        _reject_metadata_override(metadata_override)
        return self.extraction.extract_folder(str(root), pattern)

    def import_minio_object(
        self,
        bucket: str,
        object_name: str,
        metadata_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        minio_object = self.minio.get_markdown_object(bucket, object_name)
        _reject_metadata_override(metadata_override)
        result = self._extract_minio_object(minio_object)
        result["bucket"] = minio_object.bucket
        result["object_name"] = minio_object.object_name
        result["source_path"] = minio_object.source_path
        result["etag"] = minio_object.etag
        result["last_modified"] = minio_object.last_modified
        return result

    def import_minio_prefix(
        self,
        bucket: str,
        prefix: str = "",
        metadata_override: dict[str, Any] | None = None,
        *,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        _reject_metadata_override(metadata_override)
        objects = self.minio.list_markdown_objects(bucket, prefix)
        results = []
        success = 0
        failed = 0
        total = len(objects)
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "listed",
                    "bucket": bucket,
                    "prefix": prefix,
                    "total": total,
                }
            )
        for index, object_name in enumerate(objects, start=1):
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "start",
                        "bucket": bucket,
                        "prefix": prefix,
                        "object_name": object_name,
                        "index": index,
                        "total": total,
                    }
                )
            try:
                result = self.import_minio_object(bucket, object_name)
                results.append(result)
                success += 1
                if progress_callback is not None:
                    progress_callback(
                        {
                            "phase": "success",
                            "bucket": bucket,
                            "prefix": prefix,
                            "object_name": object_name,
                            "index": index,
                            "total": total,
                            "report_id": result.get("report_id", ""),
                            "stock_code": result.get("stock_code", ""),
                            "stock_name": result.get("stock_name", ""),
                            "report_date": result.get("report_date", ""),
                            "simple_events": result.get("simple_events", 0),
                        }
                    )
            except Exception as exc:
                failed += 1
                error_result = {
                    "status": "error",
                    "bucket": bucket,
                    "object_name": object_name,
                    "source_path": build_minio_source_path(bucket, object_name),
                    "error": str(exc),
                }
                results.append(error_result)
                if progress_callback is not None:
                    progress_callback(
                        {
                            "phase": "error",
                            "bucket": bucket,
                            "prefix": prefix,
                            "object_name": object_name,
                            "index": index,
                            "total": total,
                            "error": str(exc),
                        }
                    )
        summary = {
            "bucket": bucket,
            "prefix": prefix,
            "success": success,
            "failed": failed,
            "results": results,
        }
        if progress_callback is not None:
            progress_callback(
                {
                    "phase": "done",
                    "bucket": bucket,
                    "prefix": prefix,
                    "total": total,
                    "success": success,
                    "failed": failed,
                }
            )
        return summary

    def ingest_file(
        self,
        path: str,
        metadata_override: dict[str, Any] | None = None,
        *,
        enforce_local_ingest_policy: bool = False,
    ) -> dict[str, Any]:
        return self.import_file(
            path,
            metadata_override,
            enforce_local_ingest_policy=enforce_local_ingest_policy,
        )

    def ingest_folder(
        self,
        folder: str,
        pattern: str = "**/*.md",
        *,
        enforce_local_ingest_policy: bool = False,
    ) -> dict[str, Any]:
        return self.import_folder(
            folder,
            pattern,
            enforce_local_ingest_policy=enforce_local_ingest_policy,
        )

    def ingest_minio_object(
        self,
        bucket: str,
        object_name: str,
        metadata_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.import_minio_object(bucket, object_name, metadata_override)

    def ingest_minio_prefix(
        self,
        bucket: str,
        prefix: str = "",
        metadata_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.import_minio_prefix(bucket, prefix, metadata_override)

    def _extract_minio_object(self, item: MinioMarkdownObject) -> dict[str, Any]:
        with TemporaryDirectory(prefix="stockkb-minio-") as tmpdir:
            temp_path = Path(tmpdir) / item.source_name
            temp_path.write_text(item.text, encoding="utf-8")
            return self.extraction.extract_file_with_source(
                str(temp_path),
                source_path=item.source_path,
                source_name=item.source_name,
                parent_name=item.parent_name,
                source_metadata={
                    "minio_bucket": item.bucket,
                    "minio_object_name": item.object_name,
                    "minio_etag": item.etag,
                    "minio_last_modified": item.last_modified,
                },
            )


StockRAGService = StockKBService


def _resolve_local_path(
    path: str,
    settings: Settings,
    *,
    enforce_local_ingest_policy: bool,
    expect_directory: bool,
) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(resolved)

    if expect_directory and not resolved.is_dir():
        raise ValueError(f"Expected a directory path, got: {resolved}")
    if not expect_directory and not resolved.is_file():
        raise ValueError(f"Expected a file path, got: {resolved}")

    if enforce_local_ingest_policy:
        _enforce_local_ingest_policy(resolved, settings)

    return resolved


def _enforce_local_ingest_policy(path: Path, settings: Settings) -> None:
    allowed_roots = settings.local_ingest_allowed_roots
    if not allowed_roots:
        raise PermissionError(
            "API local ingest is enabled but LOCAL_INGEST_ALLOWED_ROOTS is empty. "
            "Set allowed roots explicitly before using local ingest endpoints."
        )

    if path.is_file() and path.suffix.lower() != ".md":
        raise PermissionError(f"Local ingest only allows markdown files: {path}")

    for root in allowed_roots:
        try:
            path.relative_to(root)
            return
        except ValueError:
            continue

    raise PermissionError(f"Path is outside LOCAL_INGEST_ALLOWED_ROOTS: {path}")


def _reject_metadata_override(metadata_override: dict[str, Any] | None) -> None:
    if metadata_override:
        raise ValueError(
            "Structured knowledge-base imports do not support metadata overrides. "
            "Please update the markdown report content or source filename instead."
        )
