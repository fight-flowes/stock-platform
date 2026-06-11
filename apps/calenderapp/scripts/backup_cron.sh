#!/bin/bash
# 数据库备份脚本
# 使用方式: 添加到 crontab
#   0 2 * * * /path/to/backup_cron.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/runtime/backups}"
CONTAINER_NAME="${POSTGRES_CONTAINER:-postgres-calendar}"
DATABASE="${POSTGRES_DATABASE:-calenderdb}"
USER="${POSTGRES_USER:-postgres}"
LOG_DIR="${LOG_DIR:-${PROJECT_DIR}/logs}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/stock_backup.log}"

# 保留天数
RETENTION_DAYS=30

# 创建备份目录
mkdir -p "$BACKUP_DIR" "$LOG_DIR"

# 生成备份文件名
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.sql"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始备份数据库..." >> "$LOG_FILE"

# 执行备份
docker exec "$CONTAINER_NAME" pg_dump -U "$USER" "$DATABASE" > "$BACKUP_FILE"

# 压缩备份
gzip "$BACKUP_FILE"
BACKUP_FILE_GZ="$BACKUP_FILE.gz"

# 计算文件大小
SIZE=$(du -h "$BACKUP_FILE_GZ" | cut -f1)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 备份完成: $BACKUP_FILE_GZ ($SIZE)" >> "$LOG_FILE"

# 清理旧备份
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 清理 $RETENTION_DAYS 天前的备份..." >> "$LOG_FILE"
find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# 统计备份文件数量
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "backup_*.sql.gz" | wc -l)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 当前备份数: $BACKUP_COUNT" >> "$LOG_FILE"
