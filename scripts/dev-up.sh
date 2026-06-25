#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APPS_DIR="${PLATFORM_ROOT}/apps"
CALENDERAPP_DIR="${APPS_DIR}/calenderapp"
STOCKKB_DIR="${APPS_DIR}/stockkb"
EVENTRADAR_DIR="${APPS_DIR}/eventradar"

API_PORT="${API_PORT:-8040}"
EVENTRADAR_PORT="${EVENTRADAR_PORT:-8050}"
STOCKKB_LOG_DIR="${STOCKKB_DIR}/logs"
STOCKKB_RUN_DIR="${STOCKKB_DIR}/.run"
STOCKKB_API_BASE_URL="${STOCKKB_API_BASE_URL:-http://127.0.0.1:${API_PORT}}"
EVENTRADAR_API_BASE_URL="${EVENTRADAR_API_BASE_URL:-http://127.0.0.1:${EVENTRADAR_PORT}}"

port_open() {
  local port="$1"
  ss -tln 2>/dev/null | grep -q ":${port} "
}

pid_running() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" 2>/dev/null
}

wait_for_port() {
  local port="$1"
  local name="$2"
  for _ in $(seq 1 20); do
    if port_open "${port}"; then
      echo "[OK] ${name} 已就绪 (port ${port})"
      return 0
    fi
    sleep 1
  done
  echo "[ERROR] ${name} 未在预期时间内启动" >&2
  return 1
}

start_stockkb_api() {
  mkdir -p "${STOCKKB_LOG_DIR}" "${STOCKKB_RUN_DIR}"

  if port_open "${API_PORT}"; then
    if pid_running "${STOCKKB_RUN_DIR}/api.pid"; then
      echo "[OK] stockkb API 已由 stock-platform 副本运行 (port ${API_PORT})"
      return 0
    fi
    echo "[ERROR] port ${API_PORT} 已被外部 stockkb 进程占用，拒绝复用备份目录实例" >&2
    echo "[ERROR] 请先停止旧实例，或显式设置不同的 API_PORT / STOCKKB_API_BASE_URL" >&2
    return 1
  fi

  echo "[INFO] 启动 stockkb API"
  if command -v setsid >/dev/null 2>&1; then
    setsid bash "${STOCKKB_DIR}/scripts/start_api.sh" >"${STOCKKB_LOG_DIR}/api.log" 2>&1 < /dev/null &
  else
    nohup bash "${STOCKKB_DIR}/scripts/start_api.sh" >"${STOCKKB_LOG_DIR}/api.log" 2>&1 < /dev/null &
  fi
  echo $! > "${STOCKKB_RUN_DIR}/api.pid"
  wait_for_port "${API_PORT}" "stockkb API"
}

echo "== stock-platform dev-up =="
echo "[INFO] 平台根目录: ${PLATFORM_ROOT}"

if [[ ! -d "${CALENDERAPP_DIR}" || ! -d "${STOCKKB_DIR}" ]]; then
  echo "[ERROR] 缺少 apps/calenderapp 或 apps/stockkb 目录" >&2
  exit 1
fi

echo "[INFO] 启动 stockkb 核心链路（仅 API）"
start_stockkb_api

# eventradar 是 calenderapp 公告页的数据源，必须在 calenderapp 之前启动，
# 这样 calenderapp 后端启动时的 /api/announcements/health 探测就能拿到 healthy。
if [[ -d "${EVENTRADAR_DIR}" ]]; then
  echo "[INFO] 启动 eventradar"
  EVENTRADAR_MANAGE_COMPACT=1 bash "${EVENTRADAR_DIR}/manage.sh" start
else
  echo "[WARN] apps/eventradar 不存在，公告页将无数据"
fi

echo "[INFO] 启动 calenderapp"
STOCKKB_API_BASE_URL="${STOCKKB_API_BASE_URL}" \
CALENDERAPP_MANAGE_COMPACT=1 \
bash "${CALENDERAPP_DIR}/manage.sh" start

echo ""
echo "[OK] stock-platform 启动完成"
echo "[INFO] 前端:      http://127.0.0.1:3000"
echo "[INFO] 后端:      http://127.0.0.1:5000"
echo "[INFO] stockkb:   http://127.0.0.1:${API_PORT}"
echo "[INFO] eventradar: http://127.0.0.1:${EVENTRADAR_PORT}"
