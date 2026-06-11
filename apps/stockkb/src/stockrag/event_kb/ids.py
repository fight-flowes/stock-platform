from __future__ import annotations

import hashlib


def stable_id(*parts: object) -> str:
    payload = "::".join(str(part) for part in parts if part is not None)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()
