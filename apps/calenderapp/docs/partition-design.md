# 涨停股表分区设计文档

## 背景

随着每日涨停数据的持续入库，单表数据量会快速增长：
- 日均新增 50-100 条记录
- 1 年约 1.5-3 万条
- 3 年约 5-10 万条
- 5 年可能超过 15 万条

单表长期使用会导致：
1. 查询性能下降
2. 索引维护成本增加
3. 数据清理困难
4. 备份恢复耗时增长

## 解决方案

采用 PostgreSQL 原生**按月分区**方案。

### 分区策略

```
sc.limit_up_stocks (主表)
    ├── limit_up_stocks_202508 (2025年8月)
    ├── limit_up_stocks_202509 (2025年9月)
    ├── ...
    ├── limit_up_stocks_202604 (2026年4月)
    ├── ...
    └── limit_up_stocks_default (默认分区)
```

### 分区优势

| 优势 | 说明 |
|------|------|
| **查询提速** | 只扫描相关分区，跳过历史数据 |
| **写入无影响** | 每日数据只写入当月分区 |
| **维护方便** | 可单独对历史分区做 VACUUM、索引重建 |
| **归档简单** | 旧分区可直接 detach 导出 |
| **应用透明** | SQL 语句不变，自动路由 |

### 主键设计

分区表要求**主键必须包含分区键**：

```sql
PRIMARY KEY (id, limit_up_date)
```

## 索引设计

| 索引名 | 字段 | 用途 |
|--------|------|------|
| idx_limit_up_date | limit_up_date | 日期查询 |
| idx_limit_up_stock_code | stock_code | 股票代码查询 |
| idx_limit_up_industry | industry | 行业筛选 |
| idx_limit_up_consecutive | consecutive_days DESC | 连板排序 |
| idx_limit_up_strength | strength_level DESC | 强度排序 |
| idx_limit_up_dragon | is_dragon_head | 龙头筛选（部分索引） |
| idx_limit_up_concepts | concept_tags (GIN) | JSONB 数组查询 |
| idx_limit_up_date_consecutive | limit_up_date, consecutive_days DESC | 连板榜 |
| idx_limit_up_date_institution | limit_up_date, institution_net_buy DESC | 机构排行 |
| idx_limit_up_date_hot_money | limit_up_date, hot_money_net_buy DESC | 游资排行 |

## 迁移步骤

### 1. 备份数据

```bash
pg_dump -h 127.0.0.1 -U postgres -d calenderdb -t sc.limit_up_stocks > backup.sql
```

### 2. 执行迁移

```bash
cd backend/migrations
PGPASSWORD=postgres123 psql -h 127.0.0.1 -U postgres -d calenderdb -f 001_partition_limit_up.sql
```

### 3. 验证迁移

```sql
-- 查看分区列表
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as size
FROM pg_tables 
WHERE schemaname = 'sc' AND tablename LIKE 'limit_up_stocks_%'
ORDER BY tablename;

-- 查看各分区数据量
SELECT tableoid::regclass as partition, COUNT(*) as records
FROM sc.limit_up_stocks
GROUP BY tableoid
ORDER BY partition;
```

### 4. 回滚（如需要）

```bash
PGPASSWORD=postgres123 psql -h 127.0.0.1 -U postgres -d calenderdb -f 001_partition_limit_up_rollback.sql
```

## API 接口

分区管理 API 位于 `/api/partition`：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/partition/status` | GET | 获取分区状态 |
| `/api/partition/create?year=2026&month=5` | POST | 创建指定月份分区 |
| `/api/partition/create-future?months=3` | POST | 批量创建未来分区 |
| `/api/partition/next-month` | POST | 创建下月分区 |
| `/api/partition/detach/<name>` | POST | 分离分区（归档） |
| `/api/partition/drop/<name>` | DELETE | 删除已分离分区 |

## 自动分区维护

建议设置定时任务，每月初自动创建下月分区：

### 方式一：系统 Cron

```bash
# 每月 1 日 00:05 执行
5 0 1 * * cd /path/to/backend && python -c "from app.services.partition_service import auto_create_partition_job; auto_create_partition_job()"
```

### 方式二：应用内定时器

在 `main.py` 中添加 APScheduler：

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(auto_create_partition_job, 'cron', day=1, hour=0, minute=5)
scheduler.start()
```

## 冷热数据分离

长期策略（数据量 > 20 万条时）：

```
热数据（近 3 个月）    → SSD 存储，活跃分区
温数据（3-12 个月）   → 可压缩，只读分区
冷数据（1 年以上）    → detach 导出为 Parquet，存 MinIO
```

归档脚本示例：

```python
# 分离 1 年前的分区
old_partition = "limit_up_stocks_202508"
PartitionService.detach_partition(old_partition)

# 导出为文件（可选）
# pg_dump -t sc.limit_up_stocks_202508 > 202508.sql
# 或转换为 Parquet 格式存入 MinIO
```

## 文件清单

| 文件 | 说明 |
|------|------|
| `migrations/001_partition_limit_up.sql` | 分区迁移 SQL |
| `migrations/001_partition_limit_up_rollback.sql` | 回滚 SQL |
| `app/models/limit_up_stock.py` | 修改后的模型 |
| `app/services/partition_service.py` | 分区管理服务 |
| `app/api/partition.py` | 分区管理 API |
| `docs/partition-design.md` | 本文档 |

## 注意事项

1. **迁移时机**：选择低峰期执行，避免影响业务
2. **备份**：迁移前务必备份
3. **分区键不可修改**：`limit_up_date` 作为分区键，修改会导致数据迁移到新分区
4. **默认分区**：防止意外日期数据写入失败
5. **主键变化**：从单字段 `id` 改为复合主键 `(id, limit_up_date)`

---

更新日期：2026-04-03