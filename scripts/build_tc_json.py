#!/usr/bin/env python3
"""Generate docs/threat_model.tc.json — AWS Threat Composer importable format."""
import json, pathlib

OUT = pathlib.Path("docs/threat_model.tc.json")

A1 = "f069ba5f-505c-477a-ac6e-9966b45d38ac"
A2 = "43c54cd3-6c2a-4dec-9e39-484f2c6c06c8"
A3 = "f47ea747-a2a2-4bf9-8335-5cb3abf0b3da"
A4 = "2458585c-8d5c-41d4-b1c0-160e7d8d55af"
A5 = "a0883d44-2638-4f87-a5a5-d412c8f9b80c"
A6 = "df4bb2f8-331a-42e5-9a17-5c3bee82bd6d"

assumptions = [
    {"id": A1, "numericId": 1, "displayOrder": 1,
     "content": "QuoteService is deployed on a developer workstation only, bound to 127.0.0.1. It is never intentionally exposed to the public internet.",
     "tags": ["Network","QuoteService","Deployment"], "metadata": []},
    {"id": A2, "numericId": 2, "displayOrder": 2,
     "content": "The Cloudflare Worker is the only internet-facing component. All HTTP requests to the Worker are considered untrusted.",
     "tags": ["Cloudflare","Worker","Trust-Boundary"], "metadata": []},
    {"id": A3, "numericId": 3, "displayOrder": 3,
     "content": "The SQLite telemetry database (greeting_telemetry.db) is a local file accessible only to the OS user running the CLI. It contains timing and error data — no PII.",
     "tags": ["SQLite","Telemetry","Data-Classification"], "metadata": []},
    {"id": A4, "numericId": 4, "displayOrder": 4,
     "content": "No secrets (Cloudflare API token, D1 database_id) are committed to the repository. wrangler.local.toml is gitignored. Credentials are passed via environment variables at deploy time.",
     "tags": ["Secrets","Git","Cloudflare"], "metadata": []},
    {"id": A5, "numericId": 5, "displayOrder": 5,
     "content": "The Worker /reset and /stats endpoints are unauthenticated by design for this demo. In a production deployment they would require authentication.",
     "tags": ["Worker","Authentication","Scope"], "metadata": []},
    {"id": A6, "numericId": 6, "displayOrder": 6,
     "content": "GitHub Actions runners are ephemeral and isolated. The workflow uses pinned commit SHAs for all third-party actions and declares permissions: contents: read.",
     "tags": ["CI-CD","GitHub-Actions","Least-Privilege"], "metadata": []},
]

# Mitigation IDs
M1  = "d02ae732-dc06-4c14-98b9-72b366480435"
M2  = "d6de56e7-311b-4575-9458-b7367a7bf311"
M3  = "447d5188-d3a3-4db0-9e63-5faccdc65ac5"
M4  = "da5c66b2-a4ac-4480-969a-b543385572b7"
M5  = "66c5bef0-868a-41be-90ad-c4106f0fb4c7"
M6  = "40737722-0bc7-45b0-a619-01d055a906ef"
M7  = "d324acde-a6bc-4871-a0d1-974c284810cb"
M8  = "a875f12e-f88f-495d-bd17-a5575fbbf462"
M9  = "ed84e30a-1408-48a8-b1fb-bb250ea649d5"
M10 = "f59bfc3f-d8a0-4c14-bb1d-3e98859ce2a5"
M11 = "3d57cbab-0a1b-4bd2-b2d2-3bc15e2e0cd7"
M12 = "d1d2d435-d978-4988-8f01-de78ad807682"
M13 = "29a96004-ab51-40b7-94da-72ea870acda3"
M14 = "e140177a-ce32-4bb5-9709-52e09a25fbb5"
M15 = "3cdf5c0c-17d6-4832-99ba-33f9066a90ba"
M16 = "2268844b-b35d-4716-834b-e42d85903b17"
M17 = "6b5a7958-2f16-44d7-be62-880a65b0f0b0"
M18 = "8aac83f6-5242-4beb-8fef-657c0bf901c7"
M19 = "b3c7f821-9d4e-4a1f-bc23-7e8d5f6a2c91"

mitigations = [
    {"id": M1,  "numericId": 1,  "displayOrder": 1,
     "content": "Two-pass input sanitisation on name: (1) strip full ANSI/VT100 escape sequences via regex, (2) remove non-printable bytes, (3) truncate to 100 characters. Applied in both Greeting.__init__() and Worker _sanitise_name(). Fallback to 'World' if result is empty.",
     "tags": ["Input-Validation","Implemented","T-01","T-03"], "metadata": []},
    {"id": M2,  "numericId": 2,  "displayOrder": 2,
     "content": "Add explicit range validation in TimeOfDay.from_hour(): assert isinstance(hour, int) and 0 <= hour <= 23, raise ValueError otherwise.",
     "tags": ["Input-Validation","Recommended","T-02"], "metadata": []},
    {"id": M3,  "numericId": 3,  "displayOrder": 3,
     "content": "Add authentication (e.g. a shared secret header or Cloudflare Access policy) to the Worker POST /reset endpoint to prevent unauthenticated telemetry wipes from the public internet.",
     "tags": ["Authentication","Recommended","T-04"], "metadata": []},
    {"id": M4,  "numericId": 4,  "displayOrder": 4,
     "content": "Pin PyPI dependencies with SHA-256 hashes using pip-compile --generate-hashes and enforce --require-hashes in CI pip install steps.",
     "tags": ["Supply-Chain","Recommended","T-05","T-06","T-10"], "metadata": []},
    {"id": M5,  "numericId": 5,  "displayOrder": 5,
     "content": "Run pip-audit on every CI build (currently implemented: pip-audit -r requirements.txt --disable-pip --no-deps) to detect known CVEs in dependencies before they reach production.",
     "tags": ["Supply-Chain","Implemented","T-05","T-06"], "metadata": []},
    {"id": M6,  "numericId": 6,  "displayOrder": 6,
     "content": "All GitHub Actions third-party actions are pinned to full commit SHAs (currently implemented in ci.yml). Prevents mutable-tag substitution attacks.",
     "tags": ["CI-CD","Implemented","T-07"], "metadata": []},
    {"id": M7,  "numericId": 7,  "displayOrder": 7,
     "content": "Workflow declares permissions: contents: read at both workflow and job level (currently implemented). Prevents unintended write access to repository contents.",
     "tags": ["CI-CD","Implemented","T-08"], "metadata": []},
    {"id": M8,  "numericId": 8,  "displayOrder": 8,
     "content": "Enable GitHub branch protection on main: require PR review approval before merge, require CI to pass, prevent force-push. Reduces poisoned pipeline execution risk from fork PRs.",
     "tags": ["CI-CD","Recommended","T-09"], "metadata": []},
    {"id": M9,  "numericId": 9,  "displayOrder": 9,
     "content": "QuoteService defaults to host='127.0.0.1' (loopback only). Document clearly that host='0.0.0.0' must never be used without a firewall rule restricting access to trusted networks.",
     "tags": ["Network","Implemented","T-11","T-12"], "metadata": []},
    {"id": M10, "numericId": 10, "displayOrder": 10,
     "content": "Implement a bounded thread pool (ThreadPoolExecutor with max_workers) in QuoteService.start_tcp() to cap concurrent connections and prevent file-descriptor exhaustion.",
     "tags": ["DoS","Recommended","T-13"], "metadata": []},
    {"id": M11, "numericId": 11, "displayOrder": 11,
     "content": "Use CAP_NET_BIND_SERVICE capability (setcap cap_net_bind_service=+ep python3) or systemd socket activation to bind port 17 without running the process as root.",
     "tags": ["Privilege","Recommended","T-14"], "metadata": []},
    {"id": M12, "numericId": 12, "displayOrder": 12,
     "content": "All socket errors in QuoteService are caught and logged at WARNING level server-side only (currently implemented). Stack traces are never transmitted to clients.",
     "tags": ["Information-Disclosure","Implemented","T-15"], "metadata": []},
    {"id": M13, "numericId": 13, "displayOrder": 13,
     "content": "error_msg is truncated to 500 characters before writing to SQLite (currently implemented in _MeasureContext.fail() and CfTelemetry.record()). Prevents unbounded disk growth from verbose error payloads.",
     "tags": ["SQLite","Implemented","T-16"], "metadata": []},
    {"id": M14, "numericId": 14, "displayOrder": 14,
     "content": "db_path is wrapped in pathlib.Path() at TelemetryStore construction, normalising traversal sequences. Default path is hardcoded relative to project root.",
     "tags": ["SQLite","Implemented","T-17"], "metadata": []},
    {"id": M15, "numericId": 15, "displayOrder": 15,
     "content": "All D1 queries in CfTelemetry use parameterised statements via db.prepare().bind() (currently implemented). No string interpolation of user-controlled values into SQL.",
     "tags": ["SQL-Injection","Implemented","T-18"], "metadata": []},
    {"id": M16, "numericId": 16, "displayOrder": 16,
     "content": "Store Cloudflare API token and D1 database_id in gitignored wrangler.local.toml and environment variables only. Never commit credentials to the repository (currently enforced via .gitignore).",
     "tags": ["Secrets","Implemented","T-19"], "metadata": []},
    {"id": M17, "numericId": 17, "displayOrder": 17,
     "content": "QuoteProvider validates every quote at construction time: length <= 512 chars (RFC 865 limit), non-empty corpus. Raises ValueError immediately on violation (currently implemented).",
     "tags": ["Input-Validation","Implemented","T-20"], "metadata": []},
    {"id": M18, "numericId": 18, "displayOrder": 18,
     "content": "Enable Dependabot security alerts and automated version-update PRs on the GitHub repository to surface newly disclosed CVEs in colorama and other dependencies between manual audit runs.",
     "tags": ["Supply-Chain","Recommended","T-05","T-06"], "metadata": []},
    {"id": M19, "numericId": 19, "displayOrder": 19,
     "content": "Apply html.escape() to the name parameter before embedding it in any HTML context in the Worker response, in addition to the existing ANSI/non-printable sanitisation. Add Content-Security-Policy header to restrict inline script execution.",
     "tags": ["XSS","Recommended","T-21"], "metadata": []},
]

