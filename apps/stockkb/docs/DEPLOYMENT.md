# StockKB Deployment

## 1. 当前定位

`stockkb` 现在已经收敛为一套 **simple-only 事件抽取服务**。

系统只保留下面这些结构化结果：

- `event_name`
- `event_time_text`
- `event_content`
- `affected_stocks`
- `risk_summary`

不再维护旧的复杂事件关系、证据链、图谱、研究回填等复杂事件设计。

## 2. Python 环境

默认运行环境为 `stock`：

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate stock
cd /home/leisaihua/workspace/stock_info/stock-platform/apps/stockkb
pip install -U pip
pip install -e .
```

## 3. 关键配置

常用环境变量：

```bash
STOCKKB_DUCKDB_PATH=/home/leisaihua/workspace/stock_info/stock-platform/apps/stockkb/data/stockkb.duckdb
STOCKKB_LLM_EXTRACT_ENABLED=true
STOCKKB_LLM_EXTRACT_BASE_URL=https://api.deepseek.com/v1
STOCKKB_LLM_EXTRACT_MODEL=deepseek-v4-flash
STOCKKB_LLM_EXTRACT_API_KEY=...
STOCKKB_LLM_EXTRACT_TEMPERATURE=0
```

## 4. 启动

启动 API：

```bash
cd /home/leisaihua/workspace/stock_info/stock-platform/apps/stockkb
bash scripts/manage.sh start
```

查看状态：

```bash
bash scripts/manage.sh status
```

停止：

```bash
bash scripts/manage.sh stop
```

## 5. 导入

单个 MinIO 文件：

```bash
conda run --no-capture-output -n stock python -m stockrag import-minio-object \
  '2026/06/01/601101_昊华能源.md' \
  --bucket stockinfo
```

整天批量导入：

```bash
conda run --no-capture-output -n stock python -m stockrag import-minio-prefix \
  --bucket stockinfo \
  --prefix '2026/06/01'
```

## 6. 当前 HTTP 接口

对外只保留 simple 接口：

- `POST /kb/simple/reports`
- `POST /kb/simple/events`
- `GET /kb/simple/events/{event_id}`
- `GET /kb/stats`

以及导入接口：

- `POST /kb/import/minio/object`
- `POST /kb/import/minio/prefix`
- 可选本地导入接口

## 7. DuckDB 表

当前只使用两张主表：

- `kb_simple_report`
- `kb_simple_event`

不再要求旧的复杂事件表、关系表和研究表。

## 8. 验证

查看统计：

```bash
conda run -n stock python -m stockrag kb-stats
```

查询简单报告：

```bash
conda run -n stock python -m stockrag kb-query-simple-reports --report-date 2026-06-01
```

查询简单事件：

```bash
conda run -n stock python -m stockrag kb-query-simple-events --stock-code 601101 --report-date 2026-06-01
```
