# 事件核查（Event Review）技术文档

> 覆盖范围：事件中心 `/events` 页面的「核查」按钮 → Vibe-Trading → event-review-mcp → Brave Search 的完整链路，以及配套的 session 复用机制与定时 GC。
>
> 维护说明：本功能涉及 calenderapp / stockkb / Vibe-Trading / event-review-mcp 四个组件协作，本文档是唯一的整体说明，组件内部的细节请回到各仓库源码。

---

## 1. 功能定位

事件中心里的事件都是从涨停研报里 LLM 抽取出来的（`kb_simple_event` → 聚合成 `kb_market_event`），它们只是报告里的**陈述**，未必真实、时间未必准。事件核查用一个带联网检索能力的 AI Agent（Vibe-Trading + event-review-mcp）去验证每个事件：

| 维度 | 字段 | 含义 |
|---|---|---|
| 真实性 | `event_truth` | 这件事是否真实发生（true / dubious / unverified / false） |
| 时间一致性 | `time_truth` | 报告里的时间是否准确 |
| 内容支持 | `content_truth` | 报告内容是否有证据支持 |
| 研究结论 | `disposition` | adopt / adopt_with_caution / needs_review / reject |
| 置信度 | `confidence` | 0.0 ~ 0.95 |

核查结果落库到 stockkb 的 `kb_market_event_review` 表（DuckDB），主键 `event_key`，一个事件一条核查记录。

## 2. 调用链

```
[前端 /events 页面]
  EventList「核查」按钮 @click -> EventsView.openReview(item)
        │
[/events 页面]
  review_status=completed -> 直接打开弹窗 + loadReview（走缓存）
  其他                    -> runReview(force=False) 触发新核查
        │
[前端 api/stockkb.js]
  POST /api/stockkb/market-events/{key}/review/run
  POST /api/stockkb/market-events/{key}/review/refresh   (force=True)
  GET  /api/stockkb/market-events/{key}/review
        │
[calenderapp Flask 后端]  app/api/stockkb.py
  -> EventReviewService.run_review(event_key, force)
        │
        │ ① 缓存判断：已 completed 且非 force -> 返回 (source=cache)
        │ ② StockkbProxyService.run_market_event_review -> DuckDB 标记 pending
        │ ③ 取事件详情
        │ ④ 构造 prompt（_build_review_prompt，5 字段 JSON）
        │ ⑤ _acquire_session_id：复用 DuckDB 里的 vibe_session_id，失效则新建
        │ ⑥ 写 pending 占位（含 vibe_session_id）
        │ ⑦ VibeTradingProxyService.send_message(session_id, prompt)
        │ ⑧ wait_for_completion(timeout=90s) -> SSE 监听 attempt.completed/failed
        │ ⑨ get_messages -> _extract_review_json -> _normalize_review_payload
        │ ⑩ _save_completed_review -> PUT -> DuckDB upsert
        │    失败路径 -> _save_failed_review -> status=failed
        ▼
[Vibe-Trading Agent]  http://127.0.0.1:8899  (需 VIBE_TRADING_API_KEY)
  ReAct loop，stdio 拉起 event-review-mcp 子进程，调用其 verify_event 工具
        ▼
[event-review-mcp]  ~/.vibe-trading/agent.json 中注册为 "event-review"
  EventReviewer.verify_event -> Brave Search -> 4 个评分函数 -> 结构化结论
        ▼
[DuckDB]  kb_market_event_review
```

## 3. 组件依赖

| 组件 | 地址 / 入口 | 配置 |
|---|---|---|
| calenderapp Flask | http://127.0.0.1:5000 | `backend/.env` |
| stockkb FastAPI | http://127.0.0.1:8040 | DuckDB 文件 `apps/stockkb/data/stockkb.duckdb` |
| Vibe-Trading API | http://127.0.0.1:8899 | 需 `VIBE_TRADING_API_KEY`；MCP 配置在 `~/.vibe-trading/agent.json` |
| event-review-mcp | stdio 子进程 | `~/.vibe-trading/agent.json` 注册；自带 `.env` 提供 `BRAVE_SEARCH_API_KEY` |
| Brave Search API | api.search.brave.com | 免费层 ~2000 次/日 |

任一环节缺失，核查会落到 `failed` 状态。

## 4. Session 复用机制（每事件 1 个 session）

### 背景

calenderapp 最初每次 `run_review` 都无条件新建 Vibe-Trading session，导致 session 数随重试次数线性增长（测试期 9 个事件产生 15 个 session）。

### 现状

[event_review_service.py](../backend/app/services/event_review_service.py) 的 `_acquire_session_id(event_key, existing)`：

1. 读 DuckDB `kb_market_event_review.vibe_session_id`
2. 用 `VibeTradingProxyService.get_session()` 探活
   - 200 → 复用该 session
   - 404 → 上游已删，回退新建
3. 探活失败（非 404 异常）也回退新建，不阻断核查

效果：**每个 event_key 至多 1 个 session**，重试不再产生新 session。

### DuckDB 字段语义

`vibe_session_id` 现在是"权威指针"：

- 非空 → 指向 Vibe-Trading 上当前可复用的 session
- 空 → 下次核查会新建

stockkb 的 upsert 已支持显式清空：当 PUT payload 里 `vibe_session_id` 是空串时，**清空字段**而不是回退到旧值（区别于"key 不在 payload 里"=保留旧值）。

## 5. 定时 GC

### 为什么需要