# Threat IDs — ordered Critical → High → Medium → Low
# Critical
T05 = "c3ea3d79-994e-4e88-9910-ede209e77da8"  # supply chain colorama
T07 = "275751b2-f3ce-445c-86e6-b244152c0fa4"  # poisoned pipeline
# High
T04 = "a6bdd8bf-838b-4d48-b86a-603a8daa0f8b"  # unauthenticated /reset
T08 = "1a85a617-68f7-4aaa-bb71-85c3e0411e42"  # mutable Actions tag
T13 = "91bbff65-afc7-43cc-ad9c-40230223b775"  # root for port 17
T19 = "cd632493-6169-4c47-8159-3d6b884d0f9b"  # credential leak to git
# Medium
T06 = "900c20a5-db67-4b72-8210-bcc872ed8596"  # typosquatting
T09 = "d6d30c8d-308d-4e57-9ed5-bac2cffb319d"  # excessive CI permissions
T10 = "1932fe98-fe93-4ec2-a84b-79847abed77a"  # dependency confusion
T11 = "0a5cd4a5-0f60-401e-a0e4-c057e2807589"  # 0.0.0.0 exposure
T21 = "ee12e801-d0ca-43b1-8434-6a1f992a3728"  # XSS via name
T22 = "5181e9b3-b05f-4689-adf6-3e9c4803258d"  # Worker DoS quota
T01 = "640f6502-da6f-49d2-82a4-f85b3632a265"  # ANSI injection name
T12 = "050c6692-20ea-41fd-8d54-f68e8d9d7820"  # TCP connection exhaustion
# Low
T02 = "0ee7dc62-cfbf-4a99-ab41-01086788c75e"  # datetime injection
T03 = "4e815c23-6b2b-4569-9040-b1439cb66f32"  # large name DoS
T14 = "c2af25a7-8cb4-4bcb-8122-14de77344436"  # log info disclosure
T15 = "fa551525-5932-4d76-9afe-27575b1760c2"  # UDP reflection
T16 = "aa97ee68-d4e9-4a88-b67d-e61c20978d91"  # SQLite error_msg
T17 = "59b86efe-4db2-4c9c-b69c-99074f644de3"  # db_path traversal
T18 = "f0cb25d1-c98b-4ff4-b4f8-c48c07b18b2d"  # unauthenticated /stats
T20 = "df900016-58f7-43b1-b536-c556d3e9fb57"  # corpus injection

def md(*pairs):
    return [{"key": k, "value": v} for k, v in pairs]

