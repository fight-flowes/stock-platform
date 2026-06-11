#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APPS_DIR="${PLATFORM_ROOT}/apps"
CALENDERAPP_DIR="${APPS_DIR}/calenderapp"
STOCKKB_DIR="${APPS_DIR}/stockkb"

required_paths=(
  "${CALENDERAPP_DIR}/manage.sh"
  "${CALENDERAPP_DIR}/backend/app/services/stockkb_proxy_service.py"
  "${STOCKKB_DIR}/scripts/start_api.sh"
  "${STOCKKB_DIR}/src/stockrag/api.py"
)

echo "== stock-platform dev-check =="
echo "[info] 平台根目录: ${PLATFORM_ROOT}"

for path in "${required_paths[@]}"; do
  if [[ -e "${path}" ]]; then
    echo "[ok] ${path}"
  else
    echo "[error] 缺少: ${path}" >&2
    exit 1
  fi
done

echo "[ok] 基础目录与关键入口文件检查通过"
