#!/usr/bin/env bash
# ============================================================================
# eventradar 服务管理脚本
# 使用方式: ./manage.sh [start|stop|restart|status|logs|serve|<cli-subcommand>]
#
# - start/stop/restart/status/logs: 管理 FastAPI 服务（后台运行）
# - serve: 前台运行服务（调试用）
# - 其它子命令（pull/enrich/show-config 等）直接转发给 eventradar CLI
#
# 设计目标：和 stockkb/scripts/manage.sh 风格一致，方便 scripts/dev-up.sh
# 统一编排。PID 文件 + 端口探测 + setsid/nohup 后台化，关终端不退出。
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"
LOG_DIR="${PROJECT_ROOT}/logs"
RUN_DIR="${PROJECT_ROOT}/.run"

# 服务端口（默认 8050，和 calenderapp .env 里的 EVENTRADAR_API_BASE_URL 对应）
EVENTRADAR_PORT="${EVENTRADAR_PORT:-8050}"
EVENTRADAR_HOST="${EVENTRADAR_HOST:-0.0.0.0}"
CONDA_ENV="${CONDA_ENV:-stock}"
CONDA_BASE="${CONDA_BASE:-$HOME/miniconda3}"
CONDA_PYTHON="${CONDA_PYTHON:-$CONDA_BASE/envs/$CONDA_ENV/bin/python}"

API_PID_FILE="${RUN_DIR}/api.pid"
API_LOG_FILE="${LOG_DIR}/serve.log"

mkdir -p "${LOG_DIR}" "${RUN_DIR}"

# 紧凑模式：被 dev-up.sh / dev-status.sh 调用时减少装饰性输出
compact_mode() {
    [[ "${EVENTRADAR_MANAGE_COMPACT:-0}" == "1" ]]
}

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================================
# 环境激活
# ============================================================================
activate_conda() {
    if [[ "${CONDA_DEFAULT_ENV:-}" != "$CONDA_ENV" ]]; then
        # shellcheck disable=SC1091
        source "${CONDA_BASE}/etc/profile.d/conda.sh"
        conda activate "$CONDA_ENV"
    fi
    export PYTHONPATH="${PROJECT_ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
}

# ============================================================================
# 端口 / PID 工具（与 stockkb manage.sh 同构）
# ============================================================================
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

force_release_port() {
    local port="$1"
    local name="$2"
    if ! port_open "${port}"; then
        return 0
    fi
    local pids
    pids="$(find_listening_pids "${port}" || true)"
    [[ -n "${pids}" ]] || return 1
    log_warn "端口 ${port} 被占用，回收 ${name} 监听进程"
    while read -r pid; do
        [[ -n "${pid}" ]] || continue
        kill -TERM "${pid}" 2>/dev/null || true
    done <<< "${pids}"
    sleep 1
    if port_open "${port}"; then
        while read -r pid; do
            [[ -n "${pid}" ]] || continue
            kill -KILL "${pid}" 2>/dev/null || true
        done <<< "${pids}"
        sleep 1
    fi
    if port_open "${port}"; then
        log_error "端口 ${port} 仍被占用，无法回收"
        return 1
    fi
    log_success "端口 ${port} 已回收"
}

# ============================================================================
# start / stop / status
# ============================================================================
start_api() {
    if port_open "${EVENTRADAR_PORT}"; then
        if pid_running "${API_PID_FILE}"; then
            log_success "eventradar API 已运行 (port ${EVENTRADAR_PORT})"
            return 0
        fi
        force_release_port "${EVENTRADAR_PORT}" "eventradar API" || return 1
    fi

    log_info "启动 eventradar API (port ${EVENTRADAR_PORT})"
    activate_conda
    # setsid 让进程脱离当前会话，关终端不退出；nohup 作为 fallback
    if command -v setsid >/dev/null 2>&1; then
        setsid python -m eventradar serve --host "${EVENTRADAR_HOST}" --port "${EVENTRADAR_PORT}" \
            >"${API_LOG_FILE}" 2>&1 < /dev/null &
    else
        nohup python -m eventradar serve --host "${EVENTRADAR_HOST}" --port "${EVENTRADAR_PORT}" \
            >"${API_LOG_FILE}" 2>&1 < /dev/null &
    fi
    echo $! > "${API_PID_FILE}"

    # 等端口就绪（最多 20s）
    for _ in $(seq 1 20); do
        if port_open "${EVENTRADAR_PORT}"; then
            log_success "eventradar API 启动成功"
            return 0
        fi
        sleep 1
    done
    log_error "eventradar API 启动失败，查看日志: ${API_LOG_FILE}"
    return 1
}

