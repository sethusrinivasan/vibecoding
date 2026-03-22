# Threat Model — Greeting Application

**Version:** 1.3.0
**Date:** 2026-03-22
**Methodology:** OWASP Threat Modeling Process + STRIDE
**Changelog:**
- v1.0.0 — Initial threat model (CLI greeting, colorama dependency, CI/CD pipeline)
- v1.1.0 — Added QuoteProvider and QuoteService (RFC 865) threat analysis (T-14–T-20)
- v1.2.0 — Added TelemetryStore/SQLite threat analysis (T-21–T-22); updated Python version to 3.13; updated dependency versions (sphinx 8.2.3, sphinx-rtd-theme 3.0.2); added security test coverage notes
- v1.3.0 — Updated T-21/T-22 to reflect nanosecond schema (`duration_ns INTEGER`); added Cloudflare Worker and `scripts/dev.sh` to asset inventory; updated CI audit step
**References:**
- [OWASP Threat Modeling Process](https://owasp.org/www-community/Threat_Modeling_Process)
- [OWASP Top 10 CI/CD Security Risks](https://owasp.org/www-project-top-10-ci-cd-security-risks/)
- [OWASP Dependency Check](https://owasp.org/www-project-dependency-check/)
- [OWASP Source Code Analysis Tools](https://owasp.org/www-community/Source_Code_Analysis_Tools)

---

## 1. Scope

This document covers the full attack surface of the Greeting project, structured
following the four OWASP threat modeling steps:

1. Scope the work (assets, entry points, trust levels, data flows)
2. Determine threats (STRIDE per component)
3. Determine countermeasures and mitigations
4. Assess and rank risks (DREAD-style qualitative scoring)

### 1.1 Application Overview

The Greeting application is a Python CLI tool that:

- Reads the system clock via `datetime.now()`
- Classifies the hour into a `TimeOfDay` period (enum)
- Prints a colourised greeting string to stdout using `colorama`
- Optionally appends a Quote of the Day sourced from `QuoteProvider` (RFC 865)
- Optionally runs a `QuoteService` TCP/UDP server on port 17 (RFC 865)
- Records async telemetry (response time, faults, errors) to a local SQLite database via `TelemetryStore`
- Reports statistical summaries (min/max/mean/p95/p99) via `StatsReporter`

The `QuoteService` component introduces **network connectivity** and `TelemetryStore`
introduces **local file I/O** — both are significant expansions of the attack surface
compared to v1.0.0.

### 1.2 Assets

| Asset | Description | Sensitivity |
|---|---|---|
| Source code | `src/` — application logic | Medium — integrity critical |
| Worker code | `worker/src/` — Cloudflare Worker HTTP API | Medium — integrity critical |
| CI/CD pipeline | `.github/workflows/ci.yml` | High — controls what ships |
| PyPI dependencies | `colorama`, `pytest` | High — supply chain vector |
| System clock | `datetime.now()` | Low — read-only, local |
| Terminal stdout | Output stream | Low — display only |
| Quote corpus | Built-in strings in `quote_provider.py` | Low — static data |
| TCP/UDP port 17 (or custom) | `QuoteService` network socket | Medium — network exposure |
| SQLite database | `greeting_telemetry.db` — telemetry store (`duration_ns INTEGER`) | Medium — local file, contains timing/error data |
| Cloudflare D1 database | Worker telemetry store (production) | Medium — cloud-hosted timing/error data |
| GitHub repository secrets | Any future tokens/keys | Critical |
| Developer workstation | Execution environment | Medium |

### 1.3 Entry Points

| ID | Entry Point | Trust Level |
|---|---|---|
| EP-1 | `name` parameter to `Greeting.__init__()` | Untrusted (caller-supplied) |
| EP-2 | `now` parameter to `Greeting.build()` / `Greeting.run()` | Untrusted (caller-supplied) |
| EP-3 | System clock (`datetime.now()`) | Trusted (OS-controlled) |
| EP-4 | `requirements.txt` / `setup.py` dependency resolution | Untrusted (PyPI network) |
| EP-5 | GitHub Actions workflow triggers (push, pull_request) | Partially trusted |
| EP-6 | Third-party GitHub Actions (`actions/checkout`, `actions/setup-python`) | Partially trusted |
| EP-7 | Terminal environment (TERM, COLORTERM env vars read by colorama) | Trusted (local OS) |
| EP-8 | TCP connections to `QuoteService` | Untrusted (any network client) |
| EP-9 | UDP datagrams to `QuoteService` | Untrusted (any network client) |
| EP-10 | `quotes` parameter to `QuoteProvider.__init__()` | Untrusted (caller-supplied) |
| EP-11 | `db_path` parameter to `TelemetryStore.__init__()` | Trusted (developer-supplied) |
| EP-12 | SQLite database file on disk | Trusted (local filesystem) |

### 1.4 Trust Levels

| Level | Description |
|---|---|
| 1 — Untrusted | External caller, fork PR contributor, PyPI package author |
| 2 — Partially trusted | GitHub Actions runner, repository collaborator |
| 3 — Trusted | Repository owner, local developer, OS |

### 1.5 Data Flow Diagram (textual)

```
[Caller / __main__]
        |
        | name: str (EP-1)
        v
[Greeting.__init__]
        |
        | now: datetime (EP-2) or datetime.now() (EP-3)
        v
[Greeting.build()]  <---  [TimeOfDay.from_hour()]
        |                         |
        | formatted string        | period enum member
        v                         v
[Greeting.run()]  <---  [TimeOfDay.color / .salutation]
        |
        | colorama escape + greeting string → stdout
        |
        | (optional) quote_provider.get()
        v
[QuoteProvider]  ←── quotes tuple (EP-10)
        |
        | quote string → stdout
        v
    [stdout / terminal]

[Network Client] ──TCP/UDP──► [QuoteService]  (EP-8, EP-9)
                                     |
                               [QuoteProvider.get()]
                                     |
                               quote bytes → client socket
```

---

## 2. STRIDE Threat Analysis

STRIDE categories: **S**poofing · **T**ampering · **R**epudiation ·
**I**nformation Disclosure · **D**enial of Service · **E**levation of Privilege

---

### 2.1 Component: `Greeting.__init__(name)`

#### T-01 — Tampering via unsanitised `name` input

| Field | Detail |
|---|---|
| STRIDE | Tampering, Information Disclosure |
| Entry point | EP-1 |
| Description | `name` is interpolated directly into the output string with no validation or sanitisation. A caller passing ANSI escape sequences, terminal control codes, or excessively long strings can manipulate terminal rendering, overwrite previous output lines, or cause a buffer-related display issue. |
| Example | `Greeting("\033[2J\033[H").run()` clears the terminal before printing. |
| Likelihood | Medium (requires a caller to pass malicious input) |
| Impact | Low (stdout only; no persistence, no privilege) |
| Risk | Low–Medium |

**Mitigations:**
- Strip or reject non-printable characters from `name` before use.
- Enforce a maximum length (e.g. 100 characters).
- Use `colorama.strip_ansi()` or a regex to sanitise the value at construction time.

```python
import re

_SAFE_NAME = re.compile(r'[^\x20-\x7E]')  # printable ASCII only

class Greeting:
    def __init__(self, name: str = "World"):
        name = _SAFE_NAME.sub('', name)[:100]
        self.name = name or "World"
```

---

### 2.2 Component: `Greeting.build(now)` / `Greeting.run(now)`

#### T-02 — Tampering via injected `datetime` object

| Field | Detail |
|---|---|
| STRIDE | Tampering |
| Entry point | EP-2 |
| Description | The `now` parameter accepts any `datetime` object. A caller can pass a datetime with an out-of-range `.hour` attribute (e.g. a subclassed or mocked datetime where `hour` returns a value outside 0–23). `TimeOfDay.from_hour()` has no guard against this and would fall through to `NIGHT` silently. |
| Likelihood | Low (requires deliberate misuse or a buggy mock) |
| Impact | Low (incorrect greeting period displayed) |
| Risk | Low |

**Mitigations:**
- Validate `hour` is in range 0–23 inside `TimeOfDay.from_hour()`.

```python
@classmethod
def from_hour(cls, hour: int) -> "TimeOfDay":
    if not isinstance(hour, int) or not (0 <= hour <= 23):
        raise ValueError(f"hour must be an integer 0–23, got {hour!r}")
    ...
```

#### T-03 — Denial of Service via pathological `name` string

| Field | Detail |
|---|---|
| STRIDE | Denial of Service |
| Entry point | EP-1 |
| Description | An unbounded `name` string (e.g. 100 MB) causes excessive memory allocation during f-string construction and stdout write. |
| Likelihood | Low |
| Impact | Low (process-level; no system-wide effect) |
| Risk | Low |

**Mitigations:** Enforce `name` length cap at construction (see T-01 mitigation).

---

### 2.3 Component: System Clock (`datetime.now()`)

#### T-04 — Spoofing via system clock manipulation

| Field | Detail |
|---|---|
| STRIDE | Spoofing, Tampering |
| Entry point | EP-3 |
| Description | An attacker with local OS access can manipulate the system clock (e.g. `date` command, NTP poisoning) to cause the application to display an incorrect time-of-day greeting and colour. |
| Likelihood | Low (requires local OS privilege) |
| Impact | Low (cosmetic output only) |
| Risk | Low |

**Mitigations:** Not applicable at application level for a local CLI tool. If time accuracy is critical in a future networked context, use a trusted NTP source and validate clock skew.

---

### 2.4 Component: `colorama` (Third-Party Dependency)

#### T-05 — Supply chain compromise of `colorama`

| Field | Detail |
|---|---|
| STRIDE | Tampering, Elevation of Privilege |
| Entry point | EP-4 |
| Description | `colorama` is a widely used PyPI package. A compromised release (typosquatting, maintainer account takeover, or malicious update) could execute arbitrary code at import time or during `init()`. The current `requirements.txt` pins the version but does not pin a hash. |
| Likelihood | Low–Medium (supply chain attacks on PyPI are increasing) |
| Impact | Critical (arbitrary code execution in the developer or CI environment) |
| Risk | Medium–High |

**Mitigations:**
- Pin dependencies with SHA-256 hashes using `pip-compile --generate-hashes`.
- Use `pip install --require-hashes -r requirements.txt` in CI.
- Regularly audit with `pip-audit` or `safety`.
- Consider using a private package mirror or artifact proxy (e.g. Artifactory) for production pipelines.

Example `requirements.txt` with hash pinning:
```
colorama==0.4.6 \
    --hash=sha256:08695f5cb7ed6e0531a20572697297d14b... \
    --hash=sha256:4f1d9991f5acc0ca119f9d443620b77f...
```

#### T-06 — Typosquatting attack

| Field | Detail |
|---|---|
| STRIDE | Tampering |
| Entry point | EP-4 |
| Description | A developer mistyping `colorama` (e.g. `colourama`, `coloramma`) installs a malicious package. |
| Likelihood | Low |
| Impact | Critical |
| Risk | Medium |

**Mitigations:** Use `pip install --dry-run` before installing new packages. Verify package names against PyPI directly. Enable GitHub Dependabot alerts.

---

### 2.5 Component: GitHub Actions CI/CD Pipeline

This section maps to the [OWASP Top 10 CI/CD Security Risks](https://owasp.org/www-project-top-10-ci-cd-security-risks/).

#### T-07 — Poisoned Pipeline Execution (CICD-SEC-1)

| Field | Detail |
|---|---|
| STRIDE | Tampering, Elevation of Privilege |
| Entry point | EP-5 |
| Description | The workflow triggers on `pull_request` from any fork. A malicious contributor can submit a PR that modifies the workflow file or injects commands into steps, executing arbitrary code on the CI runner with access to any repository secrets. |
| Likelihood | Medium (public repo, open PRs) |
| Impact | High (runner compromise, secret exfiltration) |
| Risk | High |

**Mitigations:**
- Use `pull_request_target` only when necessary and with explicit `if` guards.
- Never print or expose secrets in workflow steps.
- Restrict which branches can trigger workflows.
- Require PR approval before CI runs on first-time contributors (GitHub setting: "Require approval for first-time contributors").

#### T-08 — Unpinned Third-Party Actions (CICD-SEC-3)

| Field | Detail |
|---|---|
| STRIDE | Tampering |
| Entry point | EP-6 |
| Description | The workflow uses `actions/checkout@v4` and `actions/setup-python@v5` by tag. Tags are mutable — a compromised maintainer can push malicious code to the same tag, silently affecting all pipelines using it. |
| Likelihood | Low–Medium |
| Impact | High (arbitrary code on runner) |
| Risk | Medium–High |

**Mitigations:**
- Pin all third-party actions to a full commit SHA instead of a tag.

```yaml
# Instead of:
uses: actions/checkout@v4

# Use:
uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
```

#### T-09 — Insufficient Pipeline Permissions (CICD-SEC-4)

| Field | Detail |
|---|---|
| STRIDE | Elevation of Privilege |
| Entry point | EP-5 |
| Description | The current workflow does not declare `permissions`. GitHub Actions defaults to `read` for most scopes but `write` for `contents` on some event types, giving the workflow more privilege than needed. |
| Likelihood | Medium |
| Impact | Medium (unintended write access to repo) |
| Risk | Medium |

**Mitigations:**
- Explicitly declare minimal permissions at the workflow and job level.

```yaml
permissions:
  contents: read

jobs:
  test:
    permissions:
      contents: read
```

#### T-10 — Dependency confusion / artifact poisoning (CICD-SEC-8)

| Field | Detail |
|---|---|
| STRIDE | Tampering |
| Entry point | EP-4, EP-6 |
| Description | `pip install` in CI resolves packages from PyPI without hash verification. A dependency confusion attack substitutes a private package name with a malicious public one. |
| Likelihood | Low (no private packages currently) |
| Impact | High |
| Risk | Medium |

**Mitigations:**
- Use `--require-hashes` in CI (see T-05).
- If private packages are ever added, use `--index-url` to point to a trusted private registry.

#### T-11 — Secret leakage via workflow logs

| Field | Detail |
|---|---|
| STRIDE | Information Disclosure |
| Entry point | EP-5 |
| Description | If secrets are ever added to the repository (e.g. PyPI publish token), a misconfigured `run:` step or a dependency that prints environment variables could leak them in public CI logs. |
| Likelihood | Low (no secrets currently) |
| Impact | Critical (if secrets are added later) |
| Risk | Medium (future risk) |

**Mitigations:**
- Never `echo` environment variables in workflow steps.
- Use GitHub's secret masking — store all tokens in `Settings > Secrets`.
- Audit workflow logs after any change that introduces new `env:` variables.
- Use OIDC-based keyless authentication (e.g. for PyPI publishing via `trusted publisher`) to avoid storing long-lived tokens entirely.

---

### 2.6 Component: Source Code Repository

#### T-12 — Repudiation — no audit trail for dependency changes

| Field | Detail |
|---|---|
| STRIDE | Repudiation |
| Entry point | EP-4 |
| Description | Changes to `requirements.txt` or `setup.py` are not automatically reviewed or audited beyond standard git history. A compromised contributor could silently add a malicious dependency. |
| Likelihood | Low |
| Impact | High |
| Risk | Medium |

**Mitigations:**
- Require signed commits (`git commit -S`) and enforce via branch protection.
- Enable Dependabot version updates and security alerts.
- Require at least one code review approval for any PR touching dependency files.

#### T-13 — Tampering — unsigned releases

| Field | Detail |
|---|---|
| STRIDE | Tampering |
| Entry point | Source distribution |
| Description | If the package is ever published to PyPI, unsigned releases allow an attacker who gains PyPI account access to publish a malicious version without detection. |
| Likelihood | Low |
| Impact | High (downstream consumers affected) |
| Risk | Medium |

**Mitigations:**
- Use [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/) (OIDC) for publishing — eliminates long-lived API tokens.
- Sign release artifacts with `sigstore` (the Python ecosystem standard as of 2023).
- Enable 2FA on the PyPI account.

---

### 2.7 Component: `QuoteProvider`

#### T-14 — Corpus injection via custom `quotes` parameter

| Field | Detail |
|---|---|
| STRIDE | Tampering, Information Disclosure |
| Entry point | EP-10 |
| Description | A caller supplying a custom `quotes` tuple could inject quotes containing ANSI escape sequences or control characters. These are sent verbatim over the TCP/UDP socket and printed to the terminal, potentially manipulating terminal state on the receiving end. |
| Likelihood | Low (requires deliberate misuse) |
| Impact | Low–Medium (terminal manipulation on client) |
| Risk | Low–Medium |

**Mitigations:**
- `QuoteProvider` already validates length (≤512 chars) at construction.
- Consider adding the same ANSI-stripping logic used in `Greeting` to `QuoteProvider` for custom corpora.
- The built-in corpus is static and reviewed — no runtime injection possible.

#### T-15 — Denial of Service via oversized custom corpus

| Field | Detail |
|---|---|
| STRIDE | Denial of Service |
| Entry point | EP-10 |
| Description | A caller passing a very large tuple (e.g. millions of quotes) causes excessive memory allocation. |
| Likelihood | Low |
| Impact | Low (process-level) |
| Risk | Low |

**Mitigations:** Add an optional `max_corpus_size` guard if the provider is ever exposed to untrusted callers.

---

### 2.8 Component: `QuoteService` (RFC 865 TCP/UDP Server)

The `QuoteService` introduces network connectivity — the most significant attack surface expansion in v1.1.0.

#### T-16 — Denial of Service via TCP connection exhaustion

| Field | Detail |
|---|---|
| STRIDE | Denial of Service |
| Entry point | EP-8 |
| Description | An attacker can open many simultaneous TCP connections, exhausting the server's file descriptor limit or thread pool. Each connection spawns a daemon thread; unbounded thread creation can exhaust OS resources. |
| Likelihood | Medium (trivial to exploit with `nc` or a script) |
| Impact | Medium (service unavailable; no data loss) |
| Risk | Medium–High |

**Mitigations:**
- Implement a connection rate limiter or semaphore to cap concurrent connections.
- Use a thread pool (`concurrent.futures.ThreadPoolExecutor`) with a bounded `max_workers`.
- Add a per-IP connection rate limit.
- Consider running behind a reverse proxy (e.g. `inetd`, `systemd` socket activation) for production use.

#### T-17 — Information disclosure via error messages

| Field | Detail |
|---|---|
| STRIDE | Information Disclosure |
| Entry point | EP-8, EP-9 |
| Description | Unhandled exceptions in `_handle_tcp` or the UDP loop could propagate stack traces to logs, revealing internal paths, Python version, or library versions to an attacker with log access. |
| Likelihood | Low |
| Impact | Low |
| Risk | Low |

**Mitigations:** All socket errors are caught and logged at `WARNING` level without sending details to the client. Stack traces are not transmitted over the network.

#### T-18 — Binding to `0.0.0.0` exposes service to all interfaces

| Field | Detail |
|---|---|
| STRIDE | Elevation of Privilege, Information Disclosure |
| Entry point | EP-8, EP-9 |
| Description | The `host` parameter defaults to `"127.0.0.1"` (loopback only). If a caller passes `host="0.0.0.0"`, the service becomes reachable from any network interface, including public ones. RFC 865 was designed for trusted internal networks. |
| Likelihood | Medium (misconfiguration risk) |
| Impact | Medium (quote content exposed to internet; DoS surface expanded) |
| Risk | Medium |

**Mitigations:**
- Default is already `"127.0.0.1"` — safe out of the box.
- Document clearly that `"0.0.0.0"` should only be used in trusted network environments.
- Add a firewall rule recommendation in deployment docs.

#### T-19 — Port 17 requires root — privilege escalation risk

| Field | Detail |
|---|---|
| STRIDE | Elevation of Privilege |
| Entry point | EP-8, EP-9 |
| Description | RFC 865 specifies port 17, which requires root/administrator privileges on Linux/macOS. Running the service as root to bind port 17 dramatically increases the blast radius of any vulnerability in the service. |
| Likelihood | Medium (developers may run as root for convenience) |
| Impact | High (root process compromise) |
| Risk | High |

**Mitigations:**
- Default port in `QuoteService` is configurable — use port > 1023 (e.g. `1717`) for development.
- If port 17 is required in production, use `CAP_NET_BIND_SERVICE` capability instead of running as root: `setcap cap_net_bind_service=+ep python3`.
- Alternatively, use `authbind` or `systemd` socket activation to bind the privileged port without root.
- Document this risk prominently.

#### T-20 — UDP amplification / reflection attack

| Field | Detail |
|---|---|
| STRIDE | Denial of Service |
| Entry point | EP-9 |
| Description | An attacker can spoof the source IP of a UDP datagram to point to a victim. The server sends the quote response to the spoofed address, amplifying traffic toward the victim. The amplification factor is small (quote ≤512 bytes vs. empty trigger datagram) but non-zero. |
| Likelihood | Low (requires network-level IP spoofing; mitigated by BCP38) |
| Impact | Low–Medium |
| Risk | Low–Medium |

**Mitigations:**
- Bind to `127.0.0.1` by default (loopback cannot be spoofed from external networks).
- If exposing on a public interface, implement rate limiting per source IP.
- Document that the UDP service should not be exposed on public internet interfaces.

---

### 2.9 Component: `TelemetryStore` (SQLite async writer)

The `TelemetryStore` introduces local file I/O via a background thread writing to a SQLite database.

#### T-21 — Unbounded error message storage in SQLite

| Field | Detail |
|---|---|
| STRIDE | Denial of Service, Information Disclosure |
| Entry point | EP-12 |
| Description | If `_MeasureContext.fail()` or `record()` is called with an unbounded error string (e.g. a full stack trace or a multi-MB payload), the SQLite `error_msg` column could grow without limit, consuming disk space and potentially leaking sensitive internal state to anyone with read access to the database file. |
| Likelihood | Low (requires a bug or deliberate misuse in calling code) |
| Impact | Low–Medium (disk exhaustion; local info disclosure) |
| Risk | Low–Medium |

**Mitigations:**
- `_MeasureContext.fail()` already truncates messages to 500 characters.
- `record()` callers should similarly truncate before passing `error_msg`.
- The database file should have filesystem permissions set to `600` (owner read/write only) in production deployments.

#### T-22 — SQLite database path traversal / injection

| Field | Detail |
|---|---|
| STRIDE | Tampering, Information Disclosure |
| Entry point | EP-11 |
| Description | The `db_path` parameter to `TelemetryStore.__init__()` is passed directly to `sqlite3.connect()`. If a caller supplies a path like `../../etc/passwd` or a URI with special SQLite flags (e.g. `file:mem?mode=memory`), unexpected behaviour could result. The schema uses `duration_ns INTEGER` (nanoseconds); any external tool reading the DB should be aware of this unit. |
| Likelihood | Very Low (only reachable via programmatic API; no external trigger) |
| Impact | Low (local process only; no privilege escalation) |
| Risk | Low |

**Mitigations:**
- `db_path` is wrapped in `Path()` at construction, normalising the path.
- The default path is hardcoded relative to the project root.
- If `TelemetryStore` is ever exposed to untrusted configuration (e.g. environment variable), validate the path is within an expected directory before use.

---

## 3. Risk Register

Risks are scored using a qualitative model: **Likelihood × Impact** (each 1–3).

| ID | Threat | Likelihood | Impact | Risk Score | Priority |
|---|---|---|---|---|---|
| T-05 | Supply chain compromise of colorama | 2 | 3 | 6 | Critical |
| T-07 | Poisoned pipeline execution | 2 | 3 | 6 | Critical |
| T-08 | Unpinned third-party Actions | 2 | 3 | 6 | Critical |
| T-19 | Port 17 root privilege escalation | 2 | 3 | 6 | Critical |
| T-09 | Insufficient pipeline permissions | 2 | 2 | 4 | High |
| T-16 | TCP connection exhaustion DoS | 2 | 2 | 4 | High |
| T-10 | Dependency confusion in CI | 1 | 3 | 3 | High |
| T-11 | Secret leakage via logs | 1 | 3 | 3 | High |
| T-12 | No audit trail for dep changes | 1 | 3 | 3 | High |
| T-13 | Unsigned releases | 1 | 3 | 3 | High |
| T-18 | Binding to 0.0.0.0 | 2 | 2 | 4 | High |
| T-06 | Typosquatting | 1 | 3 | 3 | Medium |
| T-20 | UDP amplification | 1 | 2 | 2 | Medium |
| T-14 | Corpus injection via custom quotes | 1 | 2 | 2 | Medium |
| T-01 | Unsanitised name input | 2 | 1 | 2 | Medium |
| T-17 | Error message information disclosure | 1 | 1 | 1 | Low |
| T-02 | Injected datetime object | 1 | 1 | 1 | Low |
| T-03 | DoS via large name string | 1 | 1 | 1 | Low |
| T-04 | System clock manipulation | 1 | 1 | 1 | Low |
| T-15 | DoS via oversized corpus | 1 | 1 | 1 | Low |
| T-21 | Unbounded error_msg in SQLite | 1 | 2 | 2 | Low–Medium |
| T-22 | SQLite db_path traversal | 1 | 1 | 1 | Low |

---

## 4. Recommended Mitigations — Prioritised Action Plan

### Immediate (Critical)

1. Pin all GitHub Actions to full commit SHAs (T-08).
2. Add `permissions: contents: read` to the workflow (T-09).
3. Add hash pinning to `requirements.txt` using `pip-compile --generate-hashes` (T-05, T-10).

### Short-term (High)

4. Add `pip-audit` as a CI step to scan for known CVEs in dependencies (T-05, T-06).
5. Enable Dependabot security alerts and version updates on the repository (T-12).
6. Require PR review approval before CI runs on fork PRs (T-07).
7. Add input sanitisation to `Greeting.__init__()` (T-01).
8. Add `hour` range validation to `TimeOfDay.from_hour()` (T-02).

### Medium-term (Medium)

9. Require signed commits and enforce via branch protection rules (T-12).
10. If publishing to PyPI, configure Trusted Publishers and sign with `sigstore` (T-13).
11. Add a `SECURITY.md` policy (already added) and a vulnerability disclosure process.

---

## 5. Security Controls Already in Place

| Control | Where | Addresses |
|---|---|---|
| Dependency version pinning | `requirements.txt` | T-05 (partial) |
| Multi-version CI matrix | `ci.yml` | Regression detection |
| No secrets in codebase | Entire repo | T-11 |
| No network calls at runtime | `src/` | Reduces attack surface |
| No file I/O at runtime | `src/` | Reduces attack surface |
| No `eval` / `exec` / `subprocess` | `src/` | Prevents code injection |
| Enum-based period classification | `TimeOfDay` | Prevents arbitrary string injection into period logic |
| `colorama autoreset=True` | `greeting.py` | Limits ANSI bleed to adjacent terminal output |
| ANSI escape sequence stripping | `greeting.py` | Prevents terminal injection via name (T-01) |
| RFC 865 quote length validation (≤512) | `quote_provider.py` | Prevents oversized payloads (T-15) |
| TCP/UDP default bind to `127.0.0.1` | `quote_service.py` | Prevents external exposure by default (T-18, T-20) |
| Socket errors caught and logged | `quote_service.py` | Prevents stack trace leakage to clients (T-17) |
| Per-connection daemon threads | `quote_service.py` | Isolates client handling; daemon=True ensures clean shutdown |
| Telemetry error_msg truncated to 500 chars | `telemetry.py` | Prevents unbounded storage (T-21) |
| SQLite path wrapped in `Path()` | `telemetry.py` | Normalises db_path; mitigates traversal (T-22) |
| Async queue writer (background thread) | `telemetry.py` | Telemetry never blocks main flow |
| MIT licence | `LICENSE` | Clear legal boundary for consumers |
| `SECURITY.md` | Repo root | Responsible disclosure channel |
| Security test suite | `tests/test_security.py` | Automated regression coverage for T-01–T-22 |

---

## 6. Out of Scope

The following are explicitly out of scope for this threat model given the current
application design, but should be revisited if the application evolves:

- Authentication and authorisation (no users, no sessions — RFC 865 is unauthenticated by design)
- TLS/encryption of the quote stream (RFC 865 is plaintext by design)
- SQLite injection via application queries (all queries use parameterised statements; no user-controlled SQL)
- Web application threats (OWASP Top 10 web) — not a web app
- Container / Kubernetes threats — not containerised
- Cryptographic threats — no cryptography used

---

## 7. Residual Risk Acceptance

After applying all recommended mitigations, the following residual risks are
accepted as tolerable given the application's limited scope and impact surface:

- T-04 (clock manipulation): Accepted. Cosmetic impact only; mitigation cost exceeds benefit.
- T-02 (injected datetime): Accepted after adding range validation. Remaining risk is negligible.
- T-03 (DoS via large string): Accepted after adding length cap. No system-wide impact possible.
- T-15 (DoS via oversized corpus): Accepted. Only reachable via programmatic API misuse; no external trigger.
- T-17 (error message disclosure): Accepted. Errors are logged server-side only; nothing is sent to clients.
- T-20 (UDP amplification): Accepted for loopback-only deployments. Must be re-evaluated if `host="0.0.0.0"` is used.
- T-21 (unbounded error_msg): Accepted after adding 500-char truncation. Residual risk is negligible.
- T-22 (db_path traversal): Accepted. Only reachable via programmatic API; default path is hardcoded.

---

## 8. Review Schedule

This threat model should be reviewed and updated when:

- A new dependency is added or an existing one is upgraded
- The application gains new network interfaces, file I/O, or user authentication
- `QuoteService` is deployed on a public interface (`host="0.0.0.0"`)
- The telemetry database is moved to a shared or networked location
- The CI/CD pipeline is modified
- A security vulnerability is reported or discovered
- At minimum, once per release cycle
