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

import logging
from dataclasses import dataclass
from typing import Any, Callable

from .config import Settings, get_settings
from .normalize import ExpectedEvent
from .storage import (
    filter_meta as _filter_meta,
    get_event as _get_event,
    list_events as _list_events,
    open_primary,
    open_replica,
    publish_replica,
    upsert_events,
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
