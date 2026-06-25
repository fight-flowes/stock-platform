#!/bin/bash
# ============================================================================
# 股票日历事件管理系统启动脚本
# 使用方式: ./manage.sh [start|stop|restart|status|backend-only|frontend-only]
# ============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$SCRIPT_DIR}"
BACKEND_DIR="${BACKEND_DIR:-$PROJECT_DIR/backend}"
FRONTEND_DIR="${FRONTEND_DIR:-$PROJECT_DIR/frontend}"

# Conda 环境
CONDA_BASE="${CONDA_BASE:-$HOME/miniconda3}"
CONDA_ENV="${CONDA_ENV:-stock}"
CONDA_PYTHON="${CONDA_PYTHON:-$CONDA_BASE/envs/$CONDA_ENV/bin/python}"

# PostgreSQL Docker 容器
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-postgres-calendar}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-$POSTGRES_PORT}"
PGUSER="${PGUSER:-postgres}"
PGPASSWORD="${PGPASSWORD:-postgres123}"
PGDATABASE="${PGDATABASE:-calenderdb}"

# 服务端口
BACKEND_PORT="${BACKEND_PORT:-5000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
PUBLIC_WEB_HOST="${PUBLIC_WEB_HOST:-10.168.4.11}"
VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://127.0.0.1:${BACKEND_PORT}}"

# ============================================================================
# 辅助函数
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

compact_mode() {
    [[ "${CALENDERAPP_MANAGE_COMPACT:-0}" == "1" ]]
}

print_compact_header() {
    local label="${1:-calenderapp}"
    local action="${2:-}"
    if [ -n "$action" ]; then
        echo "[${label}] ${action}"
    else
        echo "[${label}]"
    fi
}

check_port() {
    local port=$1
    if lsof -i :$port >/dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口空闲
    fi
}

pid_running() {
    local pid_file=$1
    if [ ! -f "$pid_file" ]; then
        return 1
    fi
    local pid
    pid=$(cat "$pid_file" 2>/dev/null || true)
    if [ -z "$pid" ]; then
        return 1
    fi
    kill -0 "$pid" 2>/dev/null
}

find_listening_pids() {
    local port=$1
    lsof -ti :"$port" 2>/dev/null | sort -u
}

kill_port_processes() {
    local port=$1
    local label=$2
    local signal="${3:-TERM}"
    local pids
    pids="$(find_listening_pids "$port" || true)"

    if [ -z "$pids" ]; then
        return 1
    fi

    log_warning "端口 $port 被占用，回收 ${label} 监听进程"
    while read -r pid; do
        [ -n "$pid" ] || continue
        kill "-$signal" "$pid" 2>/dev/null || true
    done <<< "$pids"
    return 0
}

force_release_port() {
    local port=$1
    local label=$2

    if ! check_port "$port"; then
        return 0
    fi

    kill_port_processes "$port" "$label" "TERM" || return 1
    sleep 1

    if check_port "$port"; then
        kill_port_processes "$port" "$label" "KILL" || true
        sleep 1
    fi

    if check_port "$port"; then
        log_error "端口 $port 仍被占用，无法回收 ${label} 监听进程"
        return 1
    fi

    log_success "端口 $port 已回收"
    return 0
}

docker_cli_available() {
    command -v docker >/dev/null 2>&1
}

docker_accessible() {
    docker_cli_available && docker info >/dev/null 2>&1
}

wait_for_port() {
    local port=$1
    local service=$2
    local max_wait=30
    local count=0
    
    while ! check_port $port; do
        if [ $count -ge $max_wait ]; then
            log_error "$service 启动超时"
            return 1
        fi
        sleep 1
        count=$((count + 1))
    done
    return 0
}

# ============================================================================
# PostgreSQL 检查/启动
# ============================================================================

start_postgres() {
    log_info "检查 PostgreSQL Docker 容器..."

    if ! docker_cli_available; then
        log_warning "未找到 docker，跳过 PostgreSQL 容器管理；请确认数据库已可用"
        return 0
    fi

    if ! docker_accessible; then
        log_warning "当前用户无 Docker 权限，跳过 PostgreSQL 容器管理；请确认数据库已可用"
        return 0
    fi
    
    # 检查容器是否存在
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        log_warning "容器 $POSTGRES_CONTAINER 不存在"
        log_info "请手动创建 PostgreSQL 容器:"
        echo "  docker run -d --name $POSTGRES_CONTAINER -p $POSTGRES_PORT:$POSTGRES_PORT -e POSTGRES_PASSWORD=postgres123 postgres:15"
        return 1
    fi
    
    # 检查容器是否运行
    if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        log_success "PostgreSQL 容器已运行"
    else
        log_info "启动 PostgreSQL 容器..."
        docker start $POSTGRES_CONTAINER
        sleep 3
        
        if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
            log_success "PostgreSQL 容器启动成功"
        else
            log_error "PostgreSQL 容器启动失败"
            return 1
        fi
    fi
    
    # 验证数据库连接
    log_info "验证数据库连接..."
    if docker exec $POSTGRES_CONTAINER pg_isready -U postgres >/dev/null 2>&1; then
        log_success "数据库连接正常"
    else
        log_error "数据库连接失败"
        return 1
    fi
    
    return 0
}

