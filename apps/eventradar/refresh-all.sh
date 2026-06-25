#!/usr/bin/env bash
# ============================================================================
# eventradar data refresh — one-shot manual data refresh script.
#
# Runs every adapter + enrich in sequence. Idempotent — safe to re-run at
# any time. Designed for interactive use: you run it when you want fresh
# data, not automated (cron is optional, see README).
#
# Usage:
#   ./refresh-all.sh           # pull all sources + enrich
#   ./refresh-all.sh --skip-events   # skip event sources, only meta + enrich
#   ./refresh-all.sh --skip-meta     # skip tushare meta refresh
# ============================================================================

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

CONDA_ENV="${CONDA_ENV:-stock}"
SKIP_EVENTS=false
SKIP_META=false

for arg in "$@"; do
    case "$arg" in
        --skip-events) SKIP_EVENTS=true ;;
        --skip-meta)   SKIP_META=true ;;
        *) echo "unknown flag: $arg"; exit 2 ;;
    esac
done

# ============================================================================
# Activate conda env
# ============================================================================
if [[ "${CONDA_DEFAULT_ENV:-}" != "$CONDA_ENV" ]]; then
    # shellcheck disable=SC1091
    source "${CONDA_PREFIX_BASE:-$HOME/miniconda3}/etc/profile.d/conda.sh"
    conda activate "$CONDA_ENV"
fi

export PYTHONPATH="$HERE/src${PYTHONPATH:+:$PYTHONPATH}"
EVENTRADAR="python -m eventradar"

# ============================================================================
# Helper: print a pretty section header
# ============================================================================
_section() {
    printf '\n\033[1;36m===== %s =====\033[0m\n' "$*"
}

# ============================================================================
# Helper: run an eventradar subcommand and check exit code
# ============================================================================
_run() {
    local label="$1"
    shift
    _section "$label"
    $EVENTRADAR "$@" || {
        printf '\033[1;31m[FAIL] %s — stopping (fix the error and re-run)\033[0m\n' "$label"
        exit 1
    }
}

# ============================================================================
# 1. Pull event sources (each adapter is independent, failure in one stops)
# ============================================================================
if ! $SKIP_EVENTS; then
    TODAY=$(date +%Y%m%d)

    # Company calendar: pull today + previous 6 calendar days. The gsdt
    # feed is a disclosures stream, not a future calendar — a trailing
    # window captures the most recent batch of company announcements.
    _run "公司动态 (gsdt)" pull company_calendar_em date="$TODAY" days=7

    # Earnings forecasts: pull the 2 most recent report periods. Companies
    # pre-announce across a window — the just-ended quarter plus the prior
    # one covers the active forecast cycle.
    _run "业绩预告 (yjyg)" pull earnings_forecast_em quarters=2

    # Macro calendar: pull the next 14 calendar days. WSC returns
    # forward-looking entries for the next ~2 weeks (LPR, CPI, PMI,
    # central-bank meetings, industry events).
    _run "宏观日历 (WSC)" pull macro_calendar_ws date="$TODAY" days=14

    # IPO pipeline from巨潮. No params — the upstream returns the current
    # 申购→中签→缴款→上市 pipeline as one batch (~440新股, expands to
    # ~1700 milestone events). Re-pulls update in place by fingerprint.
    _run "新股申购 (巨潮)" pull ipo_cninfo

    # Insider trades from 雪球 (董监高增减持). No params, no token. Returns
    # ~21000 rows rolling ~18 months back. These are disclosed-after-fact
    # events (all dates past) but strong price-precursor signals — clusters
    # of insider sells often precede drawdowns. Takes ~2s + parquet cache.
    _run "内部交易 (雪球)" pull insider_trade_xq
fi

# ============================================================================
# 2. Stock meta (industry + market cap for all 5500+ A-shares)
# ============================================================================
if ! $SKIP_META; then
    _run "股票元数据 (tushare)" refresh-stock-meta-tushare
fi

# ============================================================================
# 3. Enrichment (fills industries, leaders, importance, expected_at_end)
# ============================================================================
_run "富化事件" enrich --all

# ============================================================================
# 4. Publish the read replica (already done by enrich, but explicit is
#    safer in case the pipeline was run in a different order)
# ============================================================================
_section "发布只读副本"
$EVENTRADAR publish-replica || {
    printf '\033[1;33m[WARN] publish-replica failed (enrich already published — this is a safety re-run)\033[0m\n'
}

printf '\n\033[1;32m========================================\033[0m\n'
printf '\033[1;32m  eventradar refresh complete\033[0m\n'
printf '\033[1;32m========================================\033[0m\n'