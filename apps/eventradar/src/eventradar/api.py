"""FastAPI app for eventradar.

The contract here is locked in by ``calenderapp/backend/app/services/
eventradar_proxy_service.py`` — every field name and every endpoint path
is mirrored on the proxy side. Do not rename anything here without
updating the proxy in the same change.

In M1 this server only serves an empty database — every endpoint returns
a well-formed but empty payload. That's enough for ``calenderapp`` to point
``EVENTRADAR_API_BASE_URL`` at us today; rows show up as adapters land.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import get_settings
from .service import EventradarService

LOGGER = logging.getLogger(__name__)


# --- request/response models -----------------------------------------------


class ListRequest(BaseModel):
    page: int = 1
    page_size: int = 20
    sort_by: str = "expected_at"
    sort_order: str = "asc"
    filters: dict[str, Any] = Field(default_factory=dict)


# --- app factory -----------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(title="eventradar", version="0.0.1")
    settings = get_settings()
    service = EventradarService(settings=settings)

    @app.get("/health")
    def health() -> dict[str, str]:
        # Static for now. Once adapters land we'll surface "last_success_at"
        # per source so the calenderapp badge can show stale-data warnings.
        return {"status": "healthy", "upstream": "eventradar"}

    @app.post("/events/expected")
    def list_announcements(payload: ListRequest) -> dict[str, Any]:
        try:
            return service.list_announcements(
                page=payload.page,
                page_size=payload.page_size,
                sort_by=payload.sort_by,
                sort_order=payload.sort_order,
                filters=payload.filters,
            )
        except NotImplementedError as exc:
            # Skeleton state — return an empty paginated payload instead of
            # 500-ing. Lets calenderapp's proxy hit us today without errors.
            LOGGER.info("eventradar.list_announcements skeleton: %s", exc)
            return _empty_list_payload(payload)

    @app.get("/events/expected/{event_id}")
    def get_announcement(event_id: str) -> dict[str, Any]:
        try:
            event = service.get_announcement(event_id)
        except NotImplementedError:
            event = None
        if not event:
            raise HTTPException(status_code=404, detail=f"event not found: {event_id}")
        return {"found": True, "event_id": event_id, "event": event}

    @app.get("/events/expected/filters/meta")
    def get_filter_meta() -> dict[str, Any]:
        try:
            return service.get_filter_meta()
        except NotImplementedError:
            return {
                "industries": [],
                "themes": [],
                "event_types": [],
                "scopes": [],
                "date_min": "",
                "date_max": "",
            }

    return app


def _empty_list_payload(req: ListRequest) -> dict[str, Any]:
    return {
        "items": [],
        "count": 0,
        "total_count": 0,
        "page": req.page,
        "page_size": req.page_size,
        "sort_by": req.sort_by,
        "sort_order": req.sort_order,
        "has_more": False,
    }