# ============================================================================
# 后端启动
# ============================================================================

start_backend() {
    log_info "检查后端服务..."
    local pid_file="$BACKEND_DIR/backend.pid"
    
    # 检查端口是否被占用
    if check_port $BACKEND_PORT; then
        log_warning "端口 $BACKEND_PORT 已被占用"
        
        # 检查是否是我们的服务
        if pid_running "$pid_file" && curl -s http://127.0.0.1:$BACKEND_PORT/health >/dev/null 2>&1; then
            log_success "后端服务已在运行"
            return 0
        else
            force_release_port "$BACKEND_PORT" "后端服务" || return 1
        fi
    fi
    
    # 检查 Conda 环境
    if [ ! -f "$CONDA_PYTHON" ]; then
        log_error "Conda 环境 $CONDA_ENV 不存在: $CONDA_PYTHON"
        return 1
    fi
    
    log_info "启动后端服务..."
    cd $BACKEND_DIR
    
    # 使用 nohup 后台启动
    nohup env \
        PGHOST="$PGHOST" \
        PGPORT="$PGPORT" \
        PGUSER="$PGUSER" \
        PGPASSWORD="$PGPASSWORD" \
        PGDATABASE="$PGDATABASE" \
        $CONDA_PYTHON main.py > backend.log 2>&1 &
    BACKEND_PID=$!
    
    # 等待启动
    sleep 5
    
    if check_port $BACKEND_PORT; then
        log_success "后端服务启动成功 (PID: $BACKEND_PID)"
        log_success "后端地址: http://127.0.0.1:$BACKEND_PORT"
        log_success "API 文档: http://127.0.0.1:$BACKEND_PORT/api/docs/"
        echo $BACKEND_PID > "$pid_file"
        return 0
    else
        log_error "后端服务启动失败"
        cat backend.log | tail -20
        return 1
    fi
}

# ============================================================================
# 前端启动
# ============================================================================

start_frontend() {
    log_info "检查前端服务..."
    local pid_file="$FRONTEND_DIR/frontend.pid"
    
    # 检查端口是否被占用
    if check_port $FRONTEND_PORT; then
        log_warning "端口 $FRONTEND_PORT 已被占用"
        
        # 检查是否是 vite 服务
        if pid_running "$pid_file" && curl -s http://127.0.0.1:$FRONTEND_PORT >/dev/null 2>&1; then
            log_success "前端服务已在运行"
            return 0
        else
            force_release_port "$FRONTEND_PORT" "前端服务" || return 1
        fi
    fi
    
    # 检查 node_modules
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        log_warning "node_modules 不存在，正在安装..."
        cd $FRONTEND_DIR
        npm install
    fi
    
    log_info "启动前端服务..."
    cd $FRONTEND_DIR
    
    # 使用 nohup 后台启动
    nohup env \
        VITE_API_BASE_URL="$VITE_API_BASE_URL" \
        npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" > frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    # 等待启动
    sleep 8
    
    if check_port $FRONTEND_PORT; then
        log_success "前端服务启动成功 (PID: $FRONTEND_PID)"
        log_success "前端地址: http://127.0.0.1:$FRONTEND_PORT"
        log_success "前端监听: http://$FRONTEND_HOST:$FRONTEND_PORT"
        log_success "前端 API: $VITE_API_BASE_URL"
        echo $FRONTEND_PID > "$pid_file"
        return 0
    else
        log_error "前端服务启动失败"
        cat frontend.log | tail -20
        return 1
    fi
}

# ============================================================================
# 停止服务
# ============================================================================

stop_all() {
    if compact_mode; then
        print_compact_header "calenderapp" "停止"
    fi

    log_info "停止所有服务..."
    
    # 停止后端
    if [ -f "$BACKEND_DIR/backend.pid" ]; then
        BACKEND_PID=$(cat $BACKEND_DIR/backend.pid)
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill $BACKEND_PID
            log_success "后端服务已停止"
        fi
        rm -f $BACKEND_DIR/backend.pid
    fi
    
    # 停止前端
    if [ -f "$FRONTEND_DIR/frontend.pid" ]; then
        FRONTEND_PID=$(cat $FRONTEND_DIR/frontend.pid)
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill $FRONTEND_PID
            log_success "前端服务已停止"
        fi
        rm -f $FRONTEND_DIR/frontend.pid
    fi
    
    if check_port $BACKEND_PORT; then
        force_release_port "$BACKEND_PORT" "后端服务" || true
    fi

    if check_port $FRONTEND_PORT; then
        force_release_port "$FRONTEND_PORT" "前端服务" || true
    fi
    
    log_success "所有服务已停止"
}

