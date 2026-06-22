"""Extract forward-looking dates from free-text ``event_content``.

The gsdt feed's ``expected_at`` is the *disclosure* date (when the company
filed the announcement), not the date the underlying event happens. The
real event date — when known — is buried inside the Chinese free text of
``具体事项``. For the guarantee/pledge/restructuring disclosures that dominate
gsdt, the most common forward-looking anchor is an **expiry/endpoint date**
("担保期限至 2027 年 6 月 3 日", "质押到期日 2028-6-30"). This parser surfaces
those as ``expected_at_end``.

Honest caveat (recorded in the M3 plan): for the current gsdt-only data
these parsed dates are mostly guarantee/pledge *expiry* endpoints, not
catalytic event schedules. The parser is still worth building because (a)
it gives the only forward-looking signal gsdt has, and (b) M2 sources
(业绩预告/解禁日历) will produce genuinely catalytic future dates that flow
through the same code.

Strategy:
    1. Regex-scan for Chinese + ISO-ish date tokens in the content.
    2. Keep only dates strictly later than the disclosure date (``expected_at``)
       — past dates are just historical context ("于 2025 年 11 月 28 日签署").
    3. Of the future dates, pick the *earliest* — that's the nearest
       forward-looking milestone, which is the most actionable. Store it as
       ``expected_at_end``.
    4. ``time_certainty`` reflects parser confidence: a full YYYY-M-D match
       is ``confirmed_date``; a month-only match (rare in this feed) is
       ``month``.

This module is pure — no I/O, no akshare. Safe to unit-test in isolation.
"""

from __future__ import annotations

import logging
import re
from datetime import date

LOGGER = logging.getLogger(__name__)

# Order matters: the YYYY年M月D日 form is checked before the month-only form
# so "2026年6月25日" matches the full-date group, not the month group.
# Each pattern's groups are positional (year, month, day) or (year, month).
_FULL_DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 2026年6月25日 / 2026年06月25日
    re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"),
    # 2026-6-25 / 2026-06-25 / 2026/6/25
    re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})"),
    # 2026.6.25
    re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})"),
)
# Month-only — only consulted when no full-date match fires for that span.
# The lookahead ``(?![0-9日])`` is critical: it prevents matching the
# year+month prefix of a full date like "2026年6月12日" (where a day digit
# follows 月). Without it, a past full date's "2026年6月" would leak through
# as a month-only future date (end-of-June) — a false positive.
_MONTH_ONLY_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月(?![0-9日])")

# Sanity bounds — a "real" A-share event date is within ~20 years of today.
# Anything outside is almost certainly a misparsed number (e.g. a 2023 share
# count picked up as a year). Keeps garbage out of expected_at_end.
_MIN_YEAR = 2000
_MAX_YEAR = 2100


def _safe_date(year: int, month: int, day: int | None) -> date | None:
    try:
        if day is None:
            # Month-only: anchor to the last day of the month so a "month"
            # certainty date sorts after any confirmed date in that month.
            import calendar

            last = calendar.monthrange(year, month)[1]
            return date(year, month, last)
        return date(year, month, day)
    except ValueError:
        return None


def parse_future_date(
    content: str | None,
    *,
    disclosure_date: date,
) -> tuple[date | None, str]:
    """Return ``(expected_at_end, time_certainty)`` for the earliest future
    date found in ``content`` that is later than ``disclosure_date``.

    Returns ``(None, "")`` when no future date is found — the caller leaves
    ``expected_at_end`` untouched.
    """
    if not content:
        return None, ""

    # Collect every full-date match with its span so we can later fall back
    # to month-only on text the full patterns missed.
    future_full: list[date] = []
    for pat in _FULL_DATE_PATTERNS:
        for m in pat.finditer(content):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if not (_MIN_YEAR <= y <= _MAX_YEAR):
                continue
            parsed = _safe_date(y, mo, d)
            if parsed and parsed > disclosure_date:
                future_full.append(parsed)

    if future_full:
        # Earliest future date = nearest forward-looking milestone.
        return min(future_full), "confirmed_date"

    # Fall back to month-only matches that weren't part of a full date.
    future_months: list[date] = []
    for m in _MONTH_ONLY_PATTERN.finditer(content):
        y, mo = int(m.group(1)), int(m.group(2))
        if not (_MIN_YEAR <= y <= _MAX_YEAR):
            continue
        parsed = _safe_date(y, mo, None)
        if parsed and parsed > disclosure_date:
            future_months.append(parsed)

    if future_months:
        return min(future_months), "month"

    return None, ""
