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

## Scheduling (cron)

Adapters are intended to run from cron, not from the API process. A typical
crontab entry for the company calendar:

```cron
# Daily at 06:31 — pull next 30 days of company calendar events.
31 6 * * *  /path/to/apps/eventradar/manage.sh pull company_calendar_em days=30 \
            >> /path/to/apps/eventradar/logs/cron.log 2>&1
```

`manage.sh` activates the `stock` conda env explicitly so cron's bare
environment doesn't break things.

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

| Layer                 | State                                  |
|-----------------------|----------------------------------------|
| Config                | ✅ done                                |
| DuckDB DDL + replica  | ✅ done (read/write helpers complete)  |
| `akshare_client`      | ✅ retry loop done; lazy akshare import |
| FastAPI server        | ✅ returns empty payloads cleanly      |
| CLI                   | ✅ all subcommands wired                |
| Adapters              | ❌ none yet (next: `company_calendar_em`) |
| Storage upsert/list   | ❌ stubbed `NotImplementedError`        |
| Industry/leader enricher | ❌ M3                              |

## Next steps

The first adapter (`sources/adapters/company_calendar_em.py`) wraps
`akshare.stock_gsrl_gsdt_em(date=...)` and is what fills in `upsert_events`
+ `list_events` + `get_event` + `filter_meta` in `storage/duckdb_backend.py`.
After that lands, `make pull ADAPTER=company_calendar_em ARGS="days=30"`
produces real data and the calenderapp 公告 page is end-to-end live.
