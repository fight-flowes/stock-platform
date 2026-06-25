import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]

PGSCHEMA = os.environ.get("PGSCHEMA", "sc")
STOCKKB_API_BASE_URL = os.environ.get("STOCKKB_API_BASE_URL", "http://127.0.0.1:8040").rstrip("/")
STOCKKB_API_TIMEOUT = int(os.environ.get("STOCKKB_API_TIMEOUT", "20"))
STOCKKB_DUCKDB_PATH = Path(
    os.environ.get(
        "STOCKKB_DUCKDB_PATH",
        str(PROJECT_ROOT / "apps" / "stockkb" / "data" / "stockkb.duckdb"),
    )
)
# Eventradar — forward-looking events from public data sources (akshare etc.).
# Empty by default because the eventradar service is still being built; in that
# case the /api/announcements/* proxy returns a friendly "not_configured"
# placeholder instead of erroring, so the frontend can render its mock view
# without requiring the upstream to be up. Set this to e.g.
# "http://127.0.0.1:8050" once eventradar is running.
EVENTRADAR_API_BASE_URL = os.environ.get("EVENTRADAR_API_BASE_URL", "").rstrip("/")
EVENTRADAR_API_TIMEOUT = int(os.environ.get("EVENTRADAR_API_TIMEOUT", "20"))
VIBE_TRADING_API_BASE_URL = os.environ.get("VIBE_TRADING_API_BASE_URL", "http://127.0.0.1:8899").rstrip("/")
VIBE_TRADING_API_TIMEOUT = int(os.environ.get("VIBE_TRADING_API_TIMEOUT", "120"))
VIBE_TRADING_API_KEY = os.environ.get("VIBE_TRADING_API_KEY", "").strip()

# Review session GC — daily cleanup of orphan / dead-reference Vibe-Trading
# sessions whose title looks like "Event Review *". Disabled by default in
# tests so that test runs do not spin up the daemon thread.
REVIEW_GC_ENABLED = os.environ.get("REVIEW_GC_ENABLED", "true").lower() == "true"
# Local time-of-day for the daily run; format "HH:MM". 03:37 by default —
# offset away from the :00 / :30 marks every other process picks.
REVIEW_GC_DAILY_AT = os.environ.get("REVIEW_GC_DAILY_AT", "03:37").strip()
# Delay before the first run after process startup, in seconds.
REVIEW_GC_STARTUP_DELAY_SECONDS = int(os.environ.get("REVIEW_GC_STARTUP_DELAY_SECONDS", "300"))
# Hard upper bound on how many sessions a single GC pass may delete. Anything
# above this is left for the next pass — protects against accidental mass-delete
# if an upstream change breaks reference tracking.
REVIEW_GC_MAX_DELETE_PER_RUN = int(os.environ.get("REVIEW_GC_MAX_DELETE_PER_RUN", "200"))

CALENDAR_V2_DUCKDB_PATH = Path(
    os.environ.get(
        "CALENDAR_V2_DUCKDB_PATH",
        str(BACKEND_DIR / "data" / "calendar_v2.duckdb"),
    )
)

# === API 认证（L2 后端 Token 校验）===
# 上公网前的安全基线：开启后所有 /api/* 请求必须带
# Authorization: Bearer <token>，token 须在 AUTH_TOKENS 白名单里。
#
# 默认关闭（AUTH_ENABLED=false），所以本地开发 / 现有部署完全不受影响 —
# 只有显式设置 AUTH_ENABLED=true（公网部署时）才会启用校验。
#
# AUTH_TOKENS 与前端 VITE_AUTH_TOKEN 同源、逗号分隔多个，二者需手动保持
# 同步。将来上用户体系（L3）后，这里会被替换成查用户表 / 校验 JWT。
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() == "true"
AUTH_TOKENS = [
    t.strip()
    for t in os.environ.get("AUTH_TOKENS", "").split(",")
    if t.strip()
]
