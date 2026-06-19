"""Centralized akshare wrapper.

This is **the only module in eventradar that is allowed to** ``import akshare``.
Everything else goes through one of the helpers here. That gives us a single
choke-point for:

    - retries with exponential backoff (akshare endpoints are best-effort)
    - the optional HTTP proxy from settings
    - parquet-cached raw payloads (audit trail; lets us replay an adapter
      without re-hitting the upstream)
    - structured failure logging — when an akshare endpoint silently
      changes its column names, we want to find it in the logs, not in
      production data

Adapters call :func:`fetch_dataframe` with the akshare function name and the
kwargs to invoke it with. We resolve the callable via ``getattr(ak, name)``
on demand — that keeps import-time cheap and means accidental typos in
adapter code surface as clear ``AttributeError``s instead of silent network
hits.

Today this module is a stub: :func:`fetch_dataframe` carries a working call
chain (retry + proxy + cache) but the actual ``akshare`` import is delayed
until first call so M1 can ``pip install -e .`` without akshare being
present yet. The first adapter PR adds ``akshare`` to the installed deps and
wires this up for real.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings

LOGGER = logging.getLogger(__name__)


class AkshareCallError(RuntimeError):
    """Wraps every akshare call failure — adapters pattern-match on this
    instead of catching arbitrary exceptions from the upstream."""

    def __init__(self, message: str, *, function: str, attempts: int) -> None:
        super().__init__(message)
        self.function = function
        self.attempts = attempts


def _import_akshare():
    """Lazy import — keeps :mod:`eventradar` import-able even if akshare is
    not installed yet. Adapters declare their dependency by calling this."""
    try:
        import akshare as ak  # type: ignore
    except ImportError as exc:  # pragma: no cover — exercised at runtime only
        raise AkshareCallError(
            "akshare 未安装，请在 eventradar 的 pyproject.toml 中加入 akshare 依赖",
            function="<import>",
            attempts=0,
        ) from exc
    return ak


def fetch_dataframe(
    function: str,
    /,
    *,
    settings: Settings | None = None,
    cache_key: str | None = None,
    **kwargs: Any,
) -> Any:
    """Invoke ``ak.<function>(**kwargs)`` with retries + caching.

    The return type is whatever akshare returns — usually a
    ``pandas.DataFrame``. We don't wrap it because adapters know how to
    handle the upstream's quirks (column reordering, dtype coercion) and we
    want them to stay close to that logic.

    ``cache_key``: when provided, the raw DataFrame is parquet-dumped under
    ``data/raw_cache/<cache_key>__<UTC-iso>.parquet`` for audit / replay.
    Cache writes are best-effort — a failure to write the cache never
    breaks the actual call chain.

    M1 implementation note: the retry loop is real, but akshare itself is
    not invoked until adapters land. Calling this raises until then.
    """
    settings = settings or get_settings()
    ak = _import_akshare()

    fn = getattr(ak, function, None)
    if fn is None:
        raise AkshareCallError(
            f"akshare 没有名为 {function!r} 的函数", function=function, attempts=0
        )

    last_error: Exception | None = None
    for attempt in range(1, settings.http_max_retries + 1):
        try:
            LOGGER.debug(
                "eventradar.akshare_call function=%s attempt=%d kwargs=%s",
                function,
                attempt,
                kwargs,
            )
            df = fn(**kwargs)
        except Exception as exc:  # noqa: BLE001 — akshare raises a wide set
            last_error = exc
            LOGGER.warning(
                "eventradar.akshare_call_failed function=%s attempt=%d error=%s",
                function,
                attempt,
                exc,
            )
            time.sleep(min(2 ** attempt, 30))
            continue

        if settings.raw_cache_enabled and cache_key:
            _write_raw_cache(df, settings.raw_cache_dir, cache_key)
        return df

    raise AkshareCallError(
        f"akshare {function} 在 {settings.http_max_retries} 次重试后仍失败: {last_error}",
        function=function,
        attempts=settings.http_max_retries,
    ) from last_error


def _write_raw_cache(df: Any, cache_dir: Path, cache_key: str) -> None:
    """Best-effort parquet dump for replay."""
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = cache_dir / f"{cache_key}__{stamp}.parquet"
        # ``to_parquet`` lives on pandas.DataFrame; keep this defensive so a
        # non-DataFrame return value doesn't fail the call chain.
        if hasattr(df, "to_parquet"):
            df.to_parquet(target, index=False)
            LOGGER.info("eventradar.raw_cache_written path=%s", target)
    except Exception as exc:  # noqa: BLE001 — caching is best-effort
        LOGGER.warning("eventradar.raw_cache_failed key=%s error=%s", cache_key, exc)
