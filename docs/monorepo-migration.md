# Monorepo Migration Notes

## Objective

Adopt a single product root at:

`/home/leisaihua/workspace/stock_info/stock-platform`

while preserving the current two-service architecture:

- `calenderapp`: user-facing platform
- `stockkb`: structured event knowledge service

## Migration status

Phase 1 is in progress:

- copied `calenderappv5.1` to `apps/calenderapp`
- copied the legacy `stockrag` workspace to `apps/stockkb`
- started replacing hard-coded runtime paths in the copied projects
- added root-level lifecycle scripts under `scripts/`

## What should change first

Inside the copied working versions, update code and scripts that assume fixed
paths.

Priority items:

- `calenderappv5.1/manage.sh`
- cron/backup scripts under `calenderappv5.1/scripts/`
- docs that reference old absolute paths
- any env vars that point directly at old service locations

## What should not change immediately

- do not merge Flask and FastAPI into one runtime
- do not merge PostgreSQL and DuckDB responsibilities
- do not remove the HTTP boundary between `calenderapp` and `stockkb`

## Suggested end state

```text
stock-platform/
├── apps/
│   ├── calenderapp/
│   │   ├── backend/
│   │   ├── frontend/
│   │   ├── docs/
│   │   └── scripts/
│   └── stockkb/
│       ├── src/
│       ├── docs/
│       ├── scripts/
│       └── tests/
├── docs/
│   ├── architecture.md
│   └── runbooks.md
├── infra/
│   ├── env/
│   └── compose/
└── scripts/
    ├── dev-up.sh
    ├── dev-down.sh
    └── dev-status.sh
```

## Integration contract to preserve

The following flow must continue to work during and after migration:

1. `calenderapp` frontend opens stock event dialog
2. `calenderapp` backend calls `/api/stockkb/*`
3. proxy forwards to `stockkb` `/kb/*`
4. `stockkb` returns structured report/event payloads

## Naming recommendation

Use stable service directory names once migrated:

- `apps/calenderapp`
- `apps/stockkb`

Avoid version numbers in directory names. Versioning belongs in git tags,
release notes, and app metadata rather than long-lived filesystem paths.
