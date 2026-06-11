from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings, get_settings


def _env_first(names: tuple[str, ...], default: str) -> str:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            return raw
    return default


def _env_float(names: tuple[str, ...], default: float) -> float:
    raw = _env_first(names, "")
    if not raw:
        return default
    return float(raw)


@dataclass(slots=True)
class EventKBSettings:
    duckdb_path: Path
    llm_extract_enabled: bool
    llm_extract_base_url: str
    llm_extract_model: str
    llm_extract_api_key: str
    llm_extract_temperature: float
    llm_extract_timeout: int
    llm_extract_max_blocks: int
    llm_merge_enabled: bool
    llm_merge_base_url: str
    llm_merge_model: str
    llm_merge_api_key: str
    llm_merge_temperature: float
    llm_merge_timeout: int
    llm_merge_confidence_threshold: float
    llm_merge_max_judges: int
    llm_merge_prompt_version: str

    def ensure_dirs(self) -> None:
        self.duckdb_path.parent.mkdir(parents=True, exist_ok=True)


def get_event_kb_settings(settings: Settings | None = None) -> EventKBSettings:
    base_settings = settings or get_settings()
    legacy_duckdb_path = base_settings.data_dir / "stockrag_kb.duckdb"
    default_duckdb_path = legacy_duckdb_path if legacy_duckdb_path.exists() else base_settings.data_dir / "stockkb.duckdb"
    raw_path = _env_first(("STOCKKB_DUCKDB_PATH", "STOCKRAG_DUCKDB_PATH"), str(default_duckdb_path))
    llm_extract_base_url = _env_first(("STOCKKB_LLM_EXTRACT_BASE_URL", "STOCKRAG_LLM_EXTRACT_BASE_URL"), "").strip()
    llm_extract_model = _env_first(("STOCKKB_LLM_EXTRACT_MODEL", "STOCKRAG_LLM_EXTRACT_MODEL"), "").strip()
    llm_extract_api_key = _env_first(("STOCKKB_LLM_EXTRACT_API_KEY", "STOCKRAG_LLM_EXTRACT_API_KEY"), "").strip()
    llm_extract_timeout = int(_env_first(("STOCKKB_LLM_EXTRACT_TIMEOUT", "STOCKRAG_LLM_EXTRACT_TIMEOUT"), "60") or 60)
    event_settings = EventKBSettings(
        duckdb_path=Path(raw_path).expanduser().resolve(),
        llm_extract_enabled=_env_first(("STOCKKB_LLM_EXTRACT_ENABLED", "STOCKRAG_LLM_EXTRACT_ENABLED"), "false").lower() == "true",
        llm_extract_base_url=llm_extract_base_url,
        llm_extract_model=llm_extract_model,
        llm_extract_api_key=llm_extract_api_key,
        llm_extract_temperature=_env_float(("STOCKKB_LLM_EXTRACT_TEMPERATURE", "STOCKRAG_LLM_EXTRACT_TEMPERATURE"), 0.0),
        llm_extract_timeout=llm_extract_timeout,
        llm_extract_max_blocks=int(_env_first(("STOCKKB_LLM_EXTRACT_MAX_BLOCKS", "STOCKRAG_LLM_EXTRACT_MAX_BLOCKS"), "24") or 24),
        llm_merge_enabled=_env_first(("STOCKKB_LLM_MERGE_ENABLED", "STOCKRAG_LLM_MERGE_ENABLED"), "false").lower() == "true",
        llm_merge_base_url=_env_first(("STOCKKB_LLM_MERGE_BASE_URL", "STOCKRAG_LLM_MERGE_BASE_URL"), llm_extract_base_url).strip(),
        llm_merge_model=_env_first(("STOCKKB_LLM_MERGE_MODEL", "STOCKRAG_LLM_MERGE_MODEL"), llm_extract_model).strip(),
        llm_merge_api_key=_env_first(("STOCKKB_LLM_MERGE_API_KEY", "STOCKRAG_LLM_MERGE_API_KEY"), llm_extract_api_key).strip(),
        llm_merge_temperature=_env_float(("STOCKKB_LLM_MERGE_TEMPERATURE", "STOCKRAG_LLM_MERGE_TEMPERATURE"), 0.0),
        llm_merge_timeout=int(_env_first(("STOCKKB_LLM_MERGE_TIMEOUT", "STOCKRAG_LLM_MERGE_TIMEOUT"), str(llm_extract_timeout)) or llm_extract_timeout),
        llm_merge_confidence_threshold=_env_float(("STOCKKB_LLM_MERGE_CONFIDENCE_THRESHOLD", "STOCKRAG_LLM_MERGE_CONFIDENCE_THRESHOLD"), 0.8),
        llm_merge_max_judges=int(_env_first(("STOCKKB_LLM_MERGE_MAX_JUDGES", "STOCKRAG_LLM_MERGE_MAX_JUDGES"), "60") or 60),
        llm_merge_prompt_version=_env_first(("STOCKKB_LLM_MERGE_PROMPT_VERSION", "STOCKRAG_LLM_MERGE_PROMPT_VERSION"), "v1").strip() or "v1",
    )
    event_settings.ensure_dirs()
    return event_settings