threats = [
  # ── 1. CRITICAL: Supply chain compromise of colorama ─────────────────────
  {
    "id": T05, "numericId": 1, "displayOrder": 1,
    "statement": "A supply chain attacker with the ability to publish a malicious release of colorama to PyPI, exploiting a compromised maintainer account or typosquatting, can cause arbitrary code execution at import time on any developer workstation or CI runner that installs the package, which leads to full environment compromise, negatively impacting source code integrity, CI/CD pipeline, and any customer data accessible from those environments.",
    "threatSource": "supply chain attacker with the ability to publish a malicious release of colorama to PyPI",
    "prerequisites": "exploiting a compromised PyPI maintainer account or a typosquatted package name accepted by pip",
    "threatAction": "cause arbitrary code execution at import time on developer workstations and CI runners",
    "threatImpact": "full developer environment or CI runner compromise; potential exfiltration of source code, secrets, and any customer data in scope",
    "impactedAssets": ["developer workstation","CI/CD pipeline","source code","GitHub repository secrets","customer data in scope"],
    "tags": ["STRIDE-Elevation-of-Privilege","STRIDE-Tampering","Priority-Critical","Supply-Chain","CI-CD"],
    "metadata": md(
      ("custom:STRIDE", "Elevation of Privilege (code execution in trusted env) + Tampering (malicious code injected into trusted build). Surface: every pip install on every dev machine and CI run. Exploitability: HIGH — PyPI supply chain attacks are well-documented and increasing."),
      ("custom:Likelihood", "Medium — colorama is widely depended upon; maintainer account compromise is a realistic threat vector"),
      ("custom:Impact", "Critical — arbitrary code execution with developer or CI runner privileges; potential customer data exfiltration if secrets are in scope"),
      ("custom:Priority", "Critical — Likelihood(2) × Impact(3) = 6. Partial mitigation: pip-audit in CI; recommended: hash-pinned requirements + Dependabot"),
    )
  },
  # ── 2. CRITICAL: Poisoned pipeline execution ─────────────────────────────
  {
    "id": T07, "numericId": 2, "displayOrder": 2,
    "statement": "A malicious fork contributor with the ability to submit a pull request to the repository, injecting shell commands into a workflow step or modifying ci.yml, can execute arbitrary code on the GitHub Actions runner with access to repository secrets, which leads to secret exfiltration and potential repository compromise, negatively impacting CI/CD pipeline integrity and any downstream customer deployments.",
    "threatSource": "malicious fork contributor with the ability to submit a pull request",
    "prerequisites": "injecting shell commands into a workflow step or modifying .github/workflows/ci.yml in the PR",
    "threatAction": "execute arbitrary code on the GitHub Actions runner and exfiltrate repository secrets",
    "threatImpact": "CI runner compromise, repository secret exfiltration, potential backdoor in shipped artifacts",
    "impactedAssets": ["CI/CD pipeline","GitHub repository secrets","GITHUB_TOKEN","source code","shipped artifacts"],
    "tags": ["STRIDE-Elevation-of-Privilege","STRIDE-Tampering","Priority-Critical","CI-CD","OWASP-CICD-SEC-1"],
    "metadata": md(
      ("custom:STRIDE", "Elevation of Privilege (runner-level code execution) + Tampering (malicious code in CI artifacts). Surface: any public fork PR. Exploitability: HIGH — any GitHub user can fork and open a PR; no special access needed."),
      ("custom:Likelihood", "Medium — public repo; any GitHub user can fork and open a PR"),
      ("custom:Impact", "High — runner compromise, secret exfiltration, potential backdoor in shipped artifacts"),
      ("custom:Priority", "Critical — Likelihood(2) × Impact(3) = 6. Mitigated: actions pinned to SHAs, permissions:contents:read; recommended: require PR approval before CI runs on fork PRs"),
    )
  },
  # ── 3. HIGH: Unauthenticated /reset ──────────────────────────────────────
  {
    "id": T04, "numericId": 3, "displayOrder": 3,
    "statement": "An unauthenticated HTTP client with access to the public Worker URL, sending a POST to /reset, can delete all telemetry rows from the D1 database, which leads to permanent loss of historic performance and error data, negatively impacting observability, incident investigation, and any customer-facing SLA reporting that depends on this data.",
    "threatSource": "unauthenticated HTTP client with access to the public Worker URL",
    "prerequisites": "sending a POST request to https://greeting-worker.cancun.workers.dev/reset — no credentials required",
    "threatAction": "delete all telemetry rows from the D1 database",
    "threatImpact": "permanent loss of historic performance, error, and fault telemetry; loss of audit trail for who wiped data",
    "impactedAssets": ["D1 telemetry database","observability data","incident investigation capability","SLA reporting data"],
    "tags": ["STRIDE-Tampering","STRIDE-Repudiation","Priority-High","Worker","Authentication","Recommended"],
    "metadata": md(
      ("custom:STRIDE", "Tampering (unauthenticated actor destroys data via public endpoint) + Repudiation (no audit trail of who triggered the wipe — the DELETE leaves no record of the actor). Surface: public internet, zero prerequisites. Exploitability: TRIVIAL — a single curl command."),
      ("custom:Likelihood", "High — endpoint is publicly reachable with no authentication; trivial to exploit"),
      ("custom:Impact", "Medium — permanent data loss; no code execution; no PII exposure in this demo, but in production this could erase customer usage records"),
      ("custom:Priority", "High — Likelihood(3) × Impact(2) = 6. No mitigation currently in place; recommend Cloudflare Access policy or shared-secret header on /reset"),
    )
  },
  # ── 4. HIGH: Mutable Actions tag ─────────────────────────────────────────
  {
    "id": T08, "numericId": 4, "displayOrder": 4,
    "statement": "A compromised GitHub Actions maintainer with write access to a mutable version tag, pushing malicious code to the same tag used in ci.yml, can silently replace a trusted action with a backdoored version, which leads to arbitrary code execution on every subsequent CI run, negatively impacting all builds and any secrets or customer data accessible to the runner.",
    "threatSource": "compromised GitHub Actions maintainer with write access to a mutable version tag",
    "prerequisites": "pushing malicious code to the same tag (e.g. v4) referenced in ci.yml",
    "threatAction": "silently replace a trusted action with a backdoored version that executes on every CI run",
    "threatImpact": "arbitrary code execution on every CI runner build; potential exfiltration of all runner-accessible secrets",
    "impactedAssets": ["CI/CD pipeline","GitHub Actions runner","all secrets accessible to the runner","shipped artifacts"],
    "tags": ["STRIDE-Tampering","STRIDE-Elevation-of-Privilege","Priority-High","CI-CD","Supply-Chain","OWASP-CICD-SEC-3","Implemented"],
    "metadata": md(
      ("custom:STRIDE", "Tampering (trusted component replaced with malicious code) + Elevation of Privilege (attacker gains runner-level execution via a trusted channel). Surface: every CI run. Exploitability: MEDIUM — requires maintainer account compromise, but mutable tags are a well-known attack vector."),
      ("custom:Likelihood", "Low-Medium — requires maintainer account compromise; mutable tags are a known risk"),
      ("custom:Impact", "High — arbitrary code execution on CI runner; all runner-accessible secrets at risk"),
      ("custom:Priority", "High — Likelihood(2) × Impact(3) = 6. Mitigated: all actions pinned to full commit SHAs in ci.yml (currently implemented)"),
    )
  },
  # ── 5. HIGH: Root for port 17 ─────────────────────────────────────────────
  {
    "id": T13, "numericId": 5, "displayOrder": 5,
    "statement": "A developer running QuoteService as root in order to bind the RFC 865 canonical port 17, with a memory-safety or logic vulnerability in the service, can allow an attacker to achieve root-level code execution on the host, which leads to full system compromise, negatively impacting the entire host operating system and any customer data stored on it.",
    "threatSource": "developer running QuoteService as root to bind the RFC 865 canonical port 17",
    "prerequisites": "a memory-safety or logic vulnerability in QuoteService or its Python runtime being exploited by a connected client",
    "threatAction": "allow an attacker to achieve root-level code execution on the host",
    "threatImpact": "full host system compromise; all data on the host at risk including any customer data",
    "impactedAssets": ["host operating system","all running processes","filesystem","credentials","customer data on host"],
    "tags": ["STRIDE-Elevation-of-Privilege","Priority-High","QuoteService","Privilege"],
    "metadata": md(
      ("custom:STRIDE", "Elevation of Privilege — running a network-facing service as root amplifies the blast radius of any vulnerability from service-level to full system compromise. Surface: any TCP client that can reach port 17. Exploitability: LOW individually but HIGH consequence if exploited."),
      ("custom:Likelihood", "Low — requires a vulnerability in the service; but developers commonly run as root for convenience"),
      ("custom:Impact", "Critical — full root compromise of the host; all customer data on the machine at risk"),
      ("custom:Priority", "High — Likelihood(1) × Impact(3) = 3, elevated to High due to catastrophic impact ceiling. Recommended: use CAP_NET_BIND_SERVICE or authbind; default port is configurable"),
    )
  },
  # ── 6. HIGH: Credential leak to git ──────────────────────────────────────
  {
    "id": T19, "numericId": 6, "displayOrder": 6,
    "statement": "A developer or automated tool with access to the repository, accidentally committing the wrangler.local.toml file containing the real Cloudflare D1 database_id and API token, can expose live infrastructure credentials in the public git history, which leads to unauthorised access to the Cloudflare account and D1 database, negatively impacting the confidentiality and integrity of the production environment and any customer telemetry data stored in D1.",
    "threatSource": "developer or automated tool with access to the repository",
    "prerequisites": "accidentally committing wrangler.local.toml or a file containing CLOUDFLARE_API_TOKEN before the .gitignore rule takes effect",
    "threatAction": "expose live Cloudflare credentials in the public git history permanently",
    "threatImpact": "unauthorised access to the Cloudflare account and D1 database; customer telemetry data exfiltration or destruction; no revocation possible without credential rotation",
    "impactedAssets": ["Cloudflare API token","D1 database","Cloudflare account","production telemetry data","customer usage records"],
    "tags": ["STRIDE-Information-Disclosure","STRIDE-Repudiation","Priority-High","Secrets","Cloudflare","Implemented"],
    "metadata": md(
      ("custom:STRIDE", "Information Disclosure (credentials in public git history accessible to any observer) + Repudiation (once public, there is no way to determine who accessed the credentials or what actions were taken — git history is permanent). Surface: public GitHub repo. Exploitability: TRIVIAL once committed — any observer can clone and extract."),
      ("custom:Likelihood", "Medium — a common developer mistake; git history is permanent even after deletion from HEAD"),
      ("custom:Impact", "High — full Cloudflare account access; D1 data wipe or exfiltration; customer telemetry records at risk"),
      ("custom:Priority", "High — Likelihood(2) × Impact(3) = 6. Mitigated: wrangler.local.toml gitignored; wrangler.toml uses placeholder ID (currently implemented); recommend git-secrets or pre-commit hook"),
    )
  },
  # ── 7. MEDIUM: Typosquatting ──────────────────────────────────────────────
  {
    "id": T06, "numericId": 7, "displayOrder": 7,
    "statement": "A malicious actor with knowledge of common package name typos, registering a package named 'colourama' or 'coloramma' on PyPI, can cause a developer who miskeys the package name to install malicious code, which leads to arbitrary code execution on the developer workstation, negatively impacting source code and credential security.",
    "threatSource": "malicious actor with knowledge of common package name typos",
    "prerequisites": "registering a typosquatted package name on PyPI before the developer installs it",
    "threatAction": "cause a developer who miskeys the package name to install and execute malicious code",
    "threatImpact": "arbitrary code execution on the developer workstation; source code and local credentials at risk",
    "impactedAssets": ["developer workstation","source code","local credentials"],
    "tags": ["STRIDE-Elevation-of-Privilege","Priority-Medium","Supply-Chain"],
    "metadata": md(
      ("custom:STRIDE", "Elevation of Privilege — attacker gains code execution by exploiting human error in package naming. Surface: developer install commands. Exploitability: LOW — requires a developer to mistype the package name, but typosquatting packages are pre-positioned and wait passively."),
      ("custom:Likelihood", "Low — requires a developer to mistype the package name during a new install"),
      ("custom:Impact", "High — arbitrary code execution on developer machine; local credentials and source code at risk"),
      ("custom:Priority", "Medium — Likelihood(1) × Impact(3) = 3. Mitigated by pip-audit; recommended: hash-pinned requirements prevent installing unintended packages"),
    )
  },
  # ── 8. MEDIUM: Excessive CI permissions ──────────────────────────────────
  {
    "id": T09, "numericId": 8, "displayOrder": 8,
    "statement": "A GitHub Actions workflow with excessive default permissions, triggered by a pull_request event from a fork, can write to repository contents or create issues without explicit authorisation, which leads to unintended repository modifications, negatively impacting source code integrity.",
    "threatSource": "GitHub Actions workflow with excessive default permissions",
    "prerequisites": "triggered by a pull_request event without explicit permissions declaration",
    "threatAction": "write to repository contents or create issues without explicit authorisation",
    "threatImpact": "unintended repository modifications; potential injection of malicious code into main branch",
    "impactedAssets": ["GitHub repository","source code","issue tracker"],
    "tags": ["STRIDE-Elevation-of-Privilege","Priority-Medium","CI-CD","Implemented"],
    "metadata": md(
      ("custom:STRIDE", "Elevation of Privilege — workflow gains more permissions than needed, enabling unintended write operations. Surface: every CI run triggered by a PR. Exploitability: MEDIUM — default GitHub Actions permissions grant write on some event types without explicit declaration."),
      ("custom:Likelihood", "Medium — default GitHub Actions permissions grant write on some event types"),
      ("custom:Impact", "Medium — unintended repo writes; no direct code execution"),
      ("custom:Priority", "Medium — Likelihood(2) × Impact(2) = 4. Mitigated: permissions: contents: read declared at workflow and job level in ci.yml (currently implemented)"),
    )
  },
  # ── 9. MEDIUM: Dependency confusion ──────────────────────────────────────
  {
    "id": T10, "numericId": 9, "displayOrder": 9,
    "statement": "A dependency confusion attacker with a malicious package published to PyPI under a name matching a hypothetical internal package, exploiting pip's default resolution order, can cause the CI runner to install and execute the malicious package instead of the intended one, which leads to arbitrary code execution in the CI environment, negatively impacting build integrity.",
    "threatSource": "dependency confusion attacker with a malicious package published to PyPI",
    "prerequisites": "exploiting pip's default public-registry-first resolution order if any private packages are ever added",
    "threatAction": "cause the CI runner to install and execute a malicious package instead of the intended one",
    "threatImpact": "arbitrary code execution in the CI environment; build artifacts potentially backdoored",
    "impactedAssets": ["CI/CD pipeline","build artifacts","runner environment"],
    "tags": ["STRIDE-Elevation-of-Privilege","Priority-Medium","CI-CD","Supply-Chain"],
    "metadata": md(
      ("custom:STRIDE", "Elevation of Privilege — attacker gains code execution in CI by exploiting package resolution order. Surface: CI pip install steps. Exploitability: LOW currently (no private packages), but risk increases if private packages are added."),
      ("custom:Likelihood", "Low — no private packages currently; risk increases if private packages are added"),
      ("custom:Impact", "High — arbitrary code execution on CI runner"),
      ("custom:Priority", "Medium — Likelihood(1) × Impact(3) = 3. Recommended: hash-pinned requirements prevent installing unintended package versions"),
    )
  },
  # ── 10. MEDIUM: 0.0.0.0 exposure ─────────────────────────────────────────
  {
    "id": T11, "numericId": 10, "displayOrder": 10,
    "statement": "A QuoteService instance misconfigured with host='0.0.0.0', running on a machine with a public IP, can accept TCP/UDP connections from any internet client, which leads to unintended public exposure of the RFC 865 service and an expanded DoS attack surface, negatively impacting service availability and potentially exposing the host to connection-based attacks.",
    "threatSource": "QuoteService instance misconfigured with host='0.0.0.0'",
    "prerequisites": "running on a machine with a public IP address or behind a NAT with port forwarding enabled",
    "threatAction": "accept TCP/UDP connections from any internet client, expanding the attack surface to the public internet",
    "threatImpact": "unintended public exposure of the RFC 865 service; expanded DoS attack surface; host network interfaces exposed",
    "impactedAssets": ["QuoteService TCP/UDP server","host network interfaces","server resources","connected clients"],
    "tags": ["STRIDE-Information-Disclosure","STRIDE-Denial-of-Service","Priority-Medium","QuoteService","Network","Implemented"],
    "metadata": md(
      ("custom:STRIDE", "Information Disclosure (service becomes reachable from untrusted networks, exposing its existence and the host's network stack) + Denial of Service (expanded attack surface enables connection floods from the public internet). Surface: any machine where QuoteService is deployed. Exploitability: MEDIUM — misconfiguration is easy; default is safe but easy to override."),
      ("custom:Likelihood", "Medium — misconfiguration risk; default is safe (127.0.0.1) but easy to override"),
      ("custom:Impact", "Medium — quote content exposed; DoS surface expanded; no credential or PII leak"),
      ("custom:Priority", "Medium — Likelihood(2) × Impact(2) = 4. Mitigated: default host is 127.0.0.1 (loopback only); document that 0.0.0.0 requires firewall rules"),
    )
  },
  # ── 11. MEDIUM: XSS via name reflection ──────────────────────────────────
  {
    "id": T21, "numericId": 11, "displayOrder": 11,
    "statement": "An attacker with the ability to send crafted HTTP requests to the Worker, injecting JavaScript payload strings into the name query parameter that are reflected into the HTML page's inline script block, can execute arbitrary JavaScript in the browser of any user who visits the crafted URL, which leads to cross-site scripting, negatively impacting the confidentiality and integrity of the user's browser session and any data accessible to that session.",
    "threatSource": "attacker with the ability to send crafted HTTP requests to the Worker",
    "prerequisites": "injecting a name value containing JavaScript that survives the current sanitisation and is reflected into the inline script block via json.dumps(name)",
    "threatAction": "execute arbitrary JavaScript in the browser of any user who visits the crafted URL",
    "threatImpact": "cross-site scripting enabling session hijacking, credential theft, or exfiltration of any data accessible in the victim's browser session",
    "impactedAssets": ["user browser session","HTML response","Worker HTML output","user credentials and session data"],
    "tags": ["STRIDE-Tampering","STRIDE-Elevation-of-Privilege","Priority-Medium","Worker","XSS","Input-Validation"],
    "metadata": md(
      ("custom:STRIDE", "Tampering (attacker injects executable content into a trusted page served to other users) + Elevation of Privilege (attacker gains JavaScript execution in the victim's browser, inheriting the victim's session context and any data accessible to it). Surface: public Worker URL, any browser. Exploitability: MEDIUM — json.dumps escapes quotes but Unicode/HTML-entity payloads may survive; the Worker IS a web app."),
      ("custom:Likelihood", "Low-Medium — name is reflected via json.dumps() which escapes quotes; ANSI/non-printable strip removes most vectors; but Unicode or HTML-entity payloads may survive"),
      ("custom:Impact", "Medium — XSS in a demo app with no auth; limited blast radius but real risk; in a production app with auth this would be High"),
      ("custom:Priority", "Medium — Likelihood(2) × Impact(2) = 4. Recommend adding html.escape() on name before embedding in HTML context + Content-Security-Policy header"),
    )
  },
  # ── 12. MEDIUM: Worker DoS quota ─────────────────────────────────────────
  {
    "id": T22, "numericId": 12, "displayOrder": 12,
    "statement": "An attacker with knowledge of the Worker's public URL, sending a high volume of GET requests to the greeting endpoint, can consume the Worker's CPU time and D1 write quota, which leads to Cloudflare rate limiting or quota exhaustion, negatively impacting availability of the greeting service for legitimate users.",
    "threatSource": "attacker with knowledge of the Worker's public URL",
    "prerequisites": "sending a sustained high volume of HTTP GET requests to https://greeting-worker.cancun.workers.dev/",
    "threatAction": "consume the Worker CPU time and D1 write quota through repeated telemetry INSERTs",
    "threatImpact": "Cloudflare rate limiting or D1 write quota exhaustion causing service degradation for legitimate users",
    "impactedAssets": ["Cloudflare Worker CPU quota","D1 write quota","greeting service availability"],
    "tags": ["STRIDE-Denial-of-Service","Priority-Medium","Worker","Cloudflare"],
    "metadata": md(
      ("custom:STRIDE", "Denial of Service — resource exhaustion via high-volume requests consuming platform quotas. Surface: public internet endpoint with no rate limiting. Exploitability: HIGH — trivial to automate with any HTTP load tool; no authentication required."),
      ("custom:Likelihood", "Medium — public endpoint with no rate limiting; trivial to automate"),
      ("custom:Impact", "Medium — service degradation; no data loss; Cloudflare's platform provides some inherent protection"),
      ("custom:Priority", "Medium — Likelihood(2) × Impact(2) = 4. Recommend enabling Cloudflare Rate Limiting rule on the Worker route"),
    )
  },
  # ── 13. MEDIUM: ANSI injection via name ──────────────────────────────────
  {
    "id": T01, "numericId": 13, "displayOrder": 13,
    "statement": "An external caller with access to the Greeting CLI or Worker API, passing a crafted name value containing ANSI escape sequences or terminal control codes, can manipulate terminal rendering or corrupt the display of subsequent output, which leads to terminal state corruption, negatively impacting the integrity of the operator's terminal session.",
    "threatSource": "external caller with access to the Greeting CLI or Worker API",
    "prerequisites": "passing a crafted name value containing ANSI escape sequences or control characters via sys.argv or HTTP query param",
    "threatAction": "manipulate terminal rendering or corrupt the display of subsequent output",
    "threatImpact": "terminal state corruption; potential for hiding malicious output from the operator",
    "impactedAssets": ["terminal stdout","operator terminal session"],
    "tags": ["STRIDE-Tampering","Priority-Medium","CLI","Worker","Input-Validation","Implemented"],
    "metadata": md(
      ("custom:STRIDE", "Tampering — attacker modifies the output stream to alter what the operator sees, potentially hiding malicious activity. Surface: CLI argv and HTTP query param — both attacker-controlled. Exploitability: MEDIUM — trivial to craft; mitigated by two-pass sanitisation."),
      ("custom:Likelihood", "Medium — name comes from CLI argv or HTTP query param, both attacker-controlled"),
      ("custom:Impact", "Low — stdout only, no persistence, no privilege escalation"),
      ("custom:Priority", "Medium — Likelihood(2) × Impact(1) = 2, elevated to Medium due to broad surface area. Mitigated: two-pass ANSI strip + printable-ASCII filter + 100-char cap (currently implemented)"),
    )
  },
  # ── 14. MEDIUM: TCP connection exhaustion ────────────────────────────────
  {
    "id": T12, "numericId": 14, "displayOrder": 14,
    "statement": "A network attacker with the ability to open many TCP connections to QuoteService, sending connections faster than they are served, can exhaust the server's OS file descriptor limit or spawn unbounded daemon threads, which leads to service unavailability for legitimate clients, negatively impacting QuoteService availability.",
    "threatSource": "network attacker with the ability to open many TCP connections to QuoteService",
    "prerequisites": "QuoteService reachable from the attacker's network (requires host='0.0.0.0' misconfiguration or local network access)",
    "threatAction": "exhaust the server OS file descriptor limit or spawn unbounded daemon threads",
    "threatImpact": "service unavailability for legitimate clients; potential host resource exhaustion",
    "impactedAssets": ["QuoteService TCP server","OS file descriptors","thread pool"],
    "tags": ["STRIDE-Denial-of-Service","Priority-Medium","QuoteService","Network"],
    "metadata": md(
      ("custom:STRIDE", "Denial of Service — resource exhaustion via unbounded connection acceptance. Surface: TCP port of QuoteService. Exploitability: HIGH if reachable — trivial with netcat or a script; gated by the loopback-only default."),
      ("custom:Likelihood", "Medium — trivial to exploit with netcat or a script if service is reachable; default loopback binding limits exposure"),
      ("custom:Impact", "Medium — service unavailable; no data loss; no privilege escalation"),
      ("custom:Priority", "Medium — Likelihood(2) × Impact(2) = 4. Recommended: bounded ThreadPoolExecutor with max_workers in start_tcp()"),
    )
  },
  # ── 15. LOW: datetime injection ───────────────────────────────────────────
  {
    "id": T02, "numericId": 15, "displayOrder": 15,
    "statement": "A test harness or caller with the ability to subclass datetime, passing an object whose .hour property returns a value outside 0-23, can cause TimeOfDay.from_hour() to silently fall through to NIGHT, which leads to an incorrect greeting period being displayed, negatively impacting output correctness.",
    "threatSource": "test harness or caller with the ability to subclass datetime",
    "prerequisites": "passing a datetime object whose .hour property returns a value outside 0-23",
    "threatAction": "cause TimeOfDay.from_hour() to silently fall through to NIGHT",
    "threatImpact": "incorrect greeting period displayed; no data loss or privacy impact",
    "impactedAssets": ["TimeOfDay period logic","greeting output"],
    "tags": ["STRIDE-Tampering","Priority-Low","CLI","Input-Validation","Recommended"],
    "metadata": md(
      ("custom:STRIDE", "Tampering — attacker manipulates the period classification logic via a crafted input object. Surface: programmatic API only; no external trigger. Exploitability: LOW — requires deliberate API misuse or a buggy mock."),
      ("custom:Likelihood", "Low — requires deliberate API misuse or a buggy mock; no external trigger"),
      ("custom:Impact", "Low — cosmetic output only; no data loss, no privacy impact"),
      ("custom:Priority", "Low — Likelihood(1) × Impact(1) = 1. Recommend adding isinstance + range check in from_hour()"),
    )
  },
  # ── 16. LOW: Large name DoS ───────────────────────────────────────────────
  {
    "id": T03, "numericId": 16, "displayOrder": 16,
    "statement": "An external caller with access to the Greeting CLI, passing an unbounded name string of several megabytes, can cause excessive memory allocation during f-string construction and stdout write, which leads to process-level memory exhaustion, negatively impacting CLI availability.",
    "threatSource": "external caller with access to the Greeting CLI",
    "prerequisites": "passing an unbounded name string of several megabytes via sys.argv",
    "threatAction": "cause excessive memory allocation during f-string construction and stdout write",
    "threatImpact": "process-level memory exhaustion; CLI unavailable for the duration",
    "impactedAssets": ["process memory","CLI availability"],
    "tags": ["STRIDE-Denial-of-Service","Priority-Low","CLI","Input-Validation","Implemented"],
    "metadata": md(
      ("custom:STRIDE", "Denial of Service — resource exhaustion via unbounded input. Surface: CLI argv. Exploitability: LOW — requires local access to run the CLI with a crafted argument."),
      ("custom:Likelihood", "Low — requires local access to run the CLI with a crafted argument"),
      ("custom:Impact", "Low — process-level only, no system-wide effect, no data loss"),
      ("custom:Priority", "Low — Likelihood(1) × Impact(1) = 1. Mitigated: 100-char cap enforced at Greeting.__init__()"),
    )
  },
  # ── 17. LOW: Log info disclosure ─────────────────────────────────────────
  {
    "id": T14, "numericId": 17, "displayOrder": 17,
    "statement": "An attacker with the ability to trigger socket errors in QuoteService handlers, causing unhandled exceptions to propagate to the logging layer, can read server log files that contain Python stack traces revealing internal file paths and library versions, which leads to information disclosure, negatively impacting operational security by aiding further attack planning.",
    "threatSource": "attacker with the ability to trigger socket errors in QuoteService handlers",
    "prerequisites": "read access to the server's log output (local or via a log aggregation system)",
    "threatAction": "read stack traces in server logs revealing internal file paths and library versions",
    "threatImpact": "information disclosure aiding further attack planning; no direct data loss or privacy impact",
    "impactedAssets": ["server log files","internal file paths","Python version and library information"],
    "tags": ["STRIDE-Information-Disclosure","Priority-Low","QuoteService","Implemented"],
    "metadata": md(
      ("custom:STRIDE", "Information Disclosure — internal implementation details leak via log output. Surface: server logs (local access required). Exploitability: LOW — requires log access; stack traces are not sent to clients."),
      ("custom:Likelihood", "Low — requires log access; stack traces are not sent to clients"),
      ("custom:Impact", "Low — aids reconnaissance; no direct exploitation; no customer data at risk"),
      ("custom:Priority", "Low — Likelihood(1) × Impact(1) = 1. Mitigated: all socket errors caught and logged at WARNING level; nothing sent to clients (currently implemented)"),
    )
  },
  # ── 18. LOW: UDP reflection ───────────────────────────────────────────────
  {
    "id": T15, "numericId": 18, "displayOrder": 18,
    "statement": "A network attacker with the ability to spoof UDP source IP addresses, sending a crafted datagram to the QuoteService UDP port with a victim's IP as the source, can cause the server to send a quote response to the victim, which leads to a low-amplification UDP reflection attack, negatively impacting the victim's network availability.",
    "threatSource": "network attacker with the ability to spoof UDP source IP addresses",
    "prerequisites": "QuoteService UDP port reachable from the attacker's network AND network path allows IP spoofing (BCP38 not enforced)",
    "threatAction": "cause the server to send quote responses to a spoofed victim IP address",
    "threatImpact": "low-amplification UDP reflection attack against the victim; no data loss or privacy impact on the server side",
    "impactedAssets": ["victim network bandwidth","QuoteService UDP socket"],
    "tags": ["STRIDE-Denial-of-Service","Priority-Low","QuoteService","Network","UDP"],
    "metadata": md(
      ("custom:STRIDE", "Denial of Service — attacker abuses the server as a reflector to amplify traffic toward a victim. Surface: UDP port of QuoteService. Exploitability: LOW — requires IP spoofing capability AND public UDP exposure; default bind is 127.0.0.1 (loopback cannot be spoofed externally)."),
      ("custom:Likelihood", "Low — requires IP spoofing capability AND public UDP exposure; default bind is 127.0.0.1"),
      ("custom:Impact", "Low-Medium — small amplification factor (quote <= 512 bytes); limited to loopback by default"),
      ("custom:Priority", "Low — Likelihood(1) × Impact(1) = 1. Mitigated by default loopback binding; re-evaluate if UDP is ever exposed on a public interface"),
    )
  },
  # ── 19. LOW: SQLite error_msg ─────────────────────────────────────────────
  {
    "id": T16, "numericId": 19, "displayOrder": 19,
    "statement": "A caller with the ability to invoke TelemetryStore.record() or _MeasureContext.fail(), passing an unbounded error string such as a full exception traceback, can write a large payload to the SQLite error_msg column, which leads to unbounded disk growth and potential leakage of internal stack trace details to anyone with read access to the database file, negatively impacting local storage and operational security.",
    "threatSource": "caller with the ability to invoke TelemetryStore.record() or _MeasureContext.fail()",
    "prerequisites": "passing an unbounded error string (e.g. a multi-kilobyte exception traceback) as the error_msg argument",
    "threatAction": "write a large payload to the SQLite error_msg column repeatedly",
    "threatImpact": "unbounded disk growth and leakage of internal stack trace details to local DB readers",
    "impactedAssets": ["SQLite database file","local disk","internal stack trace information"],
    "tags": ["STRIDE-Denial-of-Service","STRIDE-Information-Disclosure","Priority-Low","SQLite","Telemetry","Implemented"],
    "metadata": md(
      ("custom:STRIDE", "Denial of Service (disk exhaustion via unbounded error_msg writes) + Information Disclosure (stack traces stored in DB are visible to anyone with read access to the file — could reveal internal paths, library versions, or logic details). Surface: programmatic API only. Exploitability: LOW — only reachable via programmatic API; no external trigger."),
      ("custom:Likelihood", "Low — only reachable via programmatic API; no external trigger"),
      ("custom:Impact", "Low-Medium — disk exhaustion possible over time; stack traces visible to local DB readers; no PII in this app"),
      ("custom:Priority", "Low — Likelihood(1) × Impact(2) = 2. Mitigated: error_msg truncated to 500 chars in _MeasureContext.fail() and CfTelemetry.record() (currently implemented)"),
    )
  },
  # ── 20. LOW: db_path traversal ────────────────────────────────────────────
  {
    "id": T17, "numericId": 20, "displayOrder": 20,
    "statement": "A caller with the ability to configure TelemetryStore at instantiation, supplying a crafted db_path value such as '../../etc/shadow' or a SQLite URI with special flags, can cause sqlite3.connect() to open an unintended file location, which leads to unintended file creation or access outside the project directory, negatively impacting filesystem integrity.",
    "threatSource": "caller with the ability to configure TelemetryStore at instantiation",
    "prerequisites": "supplying a crafted db_path value containing path traversal sequences or SQLite URI flags",
    "threatAction": "cause sqlite3.connect() to open an unintended file location outside the project directory",
    "threatImpact": "unintended file creation or read access outside the project directory; no privilege escalation",
    "impactedAssets": ["local filesystem","SQLite database","files outside project root"],
    "tags": ["STRIDE-Tampering","Priority-Low","SQLite","Path-Traversal","Implemented"],
    "metadata": md(
      ("custom:STRIDE", "Tampering — attacker redirects database writes to an unintended filesystem location. Surface: programmatic API only; no external trigger. Exploitability: VERY LOW — db_path is only reachable via programmatic API; default is hardcoded."),
      ("custom:Likelihood", "Very Low — db_path is only reachable via programmatic API; default is hardcoded; no external trigger"),
      ("custom:Impact", "Low — local process only; no privilege escalation; no customer data at risk"),
      ("custom:Priority", "Low — Likelihood(1) × Impact(1) = 1. Mitigated: db_path wrapped in pathlib.Path() normalising traversal sequences (currently implemented)"),
    )
  },
  # ── 21. LOW: Unauthenticated /stats ──────────────────────────────────────
  {
    "id": T18, "numericId": 21, "displayOrder": 21,
    "statement": "An unauthenticated HTTP client with access to the public Worker URL, sending a GET to /stats, can read the full historic telemetry summary including request counts, latency percentiles, and fault rates, which leads to unintended disclosure of operational performance data, negatively impacting the confidentiality of service health information.",
    "threatSource": "unauthenticated HTTP client with access to the public Worker URL",
    "prerequisites": "sending a GET request to https://greeting-worker.cancun.workers.dev/stats — no credentials required",
    "threatAction": "read the full historic telemetry summary including request counts, latency percentiles, and fault rates",
    "threatImpact": "unintended disclosure of operational performance and error rate data; aids reconnaissance",
    "impactedAssets": ["D1 telemetry data","service health information","fault rate and latency metrics"],
    "tags": ["STRIDE-Information-Disclosure","Priority-Low","Worker","Authentication"],
    "metadata": md(
      ("custom:STRIDE", "Information Disclosure — operational metrics exposed to unauthenticated public clients. Surface: public internet endpoint. Exploitability: TRIVIAL — a single GET request. Impact is low because no PII or credentials are exposed, only aggregate performance metrics."),
      ("custom:Likelihood", "High — endpoint is publicly reachable with no authentication"),
      ("custom:Impact", "Low — no PII, no credentials; aids reconnaissance of service health only"),
      ("custom:Priority", "Low — Likelihood(3) × Impact(1) = 3, kept Low because impact ceiling is reconnaissance only. Acceptable for a demo; in production add Cloudflare Access or a secret header"),
    )
  },
  # ── 22. LOW: Corpus injection ─────────────────────────────────────────────
  {
    "id": T20, "numericId": 22, "displayOrder": 22,
    "statement": "A caller with the ability to instantiate QuoteProvider with a custom quotes tuple, passing quotes containing ANSI escape sequences or control characters, can cause those sequences to be transmitted verbatim over the TCP/UDP socket to connected clients, which leads to terminal state corruption on the receiving client, negatively impacting the integrity of the client's terminal session.",
    "threatSource": "caller with the ability to instantiate QuoteProvider with a custom quotes tuple",
    "prerequisites": "passing a custom quotes tuple containing ANSI escape sequences or terminal control characters",
    "threatAction": "cause malicious sequences to be transmitted verbatim over TCP/UDP to connected clients",
    "threatImpact": "terminal state corruption on the receiving RFC 865 client; no server-side data loss",
    "impactedAssets": ["QuoteService TCP/UDP clients","client terminal sessions"],
    "tags": ["STRIDE-Tampering","Priority-Low","QuoteProvider","QuoteService","Implemented"],
    "metadata": md(
      ("custom:STRIDE", "Tampering — attacker injects malicious content into the quote corpus to manipulate client terminals. Surface: programmatic API only; built-in corpus is static. Exploitability: LOW — requires deliberate API misuse."),
      ("custom:Likelihood", "Low — requires deliberate API misuse; built-in corpus is static and reviewed"),
      ("custom:Impact", "Low — terminal manipulation on client; no server-side impact; no data loss"),
      ("custom:Priority", "Low — Likelihood(1) × Impact(1) = 1. Mitigated: built-in corpus is static; length validated at construction (currently implemented); recommend ANSI-stripping for custom corpora"),
    )
  },
]

