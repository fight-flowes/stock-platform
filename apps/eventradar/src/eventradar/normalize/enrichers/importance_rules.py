"""Compute a 0–3 importance score for an event.

Composition (additive, clamped to [0, 3]):

    base                                         1
    + 1  event_type is high-impact               (restructuring / unlock /
                                                  earnings_forecast /
                                                  secondary_offering)
    + 1  event touches a leader stock            (from leader_scorer)
    + 1  expected_at_end is within 30 days       (imminent forward milestone)

The score is a prioritization hint for the UI, not a trading signal. A 3
means "large-cap + high-impact-type + imminent" — worth surfacing at the
top of the announcements list. A 0 (only reachable if base were 0, which
it isn't by default) would mean "ignore".

Kept as a pure function so it can be re-scored cheaply when any input
changes (e.g. after stock_meta refresh bumps a stock into leader territory).
"""

from __future__ import annotations

from datetime import date, timedelta

# Event types that move prices when disclosed. Tuned for the gsdt feed's
# vocabulary; M2 sources will add earnings_forecast etc. which are already
# here.
HIGH_IMPACT_TYPES: frozenset[str] = frozenset(
    {
        "restructuring",
        "unlock",
        "earnings_forecast",
        "secondary_offering",
    }
)

IMMINENCE_WINDOW_DAYS = 30


def compute_importance(
    *,
    event_type: str,
    has_leader: bool,
    expected_at_end: date | None,
    today: date | None = None,
) -> int:
    """Return an importance score in [0, 3].

    ``today`` is injectable for deterministic tests; defaults to
    ``date.today()``.
    """
    score = 1
    if event_type in HIGH_IMPACT_TYPES:
        score += 1
    if has_leader:
        score += 1
    if expected_at_end is not None:
        ref = today or date.today()
        if ref <= expected_at_end <= ref + timedelta(days=IMMINENCE_WINDOW_DAYS):
            score += 1
    return max(0, min(3, score))
