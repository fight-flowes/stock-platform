#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APPS_DIR="${PLATFORM_ROOT}/apps"
CALENDERAPP_DIR="${APPS_DIR}/calenderapp"
STOCKKB_DIR="${APPS_DIR}/stockkb"
EVENTRADAR_DIR="${APPS_DIR}/eventradar"

echo "== stock-platform dev-down =="

if [[ -d "${CALENDERAPP_DIR}" ]]; then
  echo "[INFO] 停止 calenderapp"
  CALENDERAPP_MANAGE_COMPACT=1 bash "${CALENDERAPP_DIR}/manage.sh" stop || true
fi

if [[ -d "${EVENTRADAR_DIR}" ]]; then
  echo ""
  echo "[INFO] 停止 eventradar"
  EVENTRADAR_MANAGE_COMPACT=1 bash "${EVENTRADAR_DIR}/manage.sh" stop || true
fi

if [[ -d "${STOCKKB_DIR}" ]]; then
  echo ""
  echo "[INFO] 停止 stockkb"
  STOCKKB_MANAGE_COMPACT=1 bash "${STOCKKB_DIR}/scripts/manage.sh" stop || true
fi

echo ""
echo "[OK] stock-platform 停止完成"
