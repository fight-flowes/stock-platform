"""Background daemon that runs the review-session GC.

Schedule:

* one ``startup`` run ``REVIEW_GC_STARTUP_DELAY_SECONDS`` seconds after the
  Flask process boots (default 5 minutes) — catches anything that piled up
  during the previous shutdown window;
* daily at ``REVIEW_GC_DAILY_AT`` local time (default 03:37) — the steady
  cadence; off-peak and explicitly *not* :00 / :30 to avoid colliding with
  every other house-keeping job in the environment.

Why a hand-rolled thread instead of APScheduler / cron:

* The job is simple and infrequent — a few HTTP calls every 24 hours;
* It must run inside the Flask process so the existing settings,
  ``StockkbProxyService`` and ``VibeTradingProxyService`` configurations
  apply without duplication;
* Threads are ``daemon=True`` so a process exit immediately tears them down
  without leaking workers.

The scheduler is intentionally a process-wide singleton that ignores
``Flask`` debug-mode reloader: when ``WERKZEUG_RUN_MAIN`` is unset (the
parent reloader process) we skip starting so we do not get duplicate runs.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from app.services.review_session_gc_service import ReviewSessionGCService
from app.settings import (
    REVIEW_GC_DAILY_AT,
    REVIEW_GC_ENABLED,
    REVIEW_GC_STARTUP_DELAY_SECONDS,
)


logger = logging.getLogger(__name__)


class ReviewGCScheduler:
    _started_lock = threading.Lock()
    _started: bool = False
    _thread: Optional[threading.Thread] = None
    _stop_event: Optional[threading.Event] = None

    @classmethod
    def start(cls) -> None:
        """Start the daemon thread once per process. Safe to call repeatedly."""
        with cls._started_lock:
            if cls._started:
                return

            if not REVIEW_GC_ENABLED:
                logger.info("review-gc-scheduler disabled by REVIEW_GC_ENABLED=false")
                cls._started = True
                return

            if _is_flask_reloader_parent():
                # Flask debug mode forks a worker process; only start the loop
                # in the worker so we don't double-run.
                logger.info("review-gc-scheduler skipped in Flask reloader parent")
                cls._started = True
                return

            cls._stop_event = threading.Event()
            cls._thread = threading.Thread(
                target=cls._run_loop,
                name="review-gc-scheduler",
                daemon=True,
            )
            cls._thread.start()
            cls._started = True
            logger.info(
                "review-gc-scheduler started (daily_at=%s, startup_delay=%ds)",
                REVIEW_GC_DAILY_AT,
                REVIEW_GC_STARTUP_DELAY_SECONDS,
            )

    @classmethod
    def stop(cls) -> None:
        """Signal the daemon thread to exit. Mostly for tests / shutdown hooks."""
        with cls._started_lock:
            if cls._stop_event is not None:
                cls._stop_event.set()

    @classmethod
    def _run_loop(cls) -> None:
        assert cls._stop_event is not None
        stop = cls._stop_event

        # Phase 1 — startup sweep. Use ``wait`` so the daemon reacts to stop().
        startup_delay = max(0, int(REVIEW_GC_STARTUP_DELAY_SECONDS or 0))
        if startup_delay and stop.wait(startup_delay):
            return
        cls._safe_run("startup")

        # Phase 2 — daily cadence.
        while not stop.is_set():
            sleep_seconds = _seconds_until_next_run(REVIEW_GC_DAILY_AT)
            if stop.wait(sleep_seconds):
                return
            cls._safe_run("daily")

    @staticmethod
    def _safe_run(label: str) -> None:
        try:
            result = ReviewSessionGCService.run_once()
            logger.info(
                "review-gc-scheduler %s pass deleted=%d cleared=%d errors=%d",
                label,
                result.orphan_sessions_deleted,
                result.dead_references_cleared,
                len(result.errors),
            )
        except Exception:  # pragma: no cover - safety net
            logger.exception("review-gc-scheduler %s pass crashed", label)


def _is_flask_reloader_parent() -> bool:
    flask_env = os.environ.get("FLASK_ENV", "")
    flask_debug = os.environ.get("FLASK_DEBUG", "")
    debug_mode = flask_env == "development" or flask_debug in {"1", "true", "True"}
    return bool(debug_mode and os.environ.get("WERKZEUG_RUN_MAIN") != "true")


def _seconds_until_next_run(daily_at: str) -> float:
    """Compute seconds until the next ``HH:MM`` (local time) occurrence.

    Falls back to 24 hours when the configured value is malformed; logs a
    warning so the misconfig is visible without taking down the daemon.
    """
    try:
        hour_str, minute_str = daily_at.split(":", 1)
        target_hour = int(hour_str)
        target_minute = int(minute_str)
        if not (0 <= target_hour < 24 and 0 <= target_minute < 60):
            raise ValueError(f"out of range: {daily_at}")
    except Exception as exc:
        logger.warning(
            "review-gc-scheduler invalid REVIEW_GC_DAILY_AT=%r (%s); defaulting to 24h",
            daily_at,
            exc,
        )
        return 24 * 60 * 60.0

    now = datetime.now()
    candidate = now.replace(
        hour=target_hour, minute=target_minute, second=0, microsecond=0
    )
    if candidate <= now:
        candidate = candidate + timedelta(days=1)
    delta = (candidate - now).total_seconds()
    return max(1.0, delta)
