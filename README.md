# stock-platform

`stock-platform` is the shared product root for the stock research workspace.

Current direction:

- keep `stockkb` as an independent structured event knowledge service
- keep `calenderapp` as the user-facing application service
- manage both inside one product workspace and converge scripts, docs, and config over time

## Why this root exists

This root is meant to become the product-level home for:

- application services
- shared docs
- shared infra/runtime scripts
- future cross-service tests and conventions

It now contains working copies of both services under `apps/`, while the
original source directories are kept untouched as backup baselines.

## Target layout

```text
stock-platform/
├── apps/
│   ├── calenderapp/
│   └── stockkb/
├── docs/
├── infra/
└── scripts/
```

## Current service mapping

Primary working copies under this root:

- `apps/calenderapp`
- `apps/stockkb`

Original backup directories kept unchanged:

- `/home/leisaihua/workspace/stock_info/calenderappv5.1`
- `/home/leisaihua/workspace/knowledge_base/stockrag` (`stockkb` 的历史备份基线)

## Recommended migration order

1. Normalize path-dependent scripts so they stop relying on hard-coded absolute paths.
2. Keep runtime orchestration inside `stock-platform/scripts/`.
3. Continue cleaning docs and env templates that still mention old paths.
4. Add shared integration checks for the `calenderapp -> stockkb` flow.

## Root scripts

- `bash scripts/dev-up.sh`
- `bash scripts/dev-down.sh`
- `bash scripts/dev-status.sh`
- `bash scripts/dev-check.sh`

`dev-up.sh` starts the stock-platform working copies. By default it brings up
the `stockkb` API only, which is enough for the `calenderapp -> stockkb`
event dialog flow.

## Notes

- `calenderapp` inside `apps/` was copied from the current working tree so the
  recent stock knowledge-base integration fixes are preserved.
- `stockkb` is still consumed as an upstream HTTP service and remains
  independently runnable inside `apps/stockkb`.
