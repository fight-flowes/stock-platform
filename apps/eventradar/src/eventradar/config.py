"""Runtime configuration for eventradar.

Mirrors the shape of ``stockkb.config`` so the platform stays consistent.
Loads ``.env`` at the project root if present; everything is overridable via
environment variables. Keep this file dependency-light — only stdlib +
``python-dotenv`` so importing it never triggers heavy adapter imports.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# apps/eventradar/src/eventradar/config.py → apps/eventradar/
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=False)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw is not None and raw.strip() else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    root_dir: Path = ROOT_DIR
    data_dir: Path = Path(os.getenv("EVENTRADAR_DATA_DIR", str(ROOT_DIR / "data")))

    # DuckDB primary file — written by the CLI ingestion jobs.
    duckdb_path: Path = Path(
        os.getenv("EVENTRADAR_DUCKDB_PATH", str(ROOT_DIR / "data" / "eventradar.duckdb"))
    )
    # DuckDB read-only replica — what the FastAPI server opens. The CLI
    # publishes a snapshot here after each successful write so API readers
    # never contend with writers. See ``storage.duckdb_backend.publish_replica``.
    duckdb_read_path: Path = Path(
        os.getenv(
            "EVENTRADAR_DUCKDB_READ_PATH",
            str(ROOT_DIR / "data" / "eventradar.read.duckdb"),
        )
    )

    # Raw upstream payloads — parquet files keyed by (source, fetched_at).
    # Lets us replay history when an adapter changes, or audit a row that
    # disagrees with the upstream UI.
    raw_cache_dir: Path = Path(
        os.getenv("EVENTRADAR_RAW_CACHE_DIR", str(ROOT_DIR / "data" / "raw_cache"))
    )

    # Network defaults shared by every adapter.
    http_timeout: int = _env_int("EVENTRADAR_HTTP_TIMEOUT", 30)
    http_max_retries: int = _env_int("EVENTRADAR_HTTP_MAX_RETRIES", 3)
    http_proxy: str = os.getenv("EVENTRADAR_HTTP_PROXY", "").strip()

    # Server defaults.
    api_host: str = os.getenv("EVENTRADAR_API_HOST", "0.0.0.0")
    api_port: int = _env_int("EVENTRADAR_API_PORT", 8050)

    # Future toggles — kept here so adapters never reach for os.environ.
    raw_cache_enabled: bool = _env_bool("EVENTRADAR_RAW_CACHE_ENABLED", True)

    # Enrichment (M3). A stock whose float market cap (流通市值, in CNY) is at
    # or above this threshold is tagged as a 龙头/leader. Default 500 亿 — high
    # enough that only large-caps qualify, low enough to catch sector leaders.
    # Override via env for tuning without a code change.
    leader_float_mv_threshold: float = float(
        os.getenv("EVENTRADAR_LEADER_FLOAT_MV", str(500 * 10**8))
    )

    # A1 — tushare integration for stock_meta. eventradar doesn't ship its
    # own tushare token; it reuses calenderapp's config (which already has
    # a working internal-proxy token via TUSHARE_API_URL). The path below
    # is added to sys.path on demand so `from app.config import
    # get_tushare_pro` resolves to calenderapp's module. Empty value =
    # the tushare refresher is unavailable (refresh-stock-meta-tushare
    # exits with a clear error). Default points at the sibling app under
    # the same monorepo layout — adjust if calenderapp moves.
    calenderapp_backend_path: str = os.getenv(
        "EVENTRADAR_CALENDERAPP_BACKEND_PATH",
        str((ROOT_DIR.parent / "calenderapp" / "backend").resolve()),
    )
    # Path to calenderapp's .env so we pick up its TUSHARE_TOKEN /
    # TUSHARE_API_URL without copying secrets around. Skipped if missing.
    calenderapp_env_path: str = os.getenv(
        "EVENTRADAR_CALENDERAPP_ENV_PATH",
        str((ROOT_DIR.parent / "calenderapp" / "backend" / ".env").resolve()),
    )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.raw_cache_dir.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
