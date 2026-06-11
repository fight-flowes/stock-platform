#!/bin/bash
# 涨停数据定时同步脚本
# 使用方式: 添加到 crontab
#   0 18 * * 1-5 /path/to/sync_cron.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
API_BASE="${API_BASE:-http://127.0.0.1:5000}"
LOG_DIR="${LOG_DIR:-${PROJECT_DIR}/logs}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/stock_sync.log}"
MANAGE_SCRIPT="${MANAGE_SCRIPT:-${PROJECT_DIR}/manage.sh}"

mkdir -p "$LOG_DIR"

# 获取当前日期
TODAY=$(date +%Y-%m-%d)
DAY_OF_WEEK=$(date +%u)

# 周末不执行
if [ "$DAY_OF_WEEK" -gt 5 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 周末不执行同步" >> "$LOG_FILE"
    exit 0
fi

# 检查服务是否运行
if ! curl -s "$API_BASE/health" > /dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: 服务未运行，尝试启动..." >> "$LOG_FILE"
    bash "$MANAGE_SCRIPT" start
    sleep 10
fi

# 检查今天是否是交易日
IS_TRADING=$(curl -s "$API_BASE/api/calendar/days?start_date=$TODAY&end_date=$TODAY" | \
    python3 -c "import json,sys; d=json.load(sys.stdin); items=d.get('data',{}).get('items',[]); print('true' if items and items[0].get('is_work') else 'false')" 2>/dev/null || echo "true")

if [ "$IS_TRADING" != "true" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 今日非交易日，跳过同步" >> "$LOG_FILE"
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始同步涨停数据..." >> "$LOG_FILE"

# 执行完整同步
SYNC_RESULT=$(curl -s -X POST "$API_BASE/api/limit-up/sync-full?date=$TODAY")

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 同步结果: $SYNC_RESULT" >> "$LOG_FILE"

# 解析同步结果
CREATED=$(echo "$SYNC_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('created',0))" 2>/dev/null || echo "0")
UPDATED=$(echo "$SYNC_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('updated',0))" 2>/dev/null || echo "0")

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 同步完成: 新增 $CREATED 条，更新 $UPDATED 条" >> "$LOG_FILE"
