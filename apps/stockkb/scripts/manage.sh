#!/usr/bin/env bash
# ============================================================================
# stockkb 服务管理脚本
# 使用方式: ./scripts/manage.sh [start|stop|restart|status|logs|help]
# 默认 conda 环境:
#   - API: stock
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
RUN_DIR="${PROJECT_ROOT}/.run"

API_SCRIPT="${SCRIPT_DIR}/start_api.sh"

API_PORT="${API_PORT:-8040}"
MINIO_PORT="${MINIO_PORT:-9010}"

mkdir -p "${LOG_DIR}" "${RUN_DIR}"

compact_mode() {
    [[ "${STOCKKB_MANAGE_COMPACT:-0}" == "1" ]]
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

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

find_listening_pids() {
    local port="$1"
    lsof -ti :"${port}" 2>/dev/null | sort -u
}

kill_port_processes() {
    local port="$1"
    local name="$2"
    local signal="${3:-TERM}"
    local pids
    pids="$(find_listening_pids "${port}" || true)"

    [[ -n "${pids}" ]] || return 1

    log_warn "端口 ${port} 被占用，回收 ${name} 监听进程"
    while read -r pid; do
        [[ -n "${pid}" ]] || continue
        kill "-${signal}" "${pid}" 2>/dev/null || true
    done <<< "${pids}"
    return 0
}

force_release_port() {
    local port="$1"
    local name="$2"

    if ! port_open "${port}"; then
        return 0
    fi

    kill_port_processes "${port}" "${name}" "TERM" || return 1
    sleep 1

    if port_open "${port}"; then
        kill_port_processes "${port}" "${name}" "KILL" || true
        sleep 1
    fi

    if port_open "${port}"; then
        log_error "端口 ${port} 仍被占用，无法回收 ${name} 监听进程"
        return 1
    fi

    log_success "端口 ${port} 已回收"
    return 0
}

remove_pid_file() {
    local pid_file="$1"
    if [[ -f "${pid_file}" ]]; then
        rm -f "${pid_file}"
    fi
    return 0
}

check_minio() {
    if port_open "${MINIO_PORT}"; then
        log_success "MinIO 已运行 (port ${MINIO_PORT})"
    else
        log_warn "MinIO 未启动，请确认对象存储服务可用"
    fi
}

start_background_service() {
    local name="$1"
    local port="$2"
    local script="$3"
    local pid_file="$4"
    local log_file="$5"

    if port_open "${port}"; then
        if pid_running "${pid_file}"; then
            log_success "${name} 已由当前工作区运行 (port ${port})"
            return 0
        fi
        force_release_port "${port}" "${name}" || return 1
    fi

    if pid_running "${pid_file}"; then
        log_info "检测到 ${name} pid，等待端口就绪"
    else
        log_info "启动 ${name}"
        if command -v setsid >/dev/null 2>&1; then
            setsid bash "${script}" >"${log_file}" 2>&1 < /dev/null &
        else
            nohup bash "${script}" >"${log_file}" 2>&1 < /dev/null &
        fi
        echo $! > "${pid_file}"
    fi

    for _ in $(seq 1 20); do
        if port_open "${port}"; then
            log_success "${name} 启动成功"
            return 0
        fi
        sleep 1
    done

    log_error "${name} 启动失败，请查看日志: ${log_file}"
    return 1
}

stop_background_service() {
    local name="$1"
    local pid_file="$2"
    local port="$3"

    if pid_running "${pid_file}"; then
        local pid
        pid="$(cat "${pid_file}")"
        log_info "停止 ${name} (pid ${pid})"
        kill "${pid}" 2>/dev/null || true
        sleep 1
        if kill -0 "${pid}" 2>/dev/null; then
            kill -9 "${pid}" 2>/dev/null || true
        fi
        remove_pid_file "${pid_file}"
    else
        log_info "${name} 没有活动 pid 记录"
        remove_pid_file "${pid_file}"
    fi

    if port_open "${port}"; then
        force_release_port "${port}" "${name}" || true
    fi

    if port_open "${port}"; then
        log_warn "${name} 端口 ${port} 仍在监听"
    else
        log_success "${name} 已停止"
    fi
}

status_line() {
    local name="$1"
    local port="$2"
    local pid_file="${3:-}"
    if port_open "${port}"; then
        if [[ -n "${pid_file}" && -f "${pid_file}" ]] && pid_running "${pid_file}"; then
            echo -e "${GREEN}[RUNNING]${NC} ${name} (port ${port})"
        elif [[ -n "${pid_file}" ]]; then
            echo -e "${YELLOW}[EXTERNAL]${NC} ${name} (port ${port})"
        else
            echo -e "${GREEN}[RUNNING]${NC} ${name} (port ${port})"
        fi
    else
        echo -e "${RED}[STOPPED]${NC} ${name} (port ${port})"
    fi
}

show_status() {
    if compact_mode; then
        echo "[stockkb]"
    else
        echo ""
        echo "============================================"
        echo "  stockkb 服务状态"
        echo "============================================"
        echo ""
    fi
    status_line "MinIO" "${MINIO_PORT}"
    status_line "stockkb API" "${API_PORT}" "${RUN_DIR}/api.pid"
    if compact_mode; then
        echo "日志: ${LOG_DIR}"
    else
        echo ""
        echo "日志目录: ${LOG_DIR}"
    fi
}

start_all() {
    if compact_mode; then
        echo "[stockkb] 启动"
    else
        echo ""
        echo "============================================"
        echo "  stockkb 启动"
        echo "============================================"
        echo ""
    fi
    log_info "项目目录: ${PROJECT_ROOT}"
    log_info "API 环境: stock"
    log_info "MinIO 默认 bucket: stockinfo"
    if ! compact_mode; then
        echo ""
    fi

    check_minio
    start_background_service \
        "stockkb API" \
        "${API_PORT}" \
        "${API_SCRIPT}" \
        "${RUN_DIR}/api.pid" \
        "${LOG_DIR}/api.log"

    log_success "stockkb 启动流程完成"
    if compact_mode; then
        echo "API: http://127.0.0.1:${API_PORT}/docs"
    else
        echo ""
        echo "API 文档: http://127.0.0.1:${API_PORT}/docs"
    fi
}

stop_all() {
    if compact_mode; then
        echo "[stockkb] 停止"
    else
        echo ""
        echo "============================================"
        echo "  stockkb 停止"
        echo "============================================"
        echo ""
    fi
    stop_background_service "stockkb API" "${RUN_DIR}/api.pid" "${API_PORT}"
    if ! compact_mode; then
        echo ""
    fi
    log_info "MinIO 默认不主动停止，避免影响其他项目"
}

show_logs() {
    if compact_mode; then
        echo "[stockkb] 日志"
        echo "API: ${LOG_DIR}/api.log"
    else
        echo ""
        echo "API log:"
        echo "  ${LOG_DIR}/api.log"
        echo ""
    fi
}

show_help() {
    cat <<EOF
stockkb 服务管理脚本

用法:
  bash scripts/manage.sh start
  bash scripts/manage.sh stop
  bash scripts/manage.sh restart
  bash scripts/manage.sh status
  bash scripts/manage.sh logs
  bash scripts/manage.sh help

说明:
  - start: 启动 stockkb API，并检查 MinIO 状态
  - stop: 停止 stockkb API
  - restart: 重启 stockkb API，并检查 MinIO
  - status: 查看服务端口状态
  - logs: 显示日志文件位置

默认端口:
  API_PORT=${API_PORT}
  MINIO_PORT=${MINIO_PORT}
EOF
}

command="${1:-help}"
case "${command}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        start_all
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    help|-h|--help)
        show_help
        ;;
    *)
        log_error "未知命令: ${command}"
        echo ""
        show_help
        exit 1
        ;;
esac
