# Threat Model — Greeting Application

**Version:** 1.5.0
**Date:** 2026-03-22
**Methodology:** OWASP Threat Modeling Process + STRIDE
**Changelog:**
- v1.0.0 — Initial threat model (CLI greeting, colorama dependency, CI/CD pipeline)
- v1.1.0 — Added QuoteProvider and QuoteService (RFC 865) threat analysis
- v1.2.0 — Added TelemetryStore/SQLite threat analysis; Python 3.13; updated dependency versions
- v1.3.0 — Nanosecond telemetry schema (`duration_ns INTEGER`); Cloudflare Worker and `scripts/dev.sh` added
- v1.4.0 — AWS Threat Composer JSON (`threat_model.tc.json`); Cloudflare D1 and Worker HTTP API in scope
- v1.5.0 — Full STRIDE re-evaluation considering surface area, exploitability, customer data loss and privacy; assumptionLinks populated; threats reordered Critical→High→Medium→Low; new threats T-04b (unauthenticated /reset), T-18b (unauthenticated /stats), T-19 (credential leak), T-21 (XSS), T-22 (Worker DoS) formalised; Section 6 corrected (Worker IS a web app); Section 5 updated with Worker controls

**Machine-readable format:** [`threat_model.tc.json`](threat_model.tc.json) — importable into [AWS Threat Composer](https://awslabs.github.io/threat-composer/)

**References:**
- [OWASP Threat Modeling Process](https://owasp.org/www-community/Threat_Modeling_Process)
- [OWASP Top 10 CI/CD Security Risks](https://owasp.org/www-project-top-10-ci-cd-security-risks/)
- [OWASP Top 10 Web Application Security Risks](https://owasp.org/www-project-top-ten/)
- [OWASP Dependency Check](https://owasp.org/www-project-dependency-check/)
- [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- [sigstore — Python signing standard](https://www.sigstore.dev/)

---

## 1. Scope

This document covers the full attack surface of the Greeting project following the four OWASP threat modeling steps:

1. Scope the work (assets, entry points, trust levels, data flows)
2. Determine threats (STRIDE per component)
3. Determine countermeasures and mitigations
4. Assess and rank risks

STRIDE evaluation criteria applied throughout:
- **Surface area** — how many callers / paths can reach this threat?
- **Exploitability** — how easy is it to trigger without special access?
- **Customer data loss / privacy** — does exploitation expose or destroy user data?
- **Magnitude of impact** — what is the worst-case blast radius?

### 1.1 Application Overview

The Greeting application is a Python CLI tool and Cloudflare Worker HTTP API that:

- Reads the system clock via `datetime.now()` and classifies the hour into a `TimeOfDay` period
- Prints a colourised greeting string to stdout using `colorama`
- Optionally appends a Quote of the Day sourced from `QuoteProvider` (RFC 865)
- Optionally runs a `QuoteService` TCP/UDP server on port 17 (RFC 865)
- Records async telemetry (response time, faults, errors) to a local SQLite database via `TelemetryStore`
- Exposes a Cloudflare Worker HTTP API (`entry.py`) backed by a D1 database for cloud telemetry
- Reports statistical summaries (min/max/mean/p95/p99) via `StatsReporter`

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
| SQLite database | `greeting_telemetry.db` — telemetry store (`duration_ns INTEGER`) | Medium — local file, timing/error data |
| Cloudflare D1 database | Worker telemetry store (production) | Medium — cloud-hosted timing/error data |
| GitHub repository secrets | Any future tokens/keys | Critical |
| Developer workstation | Execution environment | Medium |
| Cloudflare API token | Deploy credential | Critical |

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
| EP-13 | HTTP requests to Cloudflare Worker (public internet) | Untrusted |
| EP-14 | `name` query parameter to Worker `/?name=` | Untrusted (public internet) |

### 1.4 Trust Levels

| Level | Description |
|---|---|
| 1 — Untrusted | External caller, fork PR contributor, PyPI package author, public HTTP client |
| 2 — Partially trusted | GitHub Actions runner, repository collaborator |
| 3 — Trusted | Repository owner, local developer, OS |

### 1.5 Data Flow Diagram (textual)

```
[Caller / __main__]
        |
        | name: str (EP-1)
        v
[Greeting.__init__]  ← two-pass ANSI strip + 100-char cap
        |
        | now: datetime (EP-2) or datetime.now() (EP-3)
        v
[Greeting.build()]  <---  [TimeOfDay.from_hour()]
        |
        | colorama escape + greeting string → stdout
        |
        | (optional) quote_provider.get()
        v
[QuoteProvider]  ←── quotes tuple (EP-10)

[Network Client] ──TCP/UDP──► [QuoteService]  (EP-8, EP-9)
                                     |
                               [QuoteProvider.get()]
                                     |
                               quote bytes → client socket

[Public HTTP Client] ──HTTPS──► [Cloudflare Worker]  (EP-13, EP-14)
                                        |
                                 _sanitise_name()
                                        |
                                 [CfTelemetry] → D1 INSERT
                                        |
                                 HTML/JSON response
```

---

## 2. STRIDE Threat Analysis

STRIDE categories: **S**poofing · **T**ampering · **R**epudiation ·
**I**nformation Disclosure · **D**enial of Service · **E**levation of Privilege

Threats are ordered **Critical → High → Medium → Low** within each section.
The risk register in Section 3 provides the full priority-ordered view.

---

### 2.1 Critical Threats

#### T-01 — Supply chain compromise of `colorama` (Critical)

| Field | Detail |
|---|---|
| STRIDE | Tampering, Elevation of Privilege |
| Entry point | EP-4 |
| Surface area | Every `pip install` on every developer machine and CI run |
| Exploitability | High — PyPI supply chain attacks are well-documented and increasing |
| Customer data risk | High — arbitrary code execution could exfiltrate any data in scope |
| Likelihood | Medium |
| Impact | Critical |
| Risk | Critical |

**Why these STRIDE categories:** Tampering because a malicious release injects code into a trusted build artifact. Elevation of Privilege because the attacker gains code execution in the developer's or CI runner's trusted environment without any direct access.

**Mitigations:**
- Pin dependencies with SHA-256 hashes: `pip-compile --generate-hashes`
- Enforce `--require-hashes` in CI `pip install` steps
- Run `pip-audit` on every CI build (currently implemented)
- Enable Dependabot security alerts and version-update PRs

#### T-02 — Poisoned pipeline execution (Critical)

| Field | Detail |
|---|---|
| STRIDE | Tampering, Elevation of Privilege |
| Entry point | EP-5 |
| Surface area | Any public fork PR — any GitHub user can trigger this |
| Exploitability | High — no special access needed; fork and open a PR |
| Customer data risk | High — runner compromise could expose secrets used in customer deployments |
| Likelihood | Medium |
| Impact | High |
| Risk | Critical |

**Why these STRIDE categories:** Tampering because the attacker modifies the CI workflow to inject malicious steps. Elevation of Privilege because the attacker gains runner-level code execution (with access to repository secrets) via a trusted CI trigger.

**Mitigations:**
- Require PR approval before CI runs on fork PRs (GitHub setting)
- Never print or expose secrets in workflow steps
- Use `pull_request_target` only with explicit `if` guards

---

### 2.2 High Threats

#### T-03 — Unauthenticated POST /reset (High)

| Field | Detail |
|---|---|
| STRIDE | Tampering, Repudiation |
| Entry point | EP-13 |
| Surface area | Public internet — zero prerequisites, single curl command |
| Exploitability | Trivial — no authentication required |
| Customer data risk | Medium — destroys all telemetry records; in production could erase customer usage history |
| Likelihood | High |
| Impact | Medium |
| Risk | High |

**Why these STRIDE categories:** Tampering because an unauthenticated actor destroys data via a public endpoint. Repudiation because the DELETE leaves no audit trail of who triggered the wipe — there is no way to determine the actor after the fact.

**Mitigations:**
- Add Cloudflare Access policy or shared-secret header to POST /reset
- Log the caller's CF-Connecting-IP before executing the DELETE

#### T-04 — Mutable GitHub Actions tag (High)

| Field | Detail |
|---|---|
| STRIDE | Tampering, Elevation of Privilege |
| Entry point | EP-6 |
| Surface area | Every CI run — affects all builds automatically |
| Exploitability | Medium — requires maintainer account compromise, but mutable tags are a known vector |
| Customer data risk | High — runner compromise exposes all secrets accessible to CI |
| Likelihood | Low-Medium |
| Impact | High |
| Risk | High |

**Why these STRIDE categories:** Tampering because a trusted component is replaced with malicious code. Elevation of Privilege because the attacker gains runner-level execution via a trusted channel without direct repository access.

**Mitigations:**
- Pin all third-party actions to full commit SHAs (currently implemented in ci.yml)

```yaml
# Instead of:
uses: actions/checkout@v4
# Use:
uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
```

#### T-05 — Root process for port 17 (High)

| Field | Detail |
|---|---|
| STRIDE | Elevation of Privilege |
| Entry point | EP-8, EP-9 |
| Surface area | Any TCP client that can reach port 17 on the host |
| Exploitability | Low — requires a vulnerability in the service, but developers commonly run as root for convenience |
| Customer data risk | Critical — full root compromise exposes all data on the host |
| Likelihood | Low |
| Impact | Critical |
| Risk | High |

**Why this STRIDE category:** Elevation of Privilege — running a network-facing service as root amplifies the blast radius of any vulnerability from service-level to full system compromise. The impact ceiling (root on the host) justifies High priority despite low likelihood.

**Mitigations:**
- Use `CAP_NET_BIND_SERVICE`: `setcap cap_net_bind_service=+ep python3`
- Use `authbind` or `systemd` socket activation
- Default port in `QuoteService` is configurable — use port > 1023 for development

#### T-06 — Credential leak to git history (High)

| Field | Detail |
|---|---|
| STRIDE | Information Disclosure, Repudiation |
| Entry point | EP-4 (git push) |
| Surface area | Public GitHub repo — any observer can clone and extract |
| Exploitability | Trivial once committed — git history is permanent |
| Customer data risk | High — Cloudflare account access enables D1 data wipe or exfiltration of customer telemetry |
| Likelihood | Medium |
| Impact | High |
| Risk | High |

**Why these STRIDE categories:** Information Disclosure because credentials in a public git history are immediately accessible to any observer. Repudiation because once credentials are public, there is no way to determine who accessed them or what actions were taken — the exposure is permanent and unauditable.

**Mitigations:**
- `wrangler.local.toml` is gitignored (currently implemented)
- `wrangler.toml` uses placeholder `database_id` (currently implemented)
- Recommend `git-secrets` or a pre-commit hook to block credential patterns

---

### 2.3 Medium Threats

#### T-07 — Typosquatting attack (Medium)

| Field | Detail |
|---|---|
| STRIDE | Elevation of Privilege |
| Entry point | EP-4 |
| Likelihood | Low |
| Impact | High |
| Risk | Medium |

**Why:** Attacker gains code execution by exploiting human error in package naming. Typosquatting packages are pre-positioned and wait passively — low likelihood but high impact when triggered.

**Mitigations:** Hash-pinned requirements prevent installing unintended packages. `pip-audit` in CI.

#### T-08 — Excessive CI permissions (Medium)

| Field | Detail |
|---|---|
| STRIDE | Elevation of Privilege |
| Entry point | EP-5 |
| Likelihood | Medium |
| Impact | Medium |
| Risk | Medium |

**Why:** Workflow gains more permissions than needed, enabling unintended write operations. Mitigated: `permissions: contents: read` declared at workflow and job level (currently implemented).

#### T-09 — Dependency confusion in CI (Medium)

| Field | Detail |
|---|---|
| STRIDE | Elevation of Privilege |
| Entry point | EP-4, EP-6 |
| Likelihood | Low |
| Impact | High |
| Risk | Medium |

**Why:** Attacker gains code execution in CI by exploiting pip's public-registry-first resolution order. Risk is low currently (no private packages) but increases if private packages are added.

**Mitigations:** Hash-pinned requirements. If private packages are added, use `--index-url` to point to a trusted private registry.

#### T-10 — QuoteService bound to 0.0.0.0 (Medium)

| Field | Detail |
|---|---|
| STRIDE | Information Disclosure, Denial of Service |
| Entry point | EP-8, EP-9 |
| Likelihood | Medium |
| Impact | Medium |
| Risk | Medium |

**Why these STRIDE categories:** Information Disclosure because the service becomes reachable from untrusted networks, exposing its existence and the host's network stack. Denial of Service because the expanded surface enables connection floods from the public internet. Default is safe (`127.0.0.1`) but easy to override.

**Mitigations:** Default host is `127.0.0.1` (currently implemented). Document that `0.0.0.0` requires firewall rules.

#### T-11 — XSS via name reflection in Worker HTML (Medium)

| Field | Detail |
|---|---|
| STRIDE | Tampering, Elevation of Privilege |
| Entry point | EP-14 |
| Surface area | Public internet — any browser visiting a crafted URL |
| Exploitability | Medium — `json.dumps()` escapes quotes but Unicode/HTML-entity payloads may survive |
| Customer data risk | Medium — XSS enables session hijacking and exfiltration of any data in the victim's browser session |
| Likelihood | Low-Medium |
| Impact | Medium |
| Risk | Medium |

**Why these STRIDE categories:** Tampering because the attacker injects executable content into a trusted page served to other users. Elevation of Privilege because the attacker gains JavaScript execution in the victim's browser, inheriting the victim's session context. The Worker IS a web app — XSS is firmly in scope.

**Mitigations:**
- Apply `html.escape()` to `name` before embedding in any HTML context
- Add `Content-Security-Policy` header to restrict inline script execution
- Current sanitisation (ANSI strip + non-printable filter) is necessary but not sufficient for HTML context

#### T-12 — Worker DoS via quota exhaustion (Medium)

| Field | Detail |
|---|---|
| STRIDE | Denial of Service |
| Entry point | EP-13 |
| Surface area | Public internet endpoint with no rate limiting |
| Exploitability | High — trivial to automate with any HTTP load tool |
| Customer data risk | Medium — service degradation affects all users |
| Likelihood | Medium |
| Impact | Medium |
| Risk | Medium |

**Why:** Resource exhaustion via high-volume requests consuming Cloudflare Worker CPU time and D1 write quota. Cloudflare's platform provides some inherent protection but no explicit rate limiting is configured.

**Mitigations:** Enable Cloudflare Rate Limiting rule on the Worker route.

#### T-13 — ANSI injection via name input (Medium)

| Field | Detail |
|---|---|
| STRIDE | Tampering |
| Entry point | EP-1, EP-14 |
| Likelihood | Medium |
| Impact | Low |
| Risk | Medium |

**Why:** Attacker modifies the output stream to alter what the operator sees, potentially hiding malicious activity. Broad surface area (CLI argv and HTTP query param). Mitigated: two-pass ANSI strip + printable-ASCII filter + 100-char cap (currently implemented).

#### T-14 — TCP connection exhaustion (Medium)

| Field | Detail |
|---|---|
| STRIDE | Denial of Service |
| Entry point | EP-8 |
| Likelihood | Medium |
| Impact | Medium |
| Risk | Medium |

**Why:** Resource exhaustion via unbounded connection acceptance. Trivial to exploit with netcat if the service is reachable. Gated by the loopback-only default.

**Mitigations:** Bounded `ThreadPoolExecutor` with `max_workers` in `start_tcp()`.

---

### 2.4 Low Threats

#### T-15 — Injected datetime object (Low)

Tampering via a subclassed datetime with `.hour` outside 0–23 causes `TimeOfDay.from_hour()` to silently fall through to NIGHT. Cosmetic impact only; no data loss. Recommend adding `isinstance` + range check in `from_hour()`.

#### T-16 — DoS via large name string (Low)

Denial of Service via an unbounded name string causing process-level memory exhaustion. Mitigated: 100-char cap at `Greeting.__init__()`.

#### T-17 — Log information disclosure (Low)

Information Disclosure via stack traces in server logs revealing internal paths and library versions. Mitigated: all socket errors caught and logged at WARNING level; nothing sent to clients.

#### T-18 — UDP reflection attack (Low)

Denial of Service via spoofed UDP source IP causing the server to reflect quote responses to a victim. Mitigated by default loopback binding; re-evaluate if UDP is ever exposed on a public interface.

#### T-19 — Unbounded error_msg in SQLite (Low)

Denial of Service (disk exhaustion) + Information Disclosure (stack traces in DB visible to local DB readers). Mitigated: `error_msg` truncated to 500 chars in `_MeasureContext.fail()` and `CfTelemetry.record()`.

#### T-20 — SQLite db_path traversal (Low)

Tampering via a crafted `db_path` redirecting database writes to an unintended filesystem location. Mitigated: `db_path` wrapped in `pathlib.Path()` normalising traversal sequences.

#### T-21 — Unauthenticated GET /stats (Low)

Information Disclosure — operational metrics (request counts, latency percentiles, fault rates) exposed to unauthenticated public clients. No PII or credentials exposed; aids reconnaissance only. Acceptable for a demo; in production add Cloudflare Access or a secret header.

#### T-22 — Corpus injection via custom quotes (Low)

Tampering via a custom `quotes` tuple containing ANSI escape sequences transmitted verbatim to RFC 865 clients. Mitigated: built-in corpus is static; length validated at construction.

---

## 3. Risk Register

Risks scored: **Likelihood × Impact** (each 1–3). Ordered by priority (highest first).

| # | ID | Threat | Likelihood | Impact | Score | Priority |
|---|---|---|---|---|---|---|
| 1 | T-01 | Supply chain compromise of colorama | 2 | 3 | 6 | Critical |
| 2 | T-02 | Poisoned pipeline execution (CICD-SEC-1) | 2 | 3 | 6 | Critical |
| 3 | T-03 | Unauthenticated POST /reset | 3 | 2 | 6 | High |
| 4 | T-04 | Mutable GitHub Actions tag (CICD-SEC-3) | 2 | 3 | 6 | High |
| 5 | T-05 | Root process for port 17 | 1 | 3 | 3† | High |
| 6 | T-06 | Credential leak to git history | 2 | 3 | 6 | High |
| 7 | T-07 | Typosquatting attack | 1 | 3 | 3 | Medium |
| 8 | T-08 | Excessive CI permissions (CICD-SEC-4) | 2 | 2 | 4 | Medium |
| 9 | T-09 | Dependency confusion in CI (CICD-SEC-8) | 1 | 3 | 3 | Medium |
| 10 | T-10 | QuoteService bound to 0.0.0.0 | 2 | 2 | 4 | Medium |
| 11 | T-11 | XSS via name reflection in Worker HTML | 2 | 2 | 4 | Medium |
| 12 | T-12 | Worker DoS via quota exhaustion | 2 | 2 | 4 | Medium |
| 13 | T-13 | ANSI injection via name input | 2 | 1 | 2 | Medium |
| 14 | T-14 | TCP connection exhaustion | 2 | 2 | 4 | Medium |
| 15 | T-15 | Injected datetime object | 1 | 1 | 1 | Low |
| 16 | T-16 | DoS via large name string | 1 | 1 | 1 | Low |
| 17 | T-17 | Log information disclosure | 1 | 1 | 1 | Low |
| 18 | T-18 | UDP reflection attack | 1 | 1 | 1 | Low |
| 19 | T-19 | Unbounded error_msg in SQLite | 1 | 2 | 2 | Low |
| 20 | T-20 | SQLite db_path traversal | 1 | 1 | 1 | Low |
| 21 | T-21 | Unauthenticated GET /stats | 3 | 1 | 3 | Low |
| 22 | T-22 | Corpus injection via custom quotes | 1 | 1 | 1 | Low |

† T-05 score is 3 but elevated to High due to catastrophic impact ceiling (full root compromise).

---

## 4. Recommended Mitigations — Prioritised Action Plan

### Immediate (Critical)

1. **T-01/T-02:** Add hash pinning to `requirements.txt` using `pip-compile --generate-hashes`.
2. **T-02:** Require PR approval before CI runs on fork PRs (GitHub repository setting).
3. **T-04:** All GitHub Actions already pinned to full commit SHAs (currently implemented).

### Short-term (High)

4. **T-03:** Add authentication to POST /reset — Cloudflare Access policy or shared-secret header.
5. **T-05:** Use `CAP_NET_BIND_SERVICE` or `authbind` instead of running as root for port 17.
6. **T-06:** Add `git-secrets` or a pre-commit hook to block credential patterns before commit.
7. **T-08:** `permissions: contents: read` already declared (currently implemented).

### Medium-term (Medium)

8. **T-11:** Apply `html.escape()` to `name` before embedding in HTML; add `Content-Security-Policy` header.
9. **T-12:** Enable Cloudflare Rate Limiting rule on the Worker route.
10. **T-14:** Add bounded `ThreadPoolExecutor` with `max_workers` in `QuoteService.start_tcp()`.
11. **T-10:** Document that `host='0.0.0.0'` requires firewall rules; default is safe.

---

## 5. Security Controls Already in Place

| Control | Where | Addresses |
|---|---|---|
| Dependency version pinning | `requirements.txt` | T-01 (partial) |
| `pip-audit` in CI | `ci.yml` | T-01, T-07 |
| Multi-version CI matrix | `ci.yml` | Regression detection |
| Actions pinned to full commit SHAs | `ci.yml` | T-04 (implemented) |
| `permissions: contents: read` | `ci.yml` | T-08 (implemented) |
| No secrets in codebase | Entire repo | T-06 |
| `wrangler.local.toml` gitignored | `.gitignore` | T-06 (implemented) |
| `wrangler.toml` uses placeholder `database_id` | `worker/wrangler.toml` | T-06 (implemented) |
| Two-pass ANSI strip + 100-char cap | `greeting.py`, `entry.py` | T-13 (implemented) |
| `html.escape()` on name in Worker HTML | `entry.py` | T-11 (partial — json.dumps escapes quotes) |
| No `eval` / `exec` / `subprocess` | `src/` | Prevents code injection |
| Enum-based period classification | `TimeOfDay` | Prevents arbitrary string injection |
| `colorama autoreset=True` | `greeting.py` | Limits ANSI bleed |
| RFC 865 quote length validation (≤512) | `quote_provider.py` | T-22 |
| TCP/UDP default bind to `127.0.0.1` | `quote_service.py` | T-10, T-18 (implemented) |
| Socket errors caught and logged | `quote_service.py` | T-17 (implemented) |
| Per-connection daemon threads | `quote_service.py` | Isolates client handling |
| Telemetry `error_msg` truncated to 500 chars | `telemetry.py`, `cf_telemetry.py` | T-19 (implemented) |
| SQLite path wrapped in `Path()` | `telemetry.py` | T-20 (implemented) |
| Async queue writer (background thread) | `telemetry.py` | Telemetry never blocks main flow |
| Parameterised D1 queries | `cf_telemetry.py` | SQL injection prevention |
| `SECURITY.md` | Repo root | Responsible disclosure channel |
| Security test suite | `tests/test_security.py` | Automated regression coverage |

---

## 6. Out of Scope

The following are explicitly out of scope for this threat model given the current application design:

- Authentication and authorisation for the CLI (no users, no sessions — RFC 865 is unauthenticated by design)
- TLS/encryption of the quote stream (RFC 865 is plaintext by design)
- SQLite injection via application queries (all queries use parameterised statements)
- Container / Kubernetes threats — not containerised
- Cryptographic threats — no cryptography used

**Note:** The Cloudflare Worker IS a web application. OWASP Top 10 web threats (including XSS — T-11) are explicitly **in scope** for the Worker component. The previous "not a web app" statement in v1.4.0 was incorrect and has been removed.

---

## 7. Residual Risk Acceptance

After applying all recommended mitigations, the following residual risks are accepted as tolerable:

- **T-15** (clock manipulation): Accepted. Cosmetic impact only; mitigation cost exceeds benefit.
- **T-16** (injected datetime): Accepted after adding range validation. Remaining risk is negligible.
- **T-16** (DoS via large string): Accepted after adding length cap. No system-wide impact possible.
- **T-18** (UDP amplification): Accepted for loopback-only deployments. Must be re-evaluated if `host="0.0.0.0"` is used.
- **T-19** (unbounded error_msg): Accepted after adding 500-char truncation. Residual risk is negligible.
- **T-20** (db_path traversal): Accepted. Only reachable via programmatic API; default path is hardcoded.
- **T-21** (unauthenticated /stats): Accepted for demo. Must be re-evaluated before production use.
- **T-22** (corpus injection): Accepted. Only reachable via programmatic API misuse; built-in corpus is static.

---

## 8. Review Schedule

This threat model should be reviewed and updated when:

- A new dependency is added or an existing one is upgraded
- The application gains new network interfaces, file I/O, or user authentication
- `QuoteService` is deployed on a public interface (`host="0.0.0.0"`)
- The telemetry database is moved to a shared or networked location
- The Worker is used in a context where users have authenticated sessions (XSS impact would increase)
- Any new Worker endpoints are added
