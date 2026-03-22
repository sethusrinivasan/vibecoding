#!/usr/bin/env bash
# Convenience script — wraps all key project commands.
# Usage: ./scripts/dev.sh <command> [options]
#
# Commands:
#   run [NAME=Alice] [RESET=1]                       — run the greeting CLI
#   reset                                            — wipe telemetry database
#   report                                           — print all-time telemetry stats
#   test                                             — run the full CLI test suite
#   worker-test                                      — run the Worker test suite
#   worker-dev [PORT=8787]                           — start the local Worker HTTP server
#   worker-deploy                                    — deploy to Cloudflare (needs wrangler.local.toml)
#   scale-test [DURATION=60] [CONCURRENCY=auto]      — high-concurrency scale test (duration-based)
#              [TCP=1] [TCP_PORT=19865]               — also test TCP QuoteService
#   audit                                            — scan dependencies for known CVEs
#   docs                                             — build Sphinx HTML documentation
#   clean                                            — remove generated doc artefacts

set -eu

PYTHON=python3
SRC=src
TESTS=tests

# Resolve project root (directory containing this script's parent)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cmd="${1:-help}"
[ $# -gt 0 ] && shift

case "$cmd" in

  run)
    NAME="${NAME:-World}"
    RESET="${RESET:-}"
    if [ -n "$RESET" ]; then
      echo "→ Wiping telemetry database before run..."
      $PYTHON -c "import sys; sys.path.insert(0,'$SRC'); from telemetry import TelemetryStore; TelemetryStore().reset(); print('Telemetry reset.')"
    fi
    echo "→ Running greeting CLI for: $NAME"
    $PYTHON $SRC/greeting.py "$NAME"
    ;;

  reset)
    echo "→ Wiping all telemetry data from greeting_telemetry.db..."
    $PYTHON -c "
import sys; sys.path.insert(0,'$SRC')
from telemetry import TelemetryStore
TelemetryStore().reset()
print('Telemetry database reset.')
"
    ;;

  report)
    echo "→ Querying historic telemetry stats from greeting_telemetry.db..."
    $PYTHON -c "
import sys; sys.path.insert(0,'$SRC')
from telemetry import TelemetryStore
from stats import StatsReporter
store = TelemetryStore()
r = StatsReporter(store)
print(r.format_summary(r.historic_summary('greeting'),    label='greeting (all-time)'))
print(r.format_summary(r.historic_summary('tcp_request'), label='tcp_request (all-time)'))
print(r.format_summary(r.historic_summary('udp_request'), label='udp_request (all-time)'))
"
    ;;

  test)
    echo "→ Running CLI test suite (167 tests)..."
    $PYTHON -m unittest discover -s $TESTS -v
    ;;

  scale-test)
    # ── Smart defaults derived from this machine ──────────────────────────
    # Concurrency: 4× logical CPU count, capped at 64
    # Duration:    60s always (meaningful steady-state window)
    # Both can be overridden via env vars.
    _CPUS=$($PYTHON -c "import os; print(os.cpu_count() or 4)")
    _DEFAULT_CONCURRENCY=$(( _CPUS * 4 ))
    [ "$_DEFAULT_CONCURRENCY" -gt 64 ] && _DEFAULT_CONCURRENCY=64

    DURATION="${DURATION:-60}"
    CONCURRENCY="${CONCURRENCY:-$_DEFAULT_CONCURRENCY}"
    TCP="${TCP:-}"
    TCP_PORT="${TCP_PORT:-19865}"

    echo "→ Scale test  duration=${DURATION}s  concurrency=${CONCURRENCY}  (machine: ${_CPUS} CPUs)"
    if [ -n "$TCP" ]; then
      echo "   TCP target enabled on port $TCP_PORT"
      $PYTHON tests/scale_test.py \
        --duration    "$DURATION" \
        --concurrency "$CONCURRENCY" \
        --tcp \
        --tcp-port    "$TCP_PORT"
    else
      $PYTHON tests/scale_test.py \
        --duration    "$DURATION" \
        --concurrency "$CONCURRENCY"
    fi
    ;;

  worker-test)
    echo "→ Running Worker test suite (54 tests)..."
    $PYTHON -m unittest discover -s worker/tests -v
    ;;

  worker-dev)
    PORT="${PORT:-8787}"
    echo "→ Starting local Worker HTTP server on http://127.0.0.1:$PORT"
    echo "   Endpoints: GET /, GET /?name=Alice, GET /quote, GET /stats, POST /reset"
    echo "   Press Ctrl+C to stop."
    $PYTHON worker/src/local_server.py "$PORT"
    ;;

  worker-deploy)
    CONFIG="worker/wrangler.local.toml"
    if [ ! -f "$CONFIG" ]; then
      echo "✗ $CONFIG not found."
      echo "  Copy worker/wrangler.toml to worker/wrangler.local.toml and fill in your database_id."
      echo "  This file is gitignored — it holds your real Cloudflare resource IDs."
      exit 1
    fi
    echo "→ Deploying Cloudflare Worker using $CONFIG ..."
    echo "   (CLOUDFLARE_API_TOKEN must be set in your environment)"
    wrangler deploy --config "$CONFIG"
    ;;

  audit)
    echo "→ Scanning dependencies for known CVEs (pip-audit)..."
    pip-audit -r requirements.txt --disable-pip --no-deps
    ;;

  docs)
    echo "→ Building Sphinx HTML documentation..."
    sphinx-build -b html docs docs/_build/html
    echo "   Docs built → docs/_build/html/index.html"
    ;;

  clean)
    echo "→ Removing generated doc artefacts (docs/_build)..."
    rm -rf docs/_build
    echo "   Done."
    ;;

  help|*)
    echo "Usage: ./scripts/dev.sh <command> [NAME=...] [RESET=1] [PORT=...] [DURATION=...] [CONCURRENCY=...] [TCP=1]"
    echo ""
    echo "  run [NAME=Alice] [RESET=1]                    run the greeting CLI"
    echo "  reset                                         wipe telemetry database"
    echo "  report                                        print all-time telemetry stats"
    echo "  test                                          run CLI test suite"
    echo "  worker-test                                   run Worker test suite"
    echo "  worker-dev [PORT=8787]                        start local Worker HTTP server"
    echo "  worker-deploy                                 deploy to Cloudflare Workers"
    echo "                                                  requires: worker/wrangler.local.toml (gitignored)"
    echo "                                                  requires: CLOUDFLARE_API_TOKEN env var"
    echo "  scale-test [DURATION=60] [CONCURRENCY=auto]   duration-based scale test"
    echo "             [TCP=1] [TCP_PORT=19865]            also test TCP QuoteService"
    echo "             (concurrency defaults to 4 × CPU count, max 64)"
    echo "  audit                                         scan deps for CVEs"
    echo "  docs                                          build Sphinx HTML docs"
    echo "  clean                                         remove generated doc artefacts"
    ;;

esac