stop_api() {
    if pid_running "${API_PID_FILE}"; then
        local pid
        pid="$(cat "${API_PID_FILE}")"
        log_info "停止 eventradar API (pid ${pid})"
        kill "${pid}" 2>/dev/null || true
        sleep 1
        if kill -0 "${pid}" 2>/dev/null; then
            kill -9 "${pid}" 2>/dev/null || true
        fi
        rm -f "${API_PID_FILE}"
    else
        log_info "eventradar API 无活动 pid 记录"
        rm -f "${API_PID_FILE}"
    fi

    if port_open "${EVENTRADAR_PORT}"; then
        force_release_port "${EVENTRADAR_PORT}" "eventradar API" || true
    fi

    if port_open "${EVENTRADAR_PORT}"; then
        log_warn "eventradar API 端口 ${EVENTRADAR_PORT} 仍在监听"
    else
        log_success "eventradar API 已停止"
    fi
}

show_status() {
    if compact_mode; then
        echo "[eventradar]"
    else
        echo ""
        echo "============================================"
        echo "  eventradar 服务状态"
        echo "============================================"
    fi
    if port_open "${EVENTRADAR_PORT}"; then
        if pid_running "${API_PID_FILE}"; then
            echo -e "${GREEN}[RUNNING]${NC} eventradar API (port ${EVENTRADAR_PORT})"
        else
            echo -e "${YELLOW}[EXTERNAL]${NC} eventradar API (port ${EVENTRADAR_PORT})"
        fi
    else
        echo -e "${RED}[STOPPED]${NC} eventradar API (port ${EVENTRADAR_PORT})"
    fi
    if ! compact_mode; then
        echo "  日志: ${API_LOG_FILE}"
        echo "  PID:  ${API_PID_FILE}"
    fi
}

show_logs() {
    log_info "跟踪日志 ${API_LOG_FILE}（Ctrl+C 退出）"
    tail -f "${API_LOG_FILE}"
}

# ============================================================================
# 入口
# ============================================================================
case "${1:-help}" in
    start)
        start_api
        ;;
    stop)
        stop_api
        ;;
    restart)
        stop_api
        start_api
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    serve)
        # 前台运行，用于调试
        activate_conda
        exec python -m eventradar serve --host "${EVENTRADAR_HOST}" --port "${EVENTRADAR_PORT}"
        ;;
    help|--help|-h)
        echo "eventradar 服务管理"
        echo "用法: ./manage.sh [start|stop|restart|status|logs|serve|<cli子命令>]"
        echo ""
        echo "服务管理:"
        echo "  start    后台启动 API 服务"
        echo "  stop     停止 API 服务"
        echo "  restart  重启"
        echo "  status   查看状态"
        echo "  logs     跟踪日志"
        echo "  serve    前台运行（调试用）"
        echo ""
        echo "CLI 转发（直接传给 eventradar CLI）:"
        echo "  pull <adapter> [args]      拉数据"
        echo "  enrich [--all]             富化"
        echo "  refresh-stock-meta-tushare 刷新股票元数据"
        echo "  show-config                显示配置"
        echo "  list-adapters              列出已注册 adapter"
        ;;
    *)
        # 未识别的子命令 → 转发给 eventradar CLI
        # （pull / enrich / refresh-stock-meta-tushare / show-config 等）
        activate_conda
        exec python -m eventradar "$@"
        ;;
esac