# ── assumptionLinks ───────────────────────────────────────────────────────────
# A1 (QuoteService loopback): T11, T12, T15, T12(tcp)
# A2 (Worker internet-facing): T04, T18, T21, T22
# A3 (SQLite local, no PII): T16, T17
# A4 (No secrets in git): T19
# A5 (/reset and /stats unauthenticated by design): T04, T18
# A6 (CI runners ephemeral, actions pinned): T07, T08, T09

# AssumptionLinkSchema: type ('Threat'|'Mitigation'), assumptionId, linkedId — strict, no extra fields
def al(linked_id, assumption_id, link_type="Threat"):
    return {"type": link_type, "linkedId": linked_id, "assumptionId": assumption_id}

assumptionLinks = [
    al(T11, A1),  # A1 loopback → T-10 0.0.0.0 exposure
    al(T12, A1),  # A1 loopback → T-14 TCP exhaustion
    al(T15, A1),  # A1 loopback → T-18 UDP reflection
    al(T04, A2),  # A2 Worker internet-facing → T-03 unauthenticated /reset
    al(T18, A2),  # A2 Worker internet-facing → T-21 unauthenticated /stats
    al(T21, A2),  # A2 Worker internet-facing → T-11 XSS
    al(T22, A2),  # A2 Worker internet-facing → T-12 Worker DoS
    al(T16, A3),  # A3 SQLite local → T-19 error_msg
    al(T17, A3),  # A3 SQLite local → T-20 db_path traversal
    al(T19, A4),  # A4 no secrets in git → T-06 credential leak
    al(T04, A5),  # A5 /reset unauthenticated by design → T-03
    al(T18, A5),  # A5 /stats unauthenticated by design → T-21
    al(T07, A6),  # A6 CI runners ephemeral → T-02 poisoned pipeline
    al(T08, A6),  # A6 CI runners ephemeral → T-04 mutable Actions tag
    al(T09, A6),  # A6 CI runners ephemeral → T-08 excessive CI permissions
]

