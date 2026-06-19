import os

PGSCHEMA = os.environ.get("PGSCHEMA", "sc")
STOCKKB_API_BASE_URL = os.environ.get("STOCKKB_API_BASE_URL", "http://127.0.0.1:8040").rstrip("/")
STOCKKB_API_TIMEOUT = int(os.environ.get("STOCKKB_API_TIMEOUT", "20"))
# Eventradar — forward-looking events from public data sources (akshare etc.).
# Empty by default because the eventradar service is still being built; in that
# case the /api/announcements/* proxy returns a friendly "not_configured"
# placeholder instead of erroring, so the frontend can render its mock view
# without requiring the upstream to be up. Set this to e.g.
# "http://127.0.0.1:8050" once eventradar is running.
EVENTRADAR_API_BASE_URL = os.environ.get("EVENTRADAR_API_BASE_URL", "").rstrip("/")
EVENTRADAR_API_TIMEOUT = int(os.environ.get("EVENTRADAR_API_TIMEOUT", "20"))
