#!/usr/bin/env bash
# Convenience wrapper around the CLI for cron / systemd / interactive use.
#
# Usage:
#   ./manage.sh show-config
#   ./manage.sh serve
#   ./manage.sh pull company_calendar_em days=30
#   ./manage.sh publish-replica
#
# Designed to be cron-safe: activates the conda env so the cron environment
# (which has next to no PATH) still finds python/akshare/duckdb.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

CONDA_ENV="${CONDA_ENV:-stock}"

# Activate conda only when not already in the right env. Keeps interactive
# usage from doing redundant `conda activate` calls.
if [[ "${CONDA_DEFAULT_ENV:-}" != "$CONDA_ENV" ]]; then
  # shellcheck disable=SC1091
  source "${CONDA_PREFIX_BASE:-$HOME/miniconda3}/etc/profile.d/conda.sh"
  conda activate "$CONDA_ENV"
fi

export PYTHONPATH="$HERE/src${PYTHONPATH:+:$PYTHONPATH}"

exec python -m eventradar "$@"