复用机制堵住了"重试产生孤儿"的源头，但两类残留仍需定期清理：

1. **孤儿 session**：`Event Review *` session 上游存在，但 DuckDB 里没有任何 `vibe_session_id` 指向它（来源：历史遗留、外部脚本误建）
2. **死引用**：DuckDB 里 `vibe_session_id` 指向某 ID，但上游已 404（来源：Vibe-Trading 重置、人工删除）

### 调度策略

| 参数 | 默认值 | env 变量 |
|---|---|---|
| 开关 | true | `REVIEW_GC_ENABLED` |
| 日常运行时间 | `03:37` 本地时间 | `REVIEW_GC_DAILY_AT` |
| 启动后首次延迟 | 300 秒（5 分钟） | `REVIEW_GC_STARTUP_DELAY_SECONDS` |
| 单次删除上限 | 200 | `REVIEW_GC_MAX_DELETE_PER_RUN` |

选 **每天 1 次** 而非更频：

- 孤儿 / 死引用都是低频产生，不需要小时级响应
- 每天一次跟日志按天对齐，运维直觉友好
- 03:37（避开 :00 / :30）避免与其他 housekeeping 任务并发
- 启动 5 分钟钩子兜住"上次进程在 03:37 前崩了"的边界情况

### 实现方式

`threading.Thread` 守护线程（`apps/calenderapp/backend/app/scheduler.py`），在 `main.py` 启动时 `ReviewGCScheduler.start()` 拉起。

选线程而非 APScheduler / 系统 cron 的理由：

- 任务简单且低频（每天几次 HTTP 调用）
- 必须跑在 Flask 进程内，复用现有 settings / proxy 配置
- `daemon=True`，进程退出即回收，不泄漏 worker
- 自动跳过 Flask debug 模式的 reloader 父进程，避免双重启动

### 扫描范围

**仅** `title` 以 `"Event Review "` 开头的 session。其他 session（交互式、其他前缀）即使看起来是孤儿也不动。

### 清理动作

| 类型 | 动作 |
|---|---|
| 孤儿 session | `DELETE /sessions/{id}` 删上游 |
| 死引用 | `PUT /kb/simple/market-events/{key}/review`，传 `vibe_session_id=""` 清空 DuckDB 字段（其余核查结论保留） |

### 运维入口

```bash
# 看上次 GC 跑得怎样
curl http://127.0.0.1:5000/api/stockkb/review/gc/status

# 立刻跑一次（不等到 03:37）
curl -X POST http://127.0.0.1:5000/api/stockkb/review/gc/run
```

返回结构（`ReviewSessionGCService.GCRunResult`）：

```json
{
  "started_at": "...",
  "finished_at": "...",
  "duration_seconds": 0.112,
  "upstream_sessions_scanned": 22,
  "event_review_sessions": 12,
  "referenced_session_ids": 12,
  "orphan_sessions_found": 0,
  "orphan_sessions_deleted": 0,
  "dead_references_found": 0,
  "dead_references_cleared": 0,
  "skipped_due_to_cap": 0,
  "errors": []
}
```

## 6. 相关代码

### calenderapp（`apps/calenderapp/backend/app/`）

| 文件 | 职责 |
|---|---|
| `services/event_review_service.py` | 核查编排：缓存判断 / prompt 构造 / session 复用 / 结果解析 / 落库 |
| `services/vibe_trading_proxy_service.py` | Vibe-Trading HTTP 客户端：create / get / delete session, send_message, wait_for_completion |
| `services/stockkb_proxy_service.py` | stockkb HTTP 客户端：get/put/run review, list session_ids |
| `services/review_session_gc_service.py` | 单次 GC 扫描 + 删除核心 |
| `scheduler.py` | daemon 线程调度器 |
| `api/stockkb.py` | Flask 路由：review run/refresh/get + GC run/status |
| `settings.py` | 4 个 GC 配置开关 |

### stockkb（`apps/stockkb/src/stockrag/`）

| 文件 | 职责 |
|---|---|
| `event_kb/storage/duckdb_backend.py` | DuckDB 查询：review get/upsert, list session_ids, vibe_session_id 显式清空 |
| `event_kb/storage/ddl.py` | `kb_market_event_review` 表结构 |
| `event_kb/services/extraction_service.py` | service 层包装 |
| `api.py` | FastAPI 路由：`/kb/simple/market-events/{key}/review[/run]` + `/reviews/sessions` |

### 外部组件（不在本仓库）

| 路径 | 职责 |
|---|---|
| `~/workspace/mcp/event-review-mcp/` | MCP 工具 `verify_event`，调 Brave Search + 评分 |
| `~/workspace/stock_info/github/Vibe-Trading/` | AI Agent 服务，ReAct loop |
| `~/.vibe-trading/agent.json` | Vibe-Trading 的 MCP server 注册（含 event-review） |

## 7. 已知短板（待优化）

- **核查质量**：DuckDB 现存核查记录普遍 `unverified` + `needs_review`，置信度低。根因在 event-review-mcp 的查询构造（query 太长导致 match_level 全 weak）与评分阈值，非基础设施问题。
- **同步阻塞**：`run_review` 同步等 SSE 90s，UI 点击即锁。可改异步 + 前端轮询。
- **pending 卡死风险**：`pending` 状态无过期机制，服务崩了会永远显示"核查中"。
- **ReAct 中间过程未存档**：Vibe-Trading 的 `attempt.json.react_trace` / `events.jsonl` 实测为空，失败排障困难。
