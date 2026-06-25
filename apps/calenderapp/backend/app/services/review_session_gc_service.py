"""Garbage-collect Vibe-Trading sessions tied to event review.

Two situations are cleaned up here:

1. **Orphan sessions** – ``Event Review *`` sessions that exist upstream but no
   ``kb_market_event_review.vibe_session_id`` row references them. These can
   only show up if something outside the review flow created them (legacy
   data, manual debugging) — the per-event reuse mechanism in
   ``EventReviewService._acquire_session_id`` no longer produces new ones.
2. **Dead references** – DuckDB rows whose ``vibe_session_id`` points at a
   session the upstream has already removed (manual delete, Vibe-Trading
   reset, etc.). The pointer is wiped so the next review recreates a fresh
   session instead of failing the probe loop.

Scope is intentionally narrow — we only ever touch sessions whose ``title``
starts with ``"Event Review "``. Anything else (interactive sessions, other
prefixes) is ignored even if it looks orphaned.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.stockkb_proxy_service import StockkbProxyError, StockkbProxyService
from app.services.vibe_trading_proxy_service import VibeTradingProxyError, VibeTradingProxyService
from app.settings import REVIEW_GC_MAX_DELETE_PER_RUN


logger = logging.getLogger(__name__)

EVENT_REVIEW_TITLE_PREFIX = "Event Review "


@dataclass
class GCRunResult:
    """Outcome of a single GC sweep, exposed via the management endpoint."""

    started_at: str
    finished_at: str = ""
    duration_seconds: float = 0.0
    upstream_sessions_scanned: int = 0
    event_review_sessions: int = 0
    referenced_session_ids: int = 0
    orphan_sessions_found: int = 0
    orphan_sessions_deleted: int = 0
    dead_references_found: int = 0
    dead_references_cleared: int = 0
    skipped_due_to_cap: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": round(self.duration_seconds, 3),
            "upstream_sessions_scanned": self.upstream_sessions_scanned,
            "event_review_sessions": self.event_review_sessions,
            "referenced_session_ids": self.referenced_session_ids,
            "orphan_sessions_found": self.orphan_sessions_found,
            "orphan_sessions_deleted": self.orphan_sessions_deleted,
            "dead_references_found": self.dead_references_found,
            "dead_references_cleared": self.dead_references_cleared,
            "skipped_due_to_cap": self.skipped_due_to_cap,
            "errors": list(self.errors),
        }


class ReviewSessionGCService:
    """Single-pass GC. Thread-safe in the sense that ``run_once`` uses no
    shared mutable state; the scheduler caller serializes runs anyway.
    """

    _last_result_lock = threading.Lock()
    _last_result: Optional[GCRunResult] = None

    @classmethod
    def last_result(cls) -> Optional[dict[str, Any]]:
        with cls._last_result_lock:
            return cls._last_result.as_dict() if cls._last_result else None

    @classmethod
    def run_once(cls, *, dry_run: bool = False) -> GCRunResult:
        result = GCRunResult(started_at=datetime.now(timezone.utc).isoformat())
        started_monotonic = _monotonic()

        try:
            upstream = cls._list_event_review_sessions(result)
            referenced = cls._collect_referenced_session_ids(result)

            cls._delete_orphan_sessions(upstream, referenced, result, dry_run=dry_run)
            cls._clear_dead_references(referenced, upstream, result, dry_run=dry_run)
        except Exception as exc:  # pragma: no cover - top-level safety net
            result.errors.append(f"unexpected:{type(exc).__name__}:{exc}")
            logger.exception("review-session-gc unexpected failure")
        finally:
            result.finished_at = datetime.now(timezone.utc).isoformat()
            result.duration_seconds = _monotonic() - started_monotonic
            with cls._last_result_lock:
                cls._last_result = result
            logger.info("review-session-gc finished: %s", result.as_dict())

        return result

    # --- internals -----------------------------------------------------------

    @classmethod
    def _list_event_review_sessions(cls, result: GCRunResult) -> dict[str, dict[str, Any]]:
        try:
            sessions = VibeTradingProxyService.list_sessions(limit=200)
        except VibeTradingProxyError as exc:
            result.errors.append(f"list_sessions:{exc}")
            logger.warning("review-session-gc cannot list upstream sessions: %s", exc)
            return {}

        result.upstream_sessions_scanned = len(sessions)
        event_review = {
            str(item.get("session_id") or ""): item
            for item in sessions
            if str(item.get("title") or "").startswith(EVENT_REVIEW_TITLE_PREFIX)
            and str(item.get("session_id") or "")
        }
        result.event_review_sessions = len(event_review)
        return event_review

    @classmethod
    def _collect_referenced_session_ids(cls, result: GCRunResult) -> dict[str, str]:
        """Return ``vibe_session_id -> event_key`` for every review row that
        currently points at an upstream session. Does NOT touch DuckDB writes.
        """
        try:
            entries = StockkbProxyService.list_market_event_review_session_ids()
        except StockkbProxyError as exc:
            result.errors.append(f"list_review_session_ids:{exc}")
            logger.warning(
                "review-session-gc cannot list referenced session ids: %s", exc
            )
            return {}

        referenced: dict[str, str] = {}
        for item in entries:
            sid = str(item.get("vibe_session_id") or "").strip()
            event_key = str(item.get("event_key") or "").strip()
            if sid and event_key and sid not in referenced:
                referenced[sid] = event_key

        result.referenced_session_ids = len(referenced)
        return referenced

    @classmethod
    def _delete_orphan_sessions(
        cls,
        upstream: dict[str, dict[str, Any]],
        referenced: dict[str, str],
        result: GCRunResult,
        *,
        dry_run: bool,
    ) -> None:
        orphans = [sid for sid in upstream if sid not in referenced]
        result.orphan_sessions_found = len(orphans)

        budget = max(0, REVIEW_GC_MAX_DELETE_PER_RUN)
        targets = orphans[:budget]
        if len(orphans) > budget:
            result.skipped_due_to_cap = len(orphans) - budget

        for sid in targets:
            if dry_run:
                result.orphan_sessions_deleted += 1
                continue
            try:
                VibeTradingProxyService.delete_session(session_id=sid)
                result.orphan_sessions_deleted += 1
            except VibeTradingProxyError as exc:
                result.errors.append(f"delete_session:{sid}:{exc}")
                logger.warning("review-session-gc failed to delete %s: %s", sid, exc)

    @classmethod
    def _clear_dead_references(
        cls,
        referenced: dict[str, str],
        upstream: dict[str, dict[str, Any]],
        result: GCRunResult,
        *,
        dry_run: bool,
    ) -> None:
        # Dead reference = DuckDB knows about session id X, but X is not in the
        # upstream list anymore. Be a bit defensive and also confirm with a
        # direct GET in case list_sessions was paginated/truncated.
        suspect_ids = [sid for sid in referenced if sid not in upstream]
        confirmed: list[tuple[str, str]] = []
        for sid in suspect_ids:
            try:
                if VibeTradingProxyService.get_session(session_id=sid) is None:
                    confirmed.append((sid, referenced[sid]))
            except VibeTradingProxyError as exc:
                result.errors.append(f"probe_session:{sid}:{exc}")

        result.dead_references_found = len(confirmed)

        for sid, event_key in confirmed:
            if dry_run:
                result.dead_references_cleared += 1
                continue
            try:
                # The upstream PUT validator requires review_status to be
                # present on every request, so we read the existing row first
                # and pass it through unchanged — only ``vibe_session_id`` is
                # cleared. This keeps the rest of the verdict (event_truth,
                # confidence, headline, ...) untouched.
                review = (
                    StockkbProxyService.get_market_event_review(event_key).get("review") or {}
                )
                StockkbProxyService.put_market_event_review(
                    event_key,
                    {
                        "review_status": str(review.get("review_status") or "completed"),
                        "vibe_session_id": "",
                    },
                )
                result.dead_references_cleared += 1
            except StockkbProxyError as exc:
                result.errors.append(f"clear_dead_ref:{event_key}:{exc}")
                logger.warning(
                    "review-session-gc failed to clear vibe_session_id for %s: %s",
                    event_key,
                    exc,
                )


def _monotonic() -> float:
    # Imported lazily so that test harnesses can monkey-patch without a hard
    # module-level binding to ``time``.
    from time import monotonic

    return monotonic()
