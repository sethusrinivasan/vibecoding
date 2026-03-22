# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.4.0] — 2026-03-22

### Added
- `docs/threat_model.tc.json` — AWS Threat Composer importable JSON file covering all 22 threats,
  18 mitigations, 6 assumptions, and full mitigation links. Import at
  [awslabs.github.io/threat-composer](https://awslabs.github.io/threat-composer/).
- Threat model updated to v1.4.0: Cloudflare D1 and Worker HTTP API added to asset inventory
  and entry points; Worker input sanitisation mitigation (m-18) added; all threats use
  Threat Composer grammar (threatSource / prerequisites / threatAction / threatImpact / impactedAssets).

## [1.3.0] — 2026-03-22

### Added
- Nanosecond telemetry precision: all durations now stored as `INTEGER` nanoseconds
  (`duration_ns`) using `time.perf_counter_ns()` — eliminates sub-millisecond
  values displaying as `0.00 ms`.
- `StatsReporter.format_summary()` auto-scales display units: `ns` → `µs` → `ms` → `s`.
- `scripts/dev.sh` — POSIX-compatible convenience script wrapping all Makefile commands.

### Changed
- SQLite schema column renamed `duration_ms REAL` → `duration_ns INTEGER`.
- `TelemetryStore.record()` parameter renamed `duration_ms` → `duration_ns`.
- `StatsSummary` fields renamed from `*_ms` to `*_ns` throughout.
- `CfStatsSummary` and `CfTelemetry` updated to match nanosecond schema.
- Worker `local_server.py` and `entry.py` updated to use `perf_counter_ns()`.
- `worker/schema.sql` updated to `duration_ns INTEGER`.
- CI `pip-audit` step updated with `--disable-pip --no-deps` flags (no venv needed).

### Migration
- Delete `greeting_telemetry.db` before upgrading — the schema change is not
  backwards compatible. Run `make reset` or simply delete the file.

## [1.2.0] — 2026-03-22

### Added
- `TelemetryStore` — async SQLite telemetry store with background queue writer,
  `measure()` context manager, `record()`, `flush()`, `start()`, `stop()`, `reset()`.
- `StatsReporter` — computes min/max/mean/median/p95/p99/success_rate from DB.
- `Greeting.run()` now instruments itself and prints per-request + all-time stats.
- `make reset` target and `make run RESET=1` option to wipe telemetry DB.
- `make report` target to print historic stats without running the app.
- Cloudflare Worker in `worker/`: `entry.py`, `local_server.py`, `cf_telemetry.py`,
  `time_of_day.py` (CSS colours), `quote_provider.py`, `wrangler.toml`, `schema.sql`.
- `make worker-dev`, `make worker-test`, `make worker-deploy` targets.
- 54 worker tests in `worker/tests/test_worker.py`.
- 48 security regression tests in `tests/test_security.py` (T-01 through T-22).
- Threat model updated to v1.2.0 with T-21 (unbounded error_msg) and T-22 (db_path traversal).
- `ACKNOWLEDGEMENTS.md` — AI contribution transparency statement.
- Python 3.13 added to CI matrix and `setup.py` classifiers.

### Changed
- `Greeting.__init__()` accepts optional `telemetry` parameter.
- `requirements-dev.txt` corrected to installed versions; `pytest` removed.

## [1.1.0] — 2026-03-22

### Added
- `QuoteProvider` — RFC 865 compliant quote corpus with random selection and
  optional seeding for deterministic testing.
- `QuoteService` — RFC 865 TCP and UDP server (port 17, configurable).
  Sends one quote per connection/datagram; ignores client input per spec.
- `Greeting` now accepts an optional `quote_provider` parameter; when set,
  `run()` prints a Quote of the Day below the greeting.
- 38 new tests: unit (QuoteProvider, Greeting+quote), integration (real TCP/UDP
  sockets), and benchmark (QuoteProvider construction and get()).
- Threat model updated to v1.1.0 with 7 new threats (T-14 through T-20)
  covering the new network attack surface.
- `docs/api/quote_provider.rst` and `docs/api/quote_service.rst` Sphinx pages.

### Changed
- `Greeting.__init__()` ANSI sanitisation upgraded from single-pass non-printable
  strip to two-pass: full VT100/ANSI escape sequence removal followed by
  non-printable byte removal.
- `README.md` updated with new usage examples and project structure.

### Security
- T-19: `QuoteService` defaults to `host="127.0.0.1"` (loopback only) to
  prevent accidental public exposure.
- T-16: TCP connection handling uses daemon threads; documented connection
  rate limiting as a recommended hardening step.

## [1.0.0] — 2026-03-22

### Added
- Initial release: `TimeOfDay` enum, `Greeting` class, colourised terminal output.
- Full test suite: unit, integration, and benchmark tests.
- GitHub Actions CI/CD with multi-Python matrix and Sphinx doc build.
- OWASP threat model (v1.0.0).
- `SECURITY.md`, `CONTRIBUTING.md`, `LICENSE` (MIT).