# ── mitigationLinks ───────────────────────────────────────────────────────────
mitigationLinks = [
    {"linkedId": T01, "mitigationId": M1},
    {"linkedId": T03, "mitigationId": M1},
    {"linkedId": T02, "mitigationId": M2},
    {"linkedId": T04, "mitigationId": M3},
    {"linkedId": T05, "mitigationId": M4},
    {"linkedId": T05, "mitigationId": M5},
    {"linkedId": T05, "mitigationId": M18},
    {"linkedId": T06, "mitigationId": M4},
    {"linkedId": T06, "mitigationId": M5},
    {"linkedId": T06, "mitigationId": M18},
    {"linkedId": T07, "mitigationId": M6},
    {"linkedId": T07, "mitigationId": M8},
    {"linkedId": T08, "mitigationId": M6},
    {"linkedId": T09, "mitigationId": M7},
    {"linkedId": T09, "mitigationId": M8},
    {"linkedId": T10, "mitigationId": M4},
    {"linkedId": T11, "mitigationId": M9},
    {"linkedId": T12, "mitigationId": M9},
    {"linkedId": T12, "mitigationId": M10},
    {"linkedId": T13, "mitigationId": M11},
    {"linkedId": T14, "mitigationId": M12},
    {"linkedId": T15, "mitigationId": M12},
    {"linkedId": T16, "mitigationId": M13},
    {"linkedId": T17, "mitigationId": M14},
    {"linkedId": T18, "mitigationId": M15},
    {"linkedId": T19, "mitigationId": M16},
    {"linkedId": T20, "mitigationId": M17},
    {"linkedId": T21, "mitigationId": M1},
    {"linkedId": T21, "mitigationId": M19},
]

