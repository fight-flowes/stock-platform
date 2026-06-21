"""FastAPI app for eventradar.

The contract here is locked in by ``calenderapp/backend/app/services/
eventradar_proxy_service.py`` — every field name and every endpoint path
is mirrored on the proxy side. Do not rename anything here without
updating the proxy in the same change.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import get_settings
from .service import EventradarService
# Importing the adapters package registers each adapter into the global
# ``ADAPTERS`` table. The API doesn't *call* adapters (writes are CLI-only)
# but /health and future per-source last-success-at queries need the
# registry populated.
from .sources import adapters as _adapters  # noqa: F401

LOGGER = logging.getLogger(__name__)


# --- request/response models -----------------------------------------------


class ListRequest(BaseModel):
    page: int = 1
    page_size: int = 20
    sort_by: str = "expected_at"
    sort_order: str = "asc"
    filters: dict[str, Any] = Field(default_factory=dict)


# --- app factory -----------------------------------------------------------


class _UTF8JSONResponse(JSONResponse):
    """JSONResponse that renders non-ASCII as UTF-8 (not \\uXXXX escapes).

    Starlette's default JSONResponse sets ``ensure_ascii=True``, which turns
    every Chinese character into six bytes of escape text. For an API whose
    primary payload is Chinese stock-event descriptions that's a lot of
    wasted bytes and unreadable logs. Subclass + override ``render`` to use
    ``json.dumps(..., ensure_ascii=False)``.
    """

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


def create_app() -> FastAPI:
    # default_response_class with ensure_ascii=False serves Chinese event text
    # as UTF-8 directly instead of \uXXXX escapes — keeps logs, browser devtools
    # and curl output human-readable.
    app = FastAPI(
        title="eventradar",
        version="0.1.0",
        default_response_class=JSONResponse,
    )
    # Starlette's JSONResponse defaults to ensure_ascii=True; override the
    # renderer so our Chinese event_name / event_content come back as UTF-8.
    app.router.default_response_class = _UTF8JSONResponse
    settings = get_settings()
    service = EventradarService(settings=settings)

    @app.get("/health")
    def health() -> dict[str, str]:
        # Static for now. Once M4 lands we'll surface "last_success_at"
        # per source so the calenderapp badge can show stale-data warnings.
        return {"status": "healthy", "upstream": "eventradar"}

    @app.post("/events/expected")
    def list_announcements(payload: ListRequest) -> dict[str, Any]:
        return service.list_announcements(
            page=payload.page,
            page_size=payload.page_size,
            sort_by=payload.sort_by,
            sort_order=payload.sort_order,
            filters=payload.filters,
        )

    @app.get("/events/expected/{event_id}")
    def get_announcement(event_id: str) -> dict[str, Any]:
        event = service.get_announcement(event_id)
        if not event:
            raise HTTPException(status_code=404, detail=f"event not found: {event_id}")
        return {"found": True, "event_id": event_id, "event": event}

    @app.get("/events/expected/filters/meta")
    def get_filter_meta() -> dict[str, Any]:
        return service.get_filter_meta()

    return app
