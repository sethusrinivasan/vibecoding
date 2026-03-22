PYTHON   = python3
SPHINX   = sphinx-build
SRC      = src
DOCS_SRC = docs
DOCS_OUT = docs/_build/html
TESTS    = tests

.PHONY: all run reset report test scale-test audit docs clean worker-dev worker-deploy worker-test

## Default target: run tests then build docs
all: test docs

## Run the application (with Quote of the Day + telemetry)
## Usage: make run
##        make run NAME="Alice"
##        make run RESET=1          — wipe telemetry DB first, then run
##        make run NAME="Alice" RESET=1
run:
	$(if $(RESET),$(PYTHON) -c "\
import sys; sys.path.insert(0,'$(SRC)'); \
from telemetry import TelemetryStore; \
TelemetryStore().reset(); \
print('Telemetry database reset.');",)
	$(PYTHON) $(SRC)/greeting.py $(if $(NAME),$(NAME),)

## Wipe all telemetry data without running the app
## Usage: make reset
reset:
	$(PYTHON) -c "\
import sys; sys.path.insert(0,'$(SRC)'); \
from telemetry import TelemetryStore; \
TelemetryStore().reset(); \
print('Telemetry database reset.');"

## Print historic telemetry summary from the local SQLite database
report:
	$(PYTHON) -c "\
import sys; sys.path.insert(0,'$(SRC)'); \
from telemetry import TelemetryStore; \
from stats import StatsReporter; \
store = TelemetryStore(); \
r = StatsReporter(store); \
print(r.format_summary(r.historic_summary('greeting'),      label='greeting (all-time)')); \
print(r.format_summary(r.historic_summary('tcp_request'),   label='tcp_request (all-time)')); \
print(r.format_summary(r.historic_summary('udp_request'),   label='udp_request (all-time)')); \
"

## Run the full test suite
test:
	$(PYTHON) -m unittest discover -s $(TESTS) -v

## High-concurrency scale test — runs each target for DURATION seconds
## Concurrency defaults to 4 × CPU count (capped at 64) when not specified.
## Usage: make scale-test
##        make scale-test DURATION=60 CONCURRENCY=50
##        make scale-test TCP=1 TCP_PORT=19865     — also test TCP QuoteService
##        make scale-test DURATION=120 CONCURRENCY=100 TCP=1
_SCALE_CPUS    := $(shell $(PYTHON) -c "import os; print(os.cpu_count() or 4)")
_SCALE_DEFAULT := $(shell $(PYTHON) -c "c=$(shell $(PYTHON) -c "import os; print(os.cpu_count() or 4)")*4; print(min(c,64))")

scale-test:
	$(PYTHON) tests/scale_test.py \
		--duration    $(if $(DURATION),$(DURATION),60) \
		--concurrency $(if $(CONCURRENCY),$(CONCURRENCY),$(_SCALE_DEFAULT)) \
		$(if $(TCP),--tcp,) \
		$(if $(TCP_PORT),--tcp-port $(TCP_PORT),)

## Audit dependencies for known CVEs
## Uses --disable-pip --no-deps to avoid venv creation (not available on this system)
audit:
	pip-audit -r requirements.txt --disable-pip --no-deps

## Build HTML documentation via Sphinx
docs:
	$(SPHINX) -b html $(DOCS_SRC) $(DOCS_OUT)
	@echo "Docs built → $(DOCS_OUT)/index.html"

## Remove generated doc artefacts
clean:
	rm -rf $(DOCS_OUT)

## -------------------------------------------------------------------------
## Cloudflare Worker targets
## -------------------------------------------------------------------------

## Run the Worker locally (no Node/pywrangler needed)
## Usage: make worker-dev
##        make worker-dev PORT=9000
worker-dev:
	$(PYTHON) worker/src/local_server.py $(if $(PORT),$(PORT),8787)

## Run worker unit tests
worker-test:
	$(PYTHON) -m unittest discover -s worker/tests -v

## Deploy to Cloudflare (requires pywrangler + wrangler auth)
## Uses wrangler.local.toml (gitignored) which holds the real database_id.
## Copy worker/wrangler.local.toml, fill in your database_id, then run.
## Usage: make worker-deploy
worker-deploy:
	cd worker && uv run pywrangler deploy --config wrangler.local.toml
