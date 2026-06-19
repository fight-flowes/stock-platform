CONDA_ENV ?= stock
CONDA_RUN ?= conda run -n $(CONDA_ENV)
PYTHON ?= $(CONDA_RUN) python
PYTHONPATH_ROOT ?= $(CURDIR)/src
EVENTRADAR ?= PYTHONPATH=$(PYTHONPATH_ROOT) $(CONDA_RUN) python -m eventradar
HOST ?= 0.0.0.0
PORT ?= 8050

.PHONY: install install-adapters serve show-config list-adapters pull publish-replica clean-data

install:
	$(PYTHON) -m pip install -e .

install-adapters:
	# Pulls akshare + pyarrow once you start writing real adapters.
	$(PYTHON) -m pip install -e ".[adapters]"

show-config:
	$(EVENTRADAR) show-config

list-adapters:
	$(EVENTRADAR) list-adapters

# Usage: make pull ADAPTER=company_calendar_em ARGS="days=30"
pull:
	@if [ -z "$(ADAPTER)" ]; then \
	  echo "Usage: make pull ADAPTER=<name> [ARGS='key=value key=value']"; \
	  exit 1; \
	fi
	$(EVENTRADAR) pull "$(ADAPTER)" $(ARGS)

publish-replica:
	$(EVENTRADAR) publish-replica

serve:
	$(EVENTRADAR) serve --host $(HOST) --port $(PORT)

clean-data:
	# Wipes the local DuckDB files. Cron job will rebuild on next run.
	rm -f data/eventradar.duckdb data/eventradar.read.duckdb data/eventradar.read.duckdb.tmp
