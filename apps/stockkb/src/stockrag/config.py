from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=False)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw is not None and raw.strip() else default


def _env_paths(name: str) -> tuple[Path, ...]:
    raw = os.getenv(name, "")
    parts = [item.strip() for item in raw.split(os.pathsep) if item.strip()]
    return tuple(Path(item).expanduser().resolve() for item in parts)


def _env_first(names: tuple[str, ...], default: str) -> str:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            return raw
    return default


@dataclass(slots=True)
class Settings:
    root_dir: Path = ROOT_DIR
    data_dir: Path = Path(
        _env_first(("STOCKKB_DATA_DIR", "STOCKRAG_DATA_DIR"), str(ROOT_DIR / "data"))
    )

    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9010")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    minio_default_bucket: str = os.getenv("MINIO_DEFAULT_BUCKET", "stockinfo")
    api_enable_local_ingest: bool = os.getenv("API_ENABLE_LOCAL_INGEST", "false").lower() == "true"
    local_ingest_allowed_roots: tuple[Path, ...] = _env_paths("LOCAL_INGEST_ALLOWED_ROOTS")

    chunk_max_chars: int = _env_int("CHUNK_MAX_CHARS", 1400)
    chunk_min_chars: int = _env_int("CHUNK_MIN_CHARS", 350)
    chunk_soft_target: int = _env_int("CHUNK_SOFT_TARGET", 900)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
