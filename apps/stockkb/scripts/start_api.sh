#!/usr/bin/env bash
set -euo pipefail

CONDA_BASE="${CONDA_BASE:-${HOME}/miniconda3}"
STOCKKB_CONDA_ENV="${STOCKKB_CONDA_ENV:-${STOCKRAG_CONDA_ENV:-stock}}"
CONDA_ENV="${CONDA_ENV:-${STOCKKB_CONDA_ENV}}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-${API_PORT:-8040}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHONPATH_ROOT="${PROJECT_ROOT}/src"

if [[ ! -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]]; then
  echo "conda.sh not found: ${CONDA_BASE}/etc/profile.d/conda.sh"
  exit 1
fi

source "${CONDA_BASE}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV}"

export PYTHONPATH="${PYTHONPATH_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

exec python -m stockrag serve --host "${HOST}" --port "${PORT}"