doc = {
    "schema": 1,
    "applicationInfo": {
        "name": "Greeting — CLI + Cloudflare Worker",
        "description": (
            "A time-aware colourised terminal greeting CLI (Python) with RFC 865 Quote of the Day (TCP/UDP), "
            "async SQLite telemetry, and a Cloudflare Worker HTTP API backed by D1. "
            "Live demo: https://greeting-worker.cancun.workers.dev/\n\n"
            "Components: Greeting class, TimeOfDay enum, QuoteProvider (120-quote corpus, shuffle-deck), "
            "QuoteService (RFC 865 TCP+UDP), TelemetryStore (SQLite, background queue, nanosecond precision), "
            "StatsReporter, Cloudflare Worker (entry.py + cf_telemetry.py), GitHub Actions CI."
        )
    },
    "architecture": {
        "description": (
            "## Trust Zones\n\n"
            "**Zone 1 — Developer workstation (fully trusted):** src/, tests/, Makefile, scripts/dev.sh. "
            "Runs as the developer's OS user. SQLite DB at greeting_telemetry.db is local-only.\n\n"
            "**Zone 2 — GitHub Actions runner (partially trusted):** .github/workflows/ci.yml. "
            "Ephemeral Ubuntu runner. Has access to repository secrets. Triggered by push/pull_request.\n\n"
            "**Zone 3 — Cloudflare edge (trusted platform, untrusted input):** worker/src/entry.py runs "
            "inside a V8 isolate. Receives arbitrary HTTP requests from the public internet. D1 database is Cloudflare-managed.\n\n"
            "**Zone 4 — Network clients (untrusted):** Any TCP/UDP client connecting to QuoteService. "
            "Any HTTP client hitting the Worker.\n\n"
            "## Key Components\n\n"
            "- **Greeting.__init__(name)** — sanitises name (two-pass ANSI strip + printable-ASCII filter + 100-char cap)\n"
            "- **TimeOfDay.from_hour(hour)** — enum lookup, no external input\n"
            "- **QuoteProvider.get()** — shuffle-deck from static corpus; custom corpus accepted at construction\n"
            "- **QuoteService.start_tcp/udp()** — binds to 127.0.0.1 by default; daemon threads per connection\n"
            "- **TelemetryStore** — background queue thread writes to SQLite; error_msg truncated to 500 chars\n"
            "- **Worker Default.fetch()** — sanitises name query param; routes to greeting/quote/stats/reset\n"
            "- **CfTelemetry** — D1 INSERT via Pyodide JsProxy; parameterised queries only"
        )
    },
    "dataflow": {
        "description": (
            "## Data Flows\n\n"
            "**DF-1 CLI greeting:** sys.argv[1] (untrusted) → Greeting.__init__ (sanitise) → "
            "Greeting.build(datetime.now()) → TimeOfDay.from_hour() → stdout. "
            "TelemetryStore.record() enqueued async → SQLite writer thread → greeting_telemetry.db.\n\n"
            "**DF-2 RFC 865 TCP:** TCP client (untrusted) → QuoteService._handle_tcp() → "
            "QuoteProvider.get() → conn.sendall(quote.encode('ascii')). Client data silently discarded per RFC 865.\n\n"
            "**DF-3 RFC 865 UDP:** UDP datagram (untrusted, spoofable source) → QuoteService UDP loop → "
            "QuoteProvider.get() → srv.sendto(quote, client_addr). Source IP not verified.\n\n"
            "**DF-4 Worker HTTP GET /:** HTTP request (public internet) → Default.fetch() → "
            "_sanitise_name(params['name']) → _build_greeting() → CfTelemetry.record() → D1 INSERT → HTML/JSON response.\n\n"
            "**DF-5 Worker HTTP GET /stats:** HTTP request → Default.fetch() → "
            "CfTelemetry.historic_summary() → D1 SELECT → JSON response. No authentication on this endpoint.\n\n"
            "**DF-6 Worker HTTP POST /reset:** HTTP request → Default.fetch() → "
            "CfTelemetry.reset() → D1 DELETE. No authentication on this endpoint.\n\n"
            "**DF-7 CI/CD:** git push → GitHub Actions runner → pip install -r requirements-dev.txt → "
            "unittest → pip-audit → sphinx-build. Runner has GITHUB_TOKEN with contents:read."
        )
    },
    "assumptions": assumptions,
    "mitigations": mitigations,
    "assumptionLinks": assumptionLinks,
    "mitigationLinks": mitigationLinks,
    "threats": threats,
}

OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
print(f"Written {OUT} ({OUT.stat().st_size} bytes, {len(threats)} threats, "
      f"{len(mitigations)} mitigations, {len(assumptionLinks)} assumptionLinks, "
      f"{len(mitigationLinks)} mitigationLinks)")
