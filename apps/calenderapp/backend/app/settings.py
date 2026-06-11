import os

PGSCHEMA = os.environ.get("PGSCHEMA", "sc")
STOCKKB_API_BASE_URL = os.environ.get("STOCKKB_API_BASE_URL", "http://127.0.0.1:8040").rstrip("/")
STOCKKB_API_TIMEOUT = int(os.environ.get("STOCKKB_API_TIMEOUT", "20"))
