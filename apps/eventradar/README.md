# eventradar

> Forward-looking event radar for the A-share market — wraps `akshare` to
> surface "expected events" (业绩预披露 / 限售解禁 / IPO / 宏观日历 / 行业活动 ...)
> behind a stable HTTP contract that `calenderapp` proxies into the
> "公告" tab of the platform UI.

This directory is the **skeleton** — every subsystem (config, storage,
FastAPI server, CLI) is wired up, but no adapters are written yet. The
empty server can already be pointed at by `calenderapp`'s proxy without
errors. Adapters land one at a time after this commit.

## Layout

```
eventradar/
├── Makefile, manage.sh, pyproject.toml      # entry points
├── data/                                    # DuckDB + raw_cache (gitignored)
│   ├── eventradar.duckdb                    # primary, written by CLI
│   ├── eventradar.read.duckdb               # read replica, served by API
│   └── raw_cache/                           # akshare raw parquet (audit)
├── docs/SIMPLE_ARCHITECTURE.md              # one-page design notes
└── src/eventradar/
    ├── api.py            # FastAPI app — 4 endpoints
    ├── cli.py            # `eventradar ...` command line
    ├── config.py         # env-based settings
    ├── service.py        # composes storage + adapters
    ├── normalize/        # ExpectedEvent dataclass + id helpers
    ├── sources/          # akshare_client.py + adapters/
    │   ├── akshare_client.py    # ★ ONLY file allowed to import akshare
    │   └── adapters/            # one file per upstream endpoint (empty)
    └── storage/          # DuckDB DDL + read-replica publisher
```

## Architecture in one paragraph

`akshare` is invoked **only** from `sources/akshare_client.py`. Adapters
under `sources/adapters/` translate one upstream endpoint into a list of
`ExpectedEvent` dataclasses (`normalize/schemas.py`). The CLI's `pull`
subcommand runs an adapter, upserts the result into `eventradar.duckdb`,
and atomically copies the file onto `eventradar.read.duckdb` — the
**only** file the FastAPI server reads from. That gives us writer/reader
separation without a real DBMS:

```
[ cron ] -> manage.sh pull X -> primary DuckDB -> publish_replica()
                                                          |
                                                          v
                                       read replica -> FastAPI -> calenderapp proxy -> UI
```

## Quickstart

```bash
cd /home/leisaihua/workspace/stock_info/stock-platform/apps/eventradar

# Install the skeleton (no akshare yet — that comes with the first adapter)
make install

# Sanity-check resolved settings
make show-config

# Boot the API on :8050 (empty data, but contract is live)
make serve

# In calenderapp:
#   export EVENTRADAR_API_BASE_URL=http://127.0.0.1:8050
# The "公告" page now hits eventradar instead of returning placeholder.
```

Once the first adapter ships, you'll add:

```bash
make install-adapters   # adds akshare + pyarrow

# Adapter run + replica publish in one shot
make pull ADAPTER=company_calendar_em ARGS="days=30"
```

## M1 — company calendar adapter (live)

The `company_calendar_em` adapter wraps
`akshare.stock_gsrl_gsdt_em(date='YYYYMMDD')` — 东方财富数据中心"股市日历-公司动态"。
One call per calendar day, mapped to `ExpectedEvent` rows and upserted by
`(source, source_fingerprint)`.

### Running it

```bash
# akshare is now a default dep, so plain `make install` is enough.
make install

# Pull a 7-day window starting 2026-06-13 (a past window — see note below).
make pull ADAPTER=company_calendar_em ARGS="date=20260613 days=7"

# Then boot the API (reads the replica published by `pull`):
make serve
```

### Important: gsdt is a *today's disclosures* feed, not a future calendar

`stock_gsrl_gsdt_em(date=...)` returns the company events that were
**publicly disclosed on** `date` — not events scheduled to happen on `date`.
Empirically the upstream returns `data: null` for any date that has had no
disclosures yet, including all weekends and most future weekdays. So:

* Pulling `days=N` starting **today** usually returns very few rows (only
  what's been disclosed so far today).
* Pulling a **trailing window** (e.g. the last 7 calendar days) returns a
  rich stream of `资产重组 / 对外担保 / 股份质押 / 限售解禁 / 股东大会`
  events, each with the disclosure date as `expected_at`.

The `具体事项` text frequently references future dates ("于 2026 年 6 月 25
日召开股东大会"), so even a trailing pull surfaces genuinely forward-looking
content — M3's enricher will parse those dates out. For now the adapter is
honest: `expected_at` = disclosure date, `event_content` carries the raw
text including any future-date references.

The adapter **tolerates** null-response days (weekends, holidays, future
dates) — each is logged as `gsrl_skip_day` and the run continues. A whole
run producing zero rows is *not* an error; it just means the window had no
disclosures.


## Scheduling (cron)

Adapters are intended to run from cron, not from the API process. Because
gsdt is a *today's disclosures* feed, the useful cadence is "pull today +
a short trailing window" once per day after market close — that captures
each day's new disclosures and backfills any the previous run missed.

```cron
# 17:31 weekdays — pull today + the previous 6 calendar days. Off the :00/:30
# marks to avoid colliding with every other housekeeping job. Re-running the
# trailing days is cheap (idempotent upsert by fingerprint) and self-heals
# any single-day upstream outage.
31 17 * * 1-5  /home/leisaihua/workspace/stock_info/stock-platform/apps/eventradar/manage.sh \
               pull company_calendar_em date=$(date +\%Y\%m\%d) days=7 \
               >> /home/leisaihua/workspace/stock_info/stock-platform/apps/eventradar/logs/cron.log 2>&1
```

`manage.sh` activates the `stock` conda env explicitly so cron's bare
environment doesn't break things. Note the escaped `%` in `$(date +\%Y\%m\%d)`
— cron treats unescaped `%` as a newline.

## HTTP contract

All four endpoints are mirrored on the `calenderapp` side
(`EventradarProxyService`) — keep them in sync.

| Endpoint                                    | Purpose                                              |
|---------------------------------------------|------------------------------------------------------|
| `GET  /health`                              | Liveness probe                                       |
| `POST /events/expected`                     | Paginated list with filters                          |
| `GET  /events/expected/{event_id}`          | Single event detail                                  |
| `GET  /events/expected/filters/meta`        | Distinct values for filter dropdowns                 |

Field names align with stockkb's `market_event` shape so the UI can reuse
existing components — see `normalize/schemas.py` for the canonical list.

## Status

| Layer                 | State                                          |
|-----------------------|------------------------------------------------|
| Config                | ✅ done                                        |
| DuckDB DDL + replica  | ✅ done (read/write helpers complete)          |
| `akshare_client`      | ✅ retry loop + raw parquet cache              |
| FastAPI server        | ✅ real data, UTF-8 Chinese output             |
| CLI                   | ✅ all subcommands wired                       |
| Adapters              | ✅ `company_calendar_em` (live)                |
| Storage upsert/list   | ✅ implemented (delete-then-insert upsert)     |
| Enrichment (M3)       | ✅ industries / leaders / importance / future-date |

## M3 — enrichment layer

Enrichment is a **separate stage** from ingestion, so adapters stay pure
(they still emit `industries=[]`, `importance=1`) and the enricher fills
the four enrichment dimensions afterward. The pipeline is:

```
pull company_calendar_em  →  refresh-stock-meta  →  enrich
(akshare 拉数)              (补 stock_meta 缓存)    (回填 4 维 + 发布副本)
```

Each stage is independently re-runnable and idempotent.

### Running it

```bash
# 1. Pull (already done in M1; only needed when refreshing the window)
make pull ADAPTER=company_calendar_em ARGS="date=20260613 days=7"

# 2. Warm the stock_meta cache (industry + 流通市值 per stock).
#    Uses akshare stock_individual_info_em (push2 endpoint — needs network).
#    Per-stock failures are skipped, not fatal.
eventradar refresh-stock-meta
# or force-refresh specific codes:
eventradar refresh-stock-meta --codes 600519,000002

# 3. Enrich — fills industries / leaders / importance / expected_at_end.
eventradar enrich          # only rows where enriched_at IS NULL
eventradar enrich --all    # re-enrich everything (after a meta refresh)
```

### What each enricher does

* **`future_date_parser`** — regex-scans `event_content` for Chinese/ISO
  dates, picks the earliest one *later than the disclosure date*, stores it
  as `expected_at_end`. For gsdt's guarantee/pledge rows this surfaces the
  担保/质押 **到期日** — the only forward-looking signal that feed has.
  (Honest caveat: these are expiry endpoints, not catalytic event
  schedules. M2's 业绩预告/解禁日历 will produce genuinely catalytic dates
  through the same parser.)
* **`industry_mapper`** — looks up each event's stock codes in `stock_meta`
  → fills `industries`. Enables "filter events by industry".
* **`leader_scorer`** — marks `leaders` = stocks with 流通市值 ≥ threshold
  (default 500 亿, env `EVENTRADAR_LEADER_FLOAT_MV`). Source-agnostic; we
  deliberately don't couple to calenderapp's 涨停龙虎 here.
* **`importance_rules`** — score 0–3: base 1, +1 high-impact type
  (restructuring/unlock/earnings_forecast/secondary_offering), +1 touches a
  leader, +1 `expected_at_end` within 30 days.

### Degradation

If `stock_meta` is cold (push2 unreachable, cache empty), `enrich` still
completes: `industries`/`leaders` stay empty and `importance` falls back to
type + future-date only. Rows still get `enriched_at` set so they aren't
retried pointlessly. Re-run `refresh-stock-meta` + `enrich --all` once the
cache is warm.

### Honest note on the current gsdt data

The 701 gsdt rows are dominated by guarantee/restructuring/pledge
disclosures — a **backward-looking** stream. M3 enrichment on them delivers
modest visible value (industry filtering, large-cap flagging, expiry dates).
The enrichment *machinery* is the real deliverable: M2's forward-looking
sources (业绩预告 / 宏观日历 / 解禁日历) flow through the same enrichers and
will produce genuinely "expected / industry-impacting / leader-impacting"
events.

## Next steps

`company_calendar_em` + M3 enrichment are live. Outstanding work:

* **M2** — more adapters (the high-value forward-looking sources): 业绩预告
  (`stock_yjyg_em`), 预约披露 (`stock_yysj_em`), 百度交易提醒
  (`news_trade_notify_*_baidu`), 宏观日历 (`news_economic_baidu` /
  `macro_info_ws`). Each flows through the M3 enrichers automatically.
* **M4** — cron scheduling + a `source_health` table surfaced through
  `/health` so the calenderapp badge can flag stale data.
