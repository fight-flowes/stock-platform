from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .api_models import MarketEventListRequestModel
from .config import get_settings
from .event_kb.services import ExtractionService


class IngestFileRequest(BaseModel):
    path: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestFolderRequest(BaseModel):
    folder: str
    pattern: str = "**/*.md"


class IngestMinioObjectRequest(BaseModel):
    bucket: str
    object_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestMinioPrefixRequest(BaseModel):
    bucket: str
    prefix: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimpleQueryRequest(BaseModel):
    page: int = 1
    page_size: int = 20
    sort_by: str = "report_date"
    sort_order: str = "desc"
    filters: dict[str, Any] = Field(default_factory=dict)


def create_app() -> FastAPI:
    app = FastAPI(title="stockkb", version="0.2.0")
    settings = get_settings()

    def build_stock_service():
        from .service import StockKBService

        return StockKBService()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.api_enable_local_ingest:
        @app.post("/ingest/file")
        @app.post("/kb/import/file")
        def ingest_file(request: IngestFileRequest) -> dict[str, Any]:
            try:
                service = build_stock_service()
                return service.ingest_file(
                    request.path,
                    request.metadata,
                    enforce_local_ingest_policy=True,
                )
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.post("/ingest/folder")
        @app.post("/kb/import/folder")
        def ingest_folder(request: IngestFolderRequest) -> dict[str, Any]:
            try:
                service = build_stock_service()
                return service.ingest_folder(
                    request.folder,
                    request.pattern,
                    enforce_local_ingest_policy=True,
                )
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/ingest/minio/object")
    @app.post("/kb/import/minio/object")
    def ingest_minio_object(request: IngestMinioObjectRequest) -> dict[str, Any]:
        service = build_stock_service()
        return service.ingest_minio_object(request.bucket, request.object_name, request.metadata)

    @app.post("/ingest/minio/prefix")
    @app.post("/kb/import/minio/prefix")
    def ingest_minio_prefix(request: IngestMinioPrefixRequest) -> dict[str, Any]:
        service = build_stock_service()
        return service.ingest_minio_prefix(request.bucket, request.prefix, request.metadata)

    @app.post("/kb/simple/reports")
    def kb_query_simple_reports(request: SimpleQueryRequest) -> dict[str, Any]:
        try:
            kb_service = ExtractionService()
            return kb_service.kb_query_simple_reports(
                filters=request.filters,
                page=request.page,
                page_size=request.page_size,
                sort_by=request.sort_by,
                sort_order=request.sort_order,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/kb/simple/events")
    def kb_query_simple_events(request: SimpleQueryRequest) -> dict[str, Any]:
        try:
            kb_service = ExtractionService()
            return kb_service.kb_query_simple_events(
                filters=request.filters,
                page=request.page,
                page_size=request.page_size,
                sort_by=request.sort_by or "event_time_normalized",
                sort_order=request.sort_order,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/kb/simple/market-events")
    def kb_query_market_events(request: MarketEventListRequestModel) -> dict[str, Any]:
        try:
            kb_service = ExtractionService()
            return kb_service.kb_query_market_events(
                filters=request.filters.model_dump(),
                page=request.page,
                page_size=request.page_size,
                sort_by=request.sort_by or "latest_active_date",
                sort_order=request.sort_order,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/kb/simple/market-events/filters/meta")
    def kb_query_market_event_filter_meta() -> dict[str, Any]:
        try:
            kb_service = ExtractionService()
            return kb_service.kb_query_market_event_filter_meta()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/kb/simple/market-events/{event_key}")
    def kb_query_market_event_detail(event_key: str) -> dict[str, Any]:
        try:
            kb_service = ExtractionService()
            result = kb_service.kb_query_market_event_detail(event_key)
            if not result.get("found", False):
                raise HTTPException(status_code=404, detail=f"Market event not found: {event_key}")
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/kb/simple/market-events/{event_key}/timeline")
    def kb_query_market_event_timeline(event_key: str) -> dict[str, Any]:
        try:
            kb_service = ExtractionService()
            return kb_service.kb_query_market_event_timeline(event_key)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/kb/simple/events/{event_id}")
    def kb_query_simple_event_detail(event_id: str) -> dict[str, Any]:
        try:
            kb_service = ExtractionService()
            result = kb_service.kb_query_simple_event_detail(event_id)
            if not result.get("found", False):
                raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/kb/simple/events/{event_id}/favorite")
    def kb_mark_simple_event_favorite(event_id: str) -> dict[str, Any]:
        try:
            kb_service = ExtractionService()
            result = kb_service.kb_set_simple_event_favorite(event_id, is_favorite=True)
            if not result.get("found", False):
                raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete("/kb/simple/events/{event_id}/favorite")
    def kb_unmark_simple_event_favorite(event_id: str) -> dict[str, Any]:
        try:
            kb_service = ExtractionService()
            result = kb_service.kb_set_simple_event_favorite(event_id, is_favorite=False)
            if not result.get("found", False):
                raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/kb/stats")
    def kb_stats() -> dict[str, Any]:
        try:
            kb_service = ExtractionService()
            return kb_service.kb_stats()
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


app = create_app()
