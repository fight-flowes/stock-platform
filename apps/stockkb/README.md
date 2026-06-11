# stockkb

面向 `calenderapp` 的股票结构化事件知识库服务，使用：

- FastAPI 提供 `/kb/*` 查询接口
- MinIO 作为 Markdown 报告来源
- DuckDB 作为结构化事件知识库存储

## 设计目标

- 对 Markdown 结构化研报友好
- 聚焦报告抽取、事件落库和研究指标查询
- 只服务 `calenderapp` 的事件知识库链路
- 不承担通用检索型 RAG 能力

## 基本命令

默认推荐：
- 生产/Agent 入库默认走 `MinIO stockinfo`
- 本地 `import-file` / `import-folder` 仅保留给 `dev/debug`

CLI 方式：

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate stock
stockkb import-minio-object 2026/05/07/000509_华塑控股.md
stockkb import-minio-prefix --prefix 2026/05/07
stockkb serve --host 0.0.0.0 --port 8040
```

本地调试入口：

```bash
stockkb import-file /absolute/path/to/report.md
stockkb import-folder /path/to/reports --pattern "**/*.md"
```

Make 方式：

```bash
cd /home/leisaihua/workspace/stock_info/stock-platform/apps/stockkb
make show-config
make import-minio-object OBJECT_NAME='2026/05/07/000509_华塑控股.md'
make import-minio PREFIX='2026/05/07'
make serve PORT=8040
```

本地调试入口：

```bash
make import-file FILE=/absolute/path/to/report.md
make import FOLDER=/path/to/reports PATTERN="**/*.md"
```

如果你希望 API 只暴露 `MinIO` 入库接口，可以在 `.env` 里设置：

```env
API_ENABLE_LOCAL_INGEST=false
```

如果你必须在 API 中临时启用本地 ingest，请同时设置白名单根目录：

```env
API_ENABLE_LOCAL_INGEST=true
LOCAL_INGEST_ALLOWED_ROOTS=/absolute/path/to/reports
```

这样 FastAPI 会保留：
- `/kb/import/minio/object`
- `/kb/import/minio/prefix`
- `/ingest/minio/object`
- `/ingest/minio/prefix`

并隐藏本地入口：
- `/kb/import/file`
- `/kb/import/folder`
- `/ingest/file`
- `/ingest/folder`

即使显式开启本地入口，也只允许摄取白名单根目录下的 Markdown 文件。
