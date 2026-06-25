# StockKB Simple Architecture

## 1. 目标

`stockkb` 现在的目标很简单：

- 从涨停分析 Markdown 报告中抽取少量高价值事件
- 为 `calenderapp` 的“事件”弹窗提供极简结构化结果

不再承担复杂知识图谱、关系链、研究回填、证据追踪等职责。

## 2. 输入假设

当前默认输入是 `limit-up-analyzer` 生成的 Markdown 报告。

这类原始文档具备几个前提：

- 标题、股票代码、股票名称、日期较稳定
- 通常包含“基本信息”“上涨核心逻辑”“催化因素分层与事件溯源”“风险提示”等章节
- 适合作为二次抽取输入，但不是最优的纯机器事件材料

当前 simple 链路的判断是：

- 原始 Markdown `能用`
- 事件溯源表格是最适合抽事件的核心区域
- “上涨核心逻辑”适合作为报告级 `core_logic`
- 搜索记录、验证记录、免责声明等区域需要在抽取时主动降噪

## 3. 输出模型

每份报告只保留：

### 报告级

- `report_id`
- `source_path`
- `source_name`
- `report_title`
- `core_logic`
- `stock_code`
- `stock_name`
- `report_date`
- `risk_summary`

### 事件级

- `event_id`
- `report_id`
- `event_name`
- `event_time_text`
- `event_time_normalized`
- `event_content`
- `event_scope`
- `scope_reason`
- `source_name`
- `source_url`
- `affected_industries`
- `affected_themes`
- `affected_stocks`

## 4. 主链路

```text
MinIO / Local Markdown
  -> metadata extract
  -> basic-info extract
  -> core-logic extract
  -> markdown parse
  -> simple LLM event extract
  -> SimpleReportBundle
  -> DuckDB
  -> simple query API
  -> calenderapp dialog
```

## 5. 对外集成边界

`stockkb` 当前只把自己看成一个 simple-only 事件摘要服务。

对外只保留这类 simple 接口：

- `POST /kb/simple/reports`
- `POST /kb/simple/events`
- `GET /kb/simple/events/{event_id}`
- `POST /kb/simple/market-events`
- `GET /kb/simple/market-events/{event_key}`
- `GET /kb/simple/market-events/{event_key}/timeline`
- `GET /kb/simple/market-events/filters/meta`
- `GET /kb/simple/market-events/{event_key}/review` — 读取核查结果
- `PUT /kb/simple/market-events/{event_key}/review` — upsert 核查结果（`vibe_session_id=""` 表示显式清空死引用）
- `POST /kb/simple/market-events/{event_key}/review/run` — 标记 pending
- `GET /kb/simple/market-events/reviews/sessions` — 轻量枚举所有非空 `vibe_session_id`（供 calenderapp GC 使用）
- `GET /kb/stats`

不再提供旧的：

- `/kb/reports`
- `/kb/events`
- `/kb/research`
- 复杂事件 graph / relation / rich detail 能力

因此无论是 `calenderapp` 还是未来的 OpenClaw 接入，都应把 `stockkb` 当成“极简事件摘要后端”，而不是事件知识图谱后端。

## 6. 代码结构

当前关键文件：

- `metadata.py`
- `event_kb/extractors/basic_info_extractor.py`
- `event_kb/extractors/core_logic_extractor.py`
- `event_kb/extractors/simple_llm_extractor.py`
- `event_kb/parsers/markdown_parser.py`
- `event_kb/pipeline/extract_simple_report.py`
- `event_kb/schemas/simple.py`
- `event_kb/storage/ddl.py`
- `event_kb/storage/duckdb_backend.py`
- `event_kb/services/extraction_service.py`
- `stockrag/api.py`
- `stockrag/cli.py`

## 7. 前端展示约束

`calenderapp` 相关弹窗当前只展示 simple-only 字段：

- “涨停列表 -> 事件”弹窗：
  - 顶部：报告状态、事件数、上涨逻辑、风险摘要
  - 详情：事件名称、时间、事件类型、事件内容、事件来源、影响个股
- “事件中心”详情弹窗：
  - 事件名称、时间、类型、事件内容、影响个股、事件来源
  - 不展示事件级风险摘要

## 8. 设计原则

- 报告级字段优先使用轻量规则抽取，不引入旧 chunking / rich schema
- 事件语义识别由 LLM 负责，候选块筛选和结果清洗由规则负责
- “上涨逻辑”属于报告级字段，不混入事件字段
- 时间原文优先保留，不强求严格标准化
- 风险只保留一条摘要，不拆分多条风险事件
- 受影响个股允许为空，但优先返回股票代码和名称
- 复杂证据链、关系链、研究指标全部删去

## 9. 不再支持的旧能力

以下能力已不再是当前系统目标：

- 复杂事件关系建模
- 事件分层依赖链
- 知识图谱
- research backfill
- 证据级结构化追踪管线
- 复杂事件标准化体系

如果未来要恢复这些能力，建议重新设计为独立子系统，而不是在当前 simple 链上叠加。
