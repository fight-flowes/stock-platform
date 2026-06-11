CONDA_ENV ?= stock
CONDA_RUN ?= conda run -n $(CONDA_ENV)
PYTHON ?= $(CONDA_RUN) python
PYTHONPATH_ROOT ?= $(CURDIR)/src
STOCKKB ?= PYTHONPATH=$(PYTHONPATH_ROOT) $(CONDA_RUN) python -m stockrag
HOST ?= 0.0.0.0
PORT ?= 8787
PATTERN ?= **/*.md
MINIO_BUCKET ?= stockinfo

.PHONY: install import import-file import-minio-object import-minio serve show-config

install:
	$(PYTHON) -m pip install -e .

import:
	@if [ -z "$(FOLDER)" ]; then echo "Usage: make import FOLDER=/path/to/reports [PATTERN='**/*.md']"; exit 1; fi
	$(STOCKKB) import-folder "$(FOLDER)" --pattern "$(PATTERN)"

import-file:
	@if [ -z "$(FILE)" ]; then echo "Usage: make import-file FILE=/absolute/path/to/report.md"; exit 1; fi
	$(STOCKKB) import-file "$(FILE)"

import-minio-object:
	@if [ -z "$(OBJECT_NAME)" ]; then echo "Usage: make import-minio-object [MINIO_BUCKET=stockinfo] OBJECT_NAME=2026-05/05/20260507/000509_华塑控股.md"; exit 1; fi
	$(STOCKKB) import-minio-object "$(OBJECT_NAME)" --bucket "$(MINIO_BUCKET)"

import-minio:
	$(STOCKKB) import-minio-prefix --bucket "$(MINIO_BUCKET)" $(if $(PREFIX),--prefix "$(PREFIX)",)

serve:
	$(STOCKKB) serve --host $(HOST) --port $(PORT)

show-config:
	$(STOCKKB) show-config
