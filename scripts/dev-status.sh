#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APPS_DIR="${PLATFORM_ROOT}/apps"
CALENDERAPP_DIR="${APPS_DIR}/calenderapp"
STOCKKB_DIR="${APPS_DIR}/stockkb"

echo "== stock-platform dev-status =="
echo "[INFO] 平台根目录: ${PLATFORM_ROOT}"

if [[ -d "${CALENDERAPP_DIR}" ]]; then
  echo ""
  CALENDERAPP_MANAGE_COMPACT=1 bash "${CALENDERAPP_DIR}/manage.sh" status || true
fi

if [[ -d "${STOCKKB_DIR}" ]]; then
  echo ""
  STOCKKB_MANAGE_COMPACT=1 bash "${STOCKKB_DIR}/scripts/manage.sh" status || true
fi
