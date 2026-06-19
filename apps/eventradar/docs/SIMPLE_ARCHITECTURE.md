# eventradar Simple Architecture

## 1. 目标

* 围绕 A 股"事件驱动"投研主线，补齐**预期事件**（forward-looking events）
* 输入是公开数据源（`akshare` 包装的东方财富 / 巨潮 / 百度股市通 / 华尔街见闻 等）
* 输出是稳定的 HTTP 契约，由 `calenderapp` 后端做 proxy，前端"公告"页消费
* 与 `stockkb`（已发生事件、Markdown 抽取）在职责上互补，**不重叠**

## 2. 输入假设

每个"预期事件"来自三类源：

| 类型 | 例子 | 处理方式 |
|---|---|---|
| 结构化日历 | 东财股市日历 (`stock_gsrl_gsdt_em`) | adapter 直接映射字段，无需 LLM |
| 半结构化预告 | 业绩预告 (`stock_yjyg_em`) / 预约披露 | adapter + 字段归一 |
| 非结构化电报 | 财联社、CCTV、宏观日历 | 先关键词规则；M5 引入 LLM |

## 3. 输出模型

`ExpectedEvent`（见 `normalize/schemas.py`）字段命名故意与 stockkb 的
`MarketEventDetail` 对齐 —— `event_name / event_type / event_scope /
scope_reason / affected_industries / affected_themes / affected_stocks` ——
这样前端组件可以两边复用。

预期专属字段：

| 字段 | 含义 |
|---|---|
| `expected_at` | 主时间锚（DATE，可排序） |
| `expected_at_end` | 区间事件结束日 |
| `time_certainty` | `confirmed_date` / `month` / `quarter` / `rumor` |
| `importance` | 0–3，由 enricher 在 M3 阶段填 |
| `source` | 上游数据源 enum |
| `source_fingerprint` | 跨次拉取去重键 |
| `status` | `expected` / `materialized` / `obsolete` |

## 4. 物理架构

```
            cron / systemd-timer
                   │
                   ▼
           manage.sh pull X
                   │
                   ▼
       eventradar.cli  ──►  EventradarService.run_adapter()
                                  │
       ┌──────────────────────────┼─────────────────────────┐
       ▼                          ▼                         ▼
 sources/akshare_client    sources/adapters/X     storage/duckdb_backend
       │                          │                         │
       └────────► raw_cache/      │                         │
                  (parquet)       └──► ExpectedEvent ──────►│
                                                            ▼
                                              eventradar.duckdb (primary, RW)
                                                            │
                                              storage.publish_replica()
                                                            │
                                                            ▼
                                          eventradar.read.duckdb (RO snapshot)
                                                            │
                                                            ▼
                                              FastAPI uvicorn :8050
                                                            │
                                                            ▼
                                       calenderapp /api/announcements/*
                                                            │
                                                            ▼
                                            前端"公告"页 (AnnouncementsView)
```

## 5. 并发模型（方案 A · 只读副本）

* DuckDB 单进程多连接安全，但**多进程写不安全**
* 只有 CLI 进程开 `eventradar.duckdb`（读写）
* FastAPI 永远只开 `eventradar.read.duckdb`（只读）
* CLI 在 `upsert` 完成后调用 `publish_replica()` —— `shutil.copy2` 到 `.tmp`
  再 POSIX `rename`，对读端原子可见
* 没有锁、没有事件总线、没有外部依赖

如果未来同一进程同时跑两个 cron job（不太可能），加一个 `portalocker.Lock`
就够了。

## 6. 字段口径与去重

* `(source, source_fingerprint)` 是**唯一约束** —— 同一上游行多次拉取做 upsert
* `event_id = sha1("${source}:${source_fingerprint}")[:16]`，外部稳定可引用
* 上游字段命名变更 → adapter 内部消化，schema 不动
* 跨源同一事件（东财 + 百度都报"贵州茅台股东大会"）暂不合并 ——
  M2 在 normalizer 层加跨源去重（按 `expected_at + event_type + 主stock_code`）

## 7. 演进路线

| 阶段 | 内容 | DDL 变更 | 契约变更 |
|---|---|---|---|
| **M0** (本次) | 骨架 + 空 API | 创建 `expected_events` | 无 |
| **M1** | `company_calendar_em` adapter + 实际 upsert/list | 无 | 无 |
| **M2** | 业绩 / 百度 / 宏观 / IPO 4 个 adapter | 无 | 无 |
| **M3** | `industry_mapper` / `leader_scorer` / `importance_rules` | 可能新增 enricher 中间表 | 无 |
| **M4** | cron 调度 + `/health` 暴露 last_success_at per-source | 新增 `source_health` 表 | `/health` 字段扩展（向后兼容） |
| **M5** | 政策类 NLP 抽取（cls/cctv） | 无 | 无 |

## 8. 边界与原则

1. **`akshare` 只能在一个文件 import**（`sources/akshare_client.py`）。
   adapter 不准跨过这一层。
2. **adapter 不准触碰 DuckDB**。adapter 输入是 kwargs，输出是 `list[ExpectedEvent]`。
3. **API 不会触发 ingestion**。所有写入只来自 CLI / cron。
4. **schema 字段命名向 stockkb 对齐**。新字段加在 schema 末尾，不重命名旧字段。
5. **adapter 不静默丢行**。无法解析的行用 `event_type="other"` 落库，
   并 log 一条 warning。
6. **每次写入都更新只读副本**。不要让 API 看不到刚 upsert 的数据。
