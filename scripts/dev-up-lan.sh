#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PUBLIC_WEB_HOST="${PUBLIC_WEB_HOST:-10.168.4.11}"
PUBLIC_FRONTEND_PORT="${PUBLIC_FRONTEND_PORT:-13000}"
PUBLIC_BACKEND_PORT="${PUBLIC_BACKEND_PORT:-15000}"
PUBLIC_STOCKKB_PORT="${PUBLIC_STOCKKB_PORT:-18040}"

echo "== stock-platform dev-up-lan =="
echo "[INFO] 平台根目录: ${PLATFORM_ROOT}"
echo "[INFO] 局域网主机: ${PUBLIC_WEB_HOST}"

cd "${PLATFORM_ROOT}"

PUBLIC_WEB_HOST="${PUBLIC_WEB_HOST}" \
VITE_API_BASE_URL="http://${PUBLIC_WEB_HOST}:${PUBLIC_BACKEND_PORT}" \
bash "${SCRIPT_DIR}/dev-up.sh"

echo ""
echo "[INFO] 局域网前端:   http://${PUBLIC_WEB_HOST}:${PUBLIC_FRONTEND_PORT}"
echo "[INFO] 局域网后端:   http://${PUBLIC_WEB_HOST}:${PUBLIC_BACKEND_PORT}"
echo "[INFO] 局域网 stockkb: http://${PUBLIC_WEB_HOST}:${PUBLIC_STOCKKB_PORT}"
