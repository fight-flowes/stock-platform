"""Deterministic id helpers for ExpectedEvent rows.

``event_id`` and ``source_fingerprint`` are both derived — re-ingesting the
same upstream row produces the same ids, which is what makes upserts safe.

Naming convention:
    event_id           = sha1(source + ":" + source_fingerprint)[:16]
    source_fingerprint = sha1(stable upstream key parts joined with "|")[:16]

We use sha1 + truncate-to-16 because:
    - 16 hex chars is short enough to read in logs;
    - 64 bits of entropy is overkill for our row counts (<10M);
    - sha1 is fast and collision-resistant for non-adversarial inputs.

If you ever need to change the hashing, bump :data:`FINGERPRINT_VERSION` and
treat existing rows as obsolete (purge + re-ingest). Adapters must NOT do
their own hashing; always go through :func:`build_event_id` /
:func:`build_source_fingerprint`.
"""

from __future__ import annotations

import hashlib
from typing import Iterable

FINGERPRINT_VERSION = 1


def _sha1_short(value: str, length: int = 16) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return digest[:length]


def build_source_fingerprint(parts: Iterable[object]) -> str:
    """Stable hash of the upstream's natural key.

    Pass the smallest set of fields that uniquely identify the upstream row.
    Empty / None parts are coerced to "" so optional columns don't shift the
    hash. Order matters — keep adapter-side code consistent.
    """
    joined = "|".join("" if p is None else str(p) for p in parts)
    return _sha1_short(f"v{FINGERPRINT_VERSION}|{joined}")


def build_event_id(source: str, source_fingerprint: str) -> str:
    """Deterministic primary key for the row in DuckDB."""
    return _sha1_short(f"{source}:{source_fingerprint}")