# ============================================================================
# 状态检查
# ============================================================================

check_status() {
    if compact_mode; then
        print_compact_header "calenderapp" "状态"
        echo ""
    else
        echo ""
        echo "============================================"
        echo "  A股投研数据平台 - 服务状态"
        echo "============================================"
        echo ""
    fi
    
    # PostgreSQL
    echo -e "${BLUE}[PostgreSQL]${NC}"
    if ! docker_cli_available; then
        echo -e "  状态: ${YELLOW}未安装 Docker，跳过容器检查${NC}"
    elif ! docker_accessible; then
        echo -e "  状态: ${YELLOW}无 Docker 权限，跳过容器检查${NC}"
    elif docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        echo -e "  状态: ${GREEN}运行中${NC}"
        echo "  容器: $POSTGRES_CONTAINER"
        docker exec $POSTGRES_CONTAINER psql -U postgres -d calenderdb -c "SELECT 1" >/dev/null 2>&1 && \
            echo -e "  数据库: ${GREEN}连接正常${NC}" || \
            echo -e "  数据库: ${RED}连接失败${NC}"
    else
        echo -e "  状态: ${RED}未运行${NC}"
    fi
    echo ""
    
    # 后端
    echo -e "${BLUE}[后端服务]${NC}"
    if check_port $BACKEND_PORT && curl -s http://127.0.0.1:$BACKEND_PORT/health >/dev/null 2>&1; then
        echo -e "  状态: ${GREEN}运行中${NC}"
        echo "  地址: http://127.0.0.1:$BACKEND_PORT"
        echo "  文档: http://127.0.0.1:$BACKEND_PORT/api/docs/"
        
        # 显示 PID
        if pid_running "$BACKEND_DIR/backend.pid"; then
            echo "  PID: $(cat $BACKEND_DIR/backend.pid)"
        else
            echo -e "  归属: ${YELLOW}外部进程（非当前工作区 PID）${NC}"
        fi
    else
        echo -e "  状态: ${RED}未运行${NC}"
    fi
    echo ""
    
    # 前端
    echo -e "${BLUE}[前端服务]${NC}"
    if check_port $FRONTEND_PORT && curl -s http://127.0.0.1:$FRONTEND_PORT >/dev/null 2>&1; then
        echo -e "  状态: ${GREEN}运行中${NC}"
        echo "  地址: http://127.0.0.1:$FRONTEND_PORT"
        
        # 显示 PID
        if pid_running "$FRONTEND_DIR/frontend.pid"; then
            echo "  PID: $(cat $FRONTEND_DIR/frontend.pid)"
        else
            echo -e "  归属: ${YELLOW}外部进程（非当前工作区 PID）${NC}"
        fi
    else
        echo -e "  状态: ${RED}未运行${NC}"
    fi
    echo ""
    
    if ! compact_mode; then
        echo "============================================"
    fi
}

# ============================================================================
# 主函数
# ============================================================================

main() {
    case "${1:-start}" in
        start)
            if compact_mode; then
                print_compact_header "calenderapp" "启动"
            else
                echo ""
                echo "============================================"
                echo "  A股投研数据平台 - 启动"
                echo "============================================"
                echo ""
            fi
            
            start_postgres || exit 1
            start_backend || exit 1
            start_frontend || exit 1
            
            log_success "A股投研数据平台启动完成！"
            if compact_mode; then
                echo "[INFO] 前端: http://127.0.0.1:${FRONTEND_PORT}"
                echo "[INFO] 后端: http://127.0.0.1:${BACKEND_PORT}"
                echo "[INFO] 文档: http://127.0.0.1:${BACKEND_PORT}/api/docs/"
            else
                echo ""
                echo "============================================"
                echo ""
                echo "访问地址:"
                echo "  前端:  http://127.0.0.1:3000"
                echo "  后端:  http://127.0.0.1:5000"
                echo "  文档:  http://127.0.0.1:5000/api/docs/"
                echo ""
            fi
            ;;
        
        backend-only)
            if compact_mode; then
                print_compact_header "calenderapp" "启动后端"
            fi
            start_postgres || exit 1
            start_backend || exit 1
            ;;
        
        frontend-only)
            if compact_mode; then
                print_compact_header "calenderapp" "启动前端"
            fi
            start_frontend || exit 1
            ;;
        
        stop)
            stop_all
            ;;
        
        status|--status|check|--check)
            check_status
            ;;
        
        restart)
            stop_all
            sleep 2
            $0 start
            ;;
        
        *)
            echo "用法: $0 [start|stop|restart|status|backend-only|frontend-only]"
            echo ""
            echo "命令说明:"
            echo "  start        启动所有服务"
            echo "  stop         停止所有服务"
            echo "  restart      重启所有服务"
            echo "  status       查看服务状态"
            echo "  backend-only 仅启动后端"
            echo "  frontend-only 仅启动前端"
            exit 1
            ;;
    esac
}

main "$@"
