#!/usr/bin/env python3
"""
Generate docs/threat_model.tc.json — AWS Threat Composer importable format.

Schema rules (from source):
  Assumption.metadata:    MetadataSchemaMinimal  → Comments | custom:*
  Mitigation.metadata:    MetadataSchemaMitigation → Comments | custom:* | source keys
  Mitigation.status:      mitigationIdentified | mitigationInProgress |
                          mitigationResolved | mitigationResolvedWillNotAction
  Threat.metadata:        MetadataSchemaThreats → STRIDE(array) | Priority(High/Medium/Low) |
                          Comments | custom:*
  AssumptionLink:         { type: "Threat"|"Mitigation", linkedId: uuid36, assumptionId: uuid36 }
  MitigationLink:         { mitigationId: uuid36, linkedId: uuid36 }
  All schemas are .strict() — no extra fields.
"""
import json, pathlib

OUT = pathlib.Path("docs/threat_model.tc.json")

# ── Assumption IDs ────────────────────────────────────────────────────────────
A1 = "f069ba5f-505c-477a-ac6e-9966b45d38ac"  # QuoteService loopback only
A2 = "43c54cd3-6c2a-4dec-9e39-484f2c6c06c8"  # Worker is only internet-facing
A3 = "f47ea747-a2a2-4bf9-8335-5cb3abf0b3da"  # SQLite local, no PII
A4 = "2458585c-8d5c-41d4-b1c0-160e7d8d55af"  # No secrets in git
A5 = "a0883d44-2638-4f87-a5a5-d412c8f9b80c"  # /reset and /stats unauthenticated by design
A6 = "df4bb2f8-331a-42e5-9a17-5c3bee82bd6d"  # CI runners ephemeral, actions pinned

# ── Mitigation IDs ────────────────────────────────────────────────────────────
M1  = "d02ae732-dc06-4c14-98b9-72b366480435"  # Two-pass name sanitisation
M2  = "d6de56e7-311b-4575-9458-b7367a7bf311"  # TimeOfDay hour range validation
M3  = "447d5188-d3a3-4db0-9e63-5faccdc65ac5"  # Auth on /reset
M4  = "da5c66b2-a4ac-4480-969a-b543385572b7"  # Hash-pin PyPI deps
M5  = "66c5bef0-868a-41be-90ad-c4106f0fb4c7"  # pip-audit in CI
M6  = "40737722-0bc7-45b0-a619-01d055a906ef"  # Pin Actions to SHAs
M7  = "d324acde-a6bc-4871-a0d1-974c284810cb"  # permissions: contents: read
M8  = "a875f12e-f88f-495d-bd17-a5575fbbf462"  # Branch protection + PR approval
M9  = "ed84e30a-1408-48a8-b1fb-bb250ea649d5"  # QuoteService loopback default
M10 = "f59bfc3f-d8a0-4c14-bb1d-3e98859ce2a5"  # Bounded ThreadPoolExecutor
M11 = "3d57cbab-0a1b-4bd2-b2d2-3bc15e2e0cd7"  # CAP_NET_BIND_SERVICE / authbind
M12 = "d1d2d435-d978-4988-8f01-de78ad807682"  # Socket errors caught, not sent to clients
M13 = "29a96004-ab51-40b7-94da-72ea870acda3"  # error_msg truncated to 500 chars
M14 = "e140177a-ce32-4bb5-9709-52e09a25fbb5"  # db_path via pathlib.Path()
M15 = "3cdf5c0c-17d6-4832-99ba-33f9066a90ba"  # Parameterised D1 queries
M16 = "2268844b-b35d-4716-834b-e42d85903b17"  # Secrets in gitignored local config
M17 = "6b5a7958-2f16-44d7-be62-880a65b0f0b0"  # QuoteProvider length validation
M18 = "8aac83f6-5242-4beb-8fef-657c0bf901c7"  # Dependabot alerts
M19 = "b3c7f821-9d4e-4a1f-bc23-7e8d5f6a2c91"  # html.escape() + CSP header

# ── Threat IDs (ordered Critical→High→Medium→Low) ────────────────────────────
T05 = "c3ea3d79-994e-4e88-9910-ede209e77da8"  # 1  Critical: supply chain colorama
T07 = "275751b2-f3ce-445c-86e6-b244152c0fa4"  # 2  Critical: poisoned pipeline
T04 = "a6bdd8bf-838b-4d48-b86a-603a8daa0f8b"  # 3  High: unauthenticated /reset
T08 = "1a85a617-68f7-4aaa-bb71-85c3e0411e42"  # 4  High: mutable Actions tag
T13 = "91bbff65-afc7-43cc-ad9c-40230223b775"  # 5  High: root for port 17
T19 = "cd632493-6169-4c47-8159-3d6b884d0f9b"  # 6  High: credential leak to git
T06 = "900c20a5-db67-4b72-8210-bcc872ed8596"  # 7  Medium: typosquatting
T09 = "d6d30c8d-308d-4e57-9ed5-bac2cffb319d"  # 8  Medium: excessive CI permissions
T10 = "1932fe98-fe93-4ec2-a84b-79847abed77a"  # 9  Medium: dependency confusion
T11 = "0a5cd4a5-0f60-401e-a0e4-c057e2807589"  # 10 Medium: 0.0.0.0 exposure
T21 = "ee12e801-d0ca-43b1-8434-6a1f992a3728"  # 11 Medium: XSS via name
T22 = "5181e9b3-b05f-4689-adf6-3e9c4803258d"  # 12 Medium: Worker DoS quota
T01 = "640f6502-da6f-49d2-82a4-f85b3632a265"  # 13 Medium: ANSI injection
T12 = "050c6692-20ea-41fd-8d54-f68e8d9d7820"  # 14 Medium: TCP exhaustion
T02 = "0ee7dc62-cfbf-4a99-ab41-01086788c75e"  # 15 Low: datetime injection
T03 = "4e815c23-6b2b-4569-9040-b1439cb66f32"  # 16 Low: large name DoS
T14 = "c2af25a7-8cb4-4bcb-8122-14de77344436"  # 17 Low: log info disclosure
T15 = "fa551525-5932-4d76-9afe-27575b1760c2"  # 18 Low: UDP reflection
T16 = "aa97ee68-d4e9-4a88-b67d-e61c20978d91"  # 19 Low: SQLite error_msg
T17 = "59b86efe-4db2-4c9c-b69c-99074f644de3"  # 20 Low: db_path traversal
T18 = "f0cb25d1-c98b-4ff4-b4f8-c48c07b18b2d"  # 21 Low: unauthenticated /stats
T20 = "df900016-58f7-43b1-b536-c556d3e9fb57"  # 22 Low: corpus injection

# ── Metadata helpers ──────────────────────────────────────────────────────────
def assumption_meta(comment):
    """Assumption metadata: Comments only (MetadataSchemaMinimal)."""
    return [{"key": "Comments", "value": comment}]

def mitigation_meta(comment, status_tag=None):
    """Mitigation metadata: Comments (MetadataSchemaMitigation)."""
    return [{"key": "Comments", "value": comment}]

def threat_meta(stride_codes, priority, comment, **custom):
    """Threat metadata: STRIDE array + Priority + Comments + optional custom:* keys."""
    result = [
        {"key": "STRIDE",   "value": stride_codes},
        {"key": "Priority", "value": priority},
        {"key": "Comments", "value": comment},
    ]
    for k, v in custom.items():
        result.append({"key": f"custom:{k}", "value": v})
    return result

# Mitigation status values
IDENTIFIED = "mitigationIdentified"
IN_PROGRESS = "mitigationInProgress"
RESOLVED    = "mitigationResolved"
WONT_ACT    = "mitigationResolvedWillNotAction"

# ── Assumptions ───────────────────────────────────────────────────────────────
# Each assumption scopes the threat model — it defines what we are NOT protecting
# against, and what we take as given. Linked to relevant threats AND mitigations.
assumptions = [
    {
        "id": A1, "numericId": 1, "displayOrder": 1,
        "content": "QuoteService binds to 127.0.0.1 (loopback) by default and is never intentionally exposed to the public internet. Any deployment on 0.0.0.0 or a public interface is a misconfiguration.",
        "tags": ["Network", "QuoteService", "Loopback"],
        "metadata": assumption_meta(
            "Scopes T-10 (0.0.0.0 exposure), T-14 (TCP exhaustion), and T-18 (UDP reflection) as misconfiguration risks rather than design flaws. If this assumption is violated, all three threats escalate to High."
        )
    },
    {
        "id": A2, "numericId": 2, "displayOrder": 2,
        "content": "The Cloudflare Worker is the only internet-facing component. All other components (CLI, QuoteService, SQLite) run on a developer workstation with no public network exposure.",
        "tags": ["Cloudflare", "Worker", "Trust-Boundary"],
        "metadata": assumption_meta(
            "Scopes XSS (T-11), Worker DoS (T-12), unauthenticated /reset (T-03), and /stats (T-21) as Worker-specific risks. If the CLI or QuoteService were ever internet-facing, the threat model would require a full revision."
        )
    },
    {
        "id": A3, "numericId": 3, "displayOrder": 3,
        "content": "The SQLite telemetry database contains only timing metrics and error strings — no PII, no credentials, no customer-identifiable data. It is readable only by the OS user running the CLI.",
        "tags": ["SQLite", "Telemetry", "Privacy", "Data-Classification"],
        "metadata": assumption_meta(
            "Scopes T-19 (error_msg) and T-20 (db_path traversal) as low-impact. If PII were ever stored (e.g. user names in telemetry), both threats would escalate to High and GDPR/privacy obligations would apply."
        )
    },
    {
        "id": A4, "numericId": 4, "displayOrder": 4,
        "content": "No long-lived secrets are committed to the repository. wrangler.local.toml (containing the real Cloudflare API token and D1 database_id) is gitignored. All credentials are injected at deploy time via environment variables.",
        "tags": ["Secrets", "Git", "Cloudflare", "Credentials"],
        "metadata": assumption_meta(
            "Scopes T-06 (credential leak) as a process risk rather than a design flaw. If this assumption breaks — e.g. a developer commits wrangler.local.toml — the Cloudflare account and D1 database are immediately at risk. Recommend git-secrets pre-commit hook as a defence-in-depth control."
        )
    },
    {
        "id": A5, "numericId": 5, "displayOrder": 5,
        "content": "The Worker /reset and /stats endpoints are intentionally unauthenticated for this demo deployment. A production deployment would gate both endpoints behind Cloudflare Access or a shared-secret header.",
        "tags": ["Worker", "Authentication", "Demo-Scope"],
        "metadata": assumption_meta(
            "Scopes T-03 (unauthenticated /reset) as High rather than Critical, and T-21 (unauthenticated /stats) as Low. In production, both endpoints must be authenticated. This assumption must be revisited before any production deployment."
        )
    },
    {
        "id": A6, "numericId": 6, "displayOrder": 6,
        "content": "GitHub Actions runners are ephemeral, isolated, and single-use. The workflow pins all third-party actions to full commit SHAs and declares permissions: contents: read at both workflow and job level.",
        "tags": ["CI-CD", "GitHub-Actions", "Least-Privilege", "Pinned-Actions"],
        "metadata": assumption_meta(
            "Scopes T-02 (poisoned pipeline), T-04 (mutable Actions tag), and T-08 (excessive CI permissions) as partially mitigated. SHA pinning and least-privilege permissions are currently implemented. Branch protection (M8) is the remaining recommended control."
        )
    },
]

# ── Mitigations ───────────────────────────────────────────────────────────────
# Each mitigation has: content (what to do), status (implemented/recommended),
# Comments metadata (why it matters + what it addresses), tags.
mitigations = [
    {
        "id": M1, "numericId": 1, "displayOrder": 1,
        "content": "Two-pass name sanitisation: (1) strip ANSI/VT100 escape sequences via regex, (2) remove non-printable bytes, (3) truncate to 100 chars. Applied in Greeting.__init__() and Worker _sanitise_name(). Empty result falls back to 'World'.",
        "status": RESOLVED,
        "tags": ["Input-Validation", "Implemented", "CLI", "Worker"],
        "metadata": mitigation_meta(
            "Addresses T-01 (ANSI injection) and T-03 (large name DoS). Implemented in both CLI and Worker. Reduces XSS surface for T-11 but html.escape() is still needed for HTML context (see M19)."
        )
    },
    {
        "id": M2, "numericId": 2, "displayOrder": 2,
        "content": "Add explicit range validation in TimeOfDay.from_hour(): raise ValueError if hour is not an integer in 0–23. Prevents silent fallthrough to NIGHT for out-of-range inputs.",
        "status": IDENTIFIED,
        "tags": ["Input-Validation", "Recommended", "CLI"],
        "metadata": mitigation_meta(
            "Addresses T-15 (datetime injection). Low priority but improves API contract correctness and prevents confusing behaviour in tests. One-line fix."
        )
    },
    {
        "id": M3, "numericId": 3, "displayOrder": 3,
        "content": "Gate Worker POST /reset behind Cloudflare Access policy or a shared-secret request header (e.g. X-Reset-Token). Log the caller's CF-Connecting-IP before executing the DELETE to create an audit trail.",
        "status": IDENTIFIED,
        "tags": ["Authentication", "Recommended", "Worker", "Audit-Trail"],
        "metadata": mitigation_meta(
            "Addresses T-03 (unauthenticated /reset). Currently the highest-exploitability unmitigated threat — a single curl command destroys all telemetry. Adding auth + audit logging directly addresses both Tampering and Repudiation STRIDE categories."
        )
    },
    {
        "id": M4, "numericId": 4, "displayOrder": 4,
        "content": "Pin all PyPI dependencies with SHA-256 hashes using pip-compile --generate-hashes. Enforce --require-hashes in CI pip install. This prevents installing any package not explicitly approved, regardless of version or name.",
        "status": IDENTIFIED,
        "tags": ["Supply-Chain", "Recommended", "CI-CD"],
        "metadata": mitigation_meta(
            "Addresses T-01 (supply chain colorama), T-07 (typosquatting), and T-09 (dependency confusion). Hash pinning is the single most effective supply chain control — it makes all three attacks impossible even if PyPI is compromised."
        )
    },
    {
        "id": M5, "numericId": 5, "displayOrder": 5,
        "content": "Run pip-audit -r requirements.txt --disable-pip --no-deps on every CI build to detect known CVEs in pinned dependencies before they reach production.",
        "status": RESOLVED,
        "tags": ["Supply-Chain", "Implemented", "CI-CD"],
        "metadata": mitigation_meta(
            "Addresses T-01 (supply chain colorama) and T-07 (typosquatting). Currently implemented. Catches known CVEs but does not prevent unknown malicious releases — hash pinning (M4) is the complementary control."
        )
    },
    {
        "id": M6, "numericId": 6, "displayOrder": 6,
        "content": "Pin all third-party GitHub Actions to full 40-character commit SHAs in ci.yml (e.g. actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683). Tags are mutable; SHAs are immutable.",
        "status": RESOLVED,
        "tags": ["CI-CD", "Implemented", "Supply-Chain"],
        "metadata": mitigation_meta(
            "Addresses T-04 (mutable Actions tag). Currently implemented. Makes it impossible for a compromised action maintainer to silently replace a trusted action — the SHA must be explicitly updated in ci.yml."
        )
    },
    {
        "id": M7, "numericId": 7, "displayOrder": 7,
        "content": "Declare permissions: contents: read at both workflow and job level in ci.yml. This is the minimum required for checkout and explicitly denies all other GitHub API write scopes.",
        "status": RESOLVED,
        "tags": ["CI-CD", "Implemented", "Least-Privilege"],
        "metadata": mitigation_meta(
            "Addresses T-08 (excessive CI permissions). Currently implemented. Prevents a compromised workflow step from writing to the repository, creating releases, or modifying issues."
        )
    },
    {
        "id": M8, "numericId": 8, "displayOrder": 8,
        "content": "Enable GitHub branch protection on main: require at least one PR review approval, require CI to pass, prevent force-push, and require approval before CI runs on first-time fork contributors.",
        "status": IDENTIFIED,
        "tags": ["CI-CD", "Recommended", "Branch-Protection"],
        "metadata": mitigation_meta(
            "Addresses T-02 (poisoned pipeline) and T-08 (excessive CI permissions). The most impactful remaining CI/CD control. Prevents a malicious fork PR from executing arbitrary code on the runner without human review."
        )
    },
    {
        "id": M9, "numericId": 9, "displayOrder": 9,
        "content": "QuoteService defaults to host='127.0.0.1' (loopback only). This is enforced in the constructor default. Document explicitly that host='0.0.0.0' must never be used without a firewall rule restricting inbound connections to trusted IPs.",
        "status": RESOLVED,
        "tags": ["Network", "Implemented", "QuoteService"],
        "metadata": mitigation_meta(
            "Addresses T-10 (0.0.0.0 exposure) and T-14 (TCP exhaustion). Loopback binding is the primary defence — it makes T-14 (TCP exhaustion) and T-18 (UDP reflection) unreachable from external networks."
        )
    },
    {
        "id": M10, "numericId": 10, "displayOrder": 10,
        "content": "Replace unbounded daemon thread spawning in QuoteService.start_tcp() with a ThreadPoolExecutor(max_workers=N). Reject new connections when the pool is full rather than spawning indefinitely.",
        "status": IDENTIFIED,
        "tags": ["DoS", "Recommended", "QuoteService"],
        "metadata": mitigation_meta(
            "Addresses T-14 (TCP connection exhaustion). Caps OS file descriptor and thread consumption. Recommended max_workers=50 for a developer workstation. Pairs with M9 (loopback binding) as defence-in-depth."
        )
    },
    {
        "id": M11, "numericId": 11, "displayOrder": 11,
        "content": "Use Linux capability CAP_NET_BIND_SERVICE (setcap cap_net_bind_service=+ep python3) or systemd socket activation to bind port 17 without running the QuoteService process as root.",
        "status": IDENTIFIED,
        "tags": ["Privilege", "Recommended", "QuoteService"],
        "metadata": mitigation_meta(
            "Addresses T-05 (root for port 17). Eliminates the need to run as root entirely. Alternatively, use a high port (>1023) for development — the default QuoteService port is already configurable."
        )
    },
    {
        "id": M12, "numericId": 12, "displayOrder": 12,
        "content": "Catch all socket exceptions in QuoteService._handle_tcp() and the UDP loop. Log at WARNING level server-side only. Never transmit stack traces, error messages, or internal state to connected clients.",
        "status": RESOLVED,
        "tags": ["Information-Disclosure", "Implemented", "QuoteService"],
        "metadata": mitigation_meta(
            "Addresses T-17 (log info disclosure). Currently implemented. Prevents reconnaissance via error messages. Stack traces remain in server logs — ensure log access is restricted to authorised operators."
        )
    },
    {
        "id": M13, "numericId": 13, "displayOrder": 13,
        "content": "Truncate error_msg to 500 characters before writing to SQLite in _MeasureContext.fail() and CfTelemetry.record(). This bounds disk growth and limits the detail of stack traces stored in the database.",
        "status": RESOLVED,
        "tags": ["SQLite", "Implemented", "Telemetry"],
        "metadata": mitigation_meta(
            "Addresses T-19 (unbounded error_msg). Currently implemented. Caps both disk exhaustion risk and the information value of stored stack traces. Complement with filesystem permissions (chmod 600) on greeting_telemetry.db."
        )
    },
    {
        "id": M14, "numericId": 14, "displayOrder": 14,
        "content": "Wrap db_path in pathlib.Path() at TelemetryStore construction to normalise traversal sequences. Default path is hardcoded relative to project root. If db_path is ever sourced from config or env vars, validate it is within an expected directory.",
        "status": RESOLVED,
        "tags": ["SQLite", "Implemented", "Path-Traversal"],
        "metadata": mitigation_meta(
            "Addresses T-20 (db_path traversal). Currently implemented for the default case. The additional env-var validation is recommended if TelemetryStore is ever made configurable via external input."
        )
    },
    {
        "id": M15, "numericId": 15, "displayOrder": 15,
        "content": "All D1 queries in CfTelemetry use parameterised statements via db.prepare().bind(). No user-controlled values are interpolated into SQL strings. This prevents SQL injection regardless of input content.",
        "status": RESOLVED,
        "tags": ["SQL-Injection", "Implemented", "Worker", "D1"],
        "metadata": mitigation_meta(
            "Addresses SQL injection risk in the Worker. Currently implemented. Parameterised queries are the only reliable SQL injection defence — string sanitisation alone is insufficient."
        )
    },
    {
        "id": M16, "numericId": 16, "displayOrder": 16,
        "content": "Store Cloudflare API token and D1 database_id only in gitignored wrangler.local.toml and environment variables. wrangler.toml uses a placeholder database_id. Add a git-secrets or pre-commit hook to block credential patterns before commit.",
        "status": IN_PROGRESS,
        "tags": ["Secrets", "Implemented", "Cloudflare", "Git"],
        "metadata": mitigation_meta(
            "Addresses T-06 (credential leak to git). gitignore and placeholder are implemented. git-secrets pre-commit hook is recommended but not yet added — marking as In-Progress. Once a secret is committed to a public repo, rotation is the only remediation."
        )
    },
    {
        "id": M17, "numericId": 17, "displayOrder": 17,
        "content": "QuoteProvider validates every quote at construction: length <= 512 chars (RFC 865 limit), non-empty string, non-empty corpus. Raises ValueError immediately on violation so misconfigured corpora fail fast.",
        "status": RESOLVED,
        "tags": ["Input-Validation", "Implemented", "QuoteProvider"],
        "metadata": mitigation_meta(
            "Addresses T-22 (corpus injection). Currently implemented. Prevents oversized payloads and empty corpus bugs. For custom corpora, additionally apply the same ANSI-stripping used in Greeting.__init__() to prevent terminal injection via quotes."
        )
    },
    {
        "id": M18, "numericId": 18, "displayOrder": 18,
        "content": "Enable Dependabot security alerts and automated version-update PRs on the GitHub repository. This surfaces newly disclosed CVEs in colorama and other dependencies between manual pip-audit runs.",
        "status": IDENTIFIED,
        "tags": ["Supply-Chain", "Recommended", "Dependabot"],
        "metadata": mitigation_meta(
            "Addresses T-01 (supply chain colorama) and T-07 (typosquatting). Complements M5 (pip-audit). Dependabot provides continuous monitoring; pip-audit provides point-in-time CI gating. Both are needed for comprehensive supply chain coverage."
        )
    },
    {
        "id": M19, "numericId": 19, "displayOrder": 19,
        "content": "Apply html.escape() to the name parameter before embedding it in any HTML context in the Worker response. Add a Content-Security-Policy response header (e.g. script-src 'self') to restrict inline script execution.",
        "status": IDENTIFIED,
        "tags": ["XSS", "Recommended", "Worker", "CSP"],
        "metadata": mitigation_meta(
            "Addresses T-11 (XSS via name reflection). The existing ANSI/non-printable sanitisation is necessary but not sufficient for HTML context — json.dumps() escapes quotes but HTML-entity and Unicode payloads can survive. html.escape() + CSP together provide defence-in-depth."
        )
    },
]

# ── Threats ───────────────────────────────────────────────────────────────────
threats = [
    # Critical → High
    {
        "id": T05, "numericId": 1, "displayOrder": 1,
        "statement": "A supply-chain attacker who publishes a malicious version of colorama (or a typosquatted package) can inject arbitrary code that executes on every developer machine and CI runner that installs it, leading to credential theft and data exfiltration, negatively impacting the integrity of the build pipeline and confidentiality of all developer secrets.",
        "threatSource": "Supply-chain attacker (external)",
        "prerequisites": "No hash pinning on PyPI dependencies; colorama installed via pip without --require-hashes",
        "threatAction": "publish a malicious or typosquatted colorama release that executes arbitrary code on pip install",
        "threatImpact": "credential theft, data exfiltration, full workstation and CI runner compromise",
        "impactedGoal": ["integrity", "confidentiality"],
        "impactedAssets": ["Build pipeline", "Developer workstation", "CI runner secrets"],
        "status": "threatIdentified",
        "tags": ["Supply-Chain", "CI-CD", "Colorama"],
        "metadata": threat_meta(["S","T","E"], "High",
            "Colorama has no hash pinning; a malicious release executes silently on pip install. Likelihood: Medium (PyPI compromises rising). Impact: Critical (full workstation + CI compromise). Score: High.")
    },
    {
        "id": T07, "numericId": 2, "displayOrder": 2,
        "statement": "A malicious contributor who submits a pull request from a fork can execute arbitrary code on the GitHub Actions runner via workflow_run or first-time contributor auto-approval, leading to exfiltration of repository secrets and poisoning of build artefacts, negatively impacting the integrity of the CI/CD pipeline.",
        "threatSource": "Malicious external contributor",
        "prerequisites": "No branch protection requiring approval before CI runs on fork PRs; public repository",
        "threatAction": "submit a fork PR that triggers the full CI workflow and executes arbitrary code on the runner",
        "threatImpact": "exfiltration of repository secrets, poisoning of build artefacts",
        "impactedGoal": ["integrity", "confidentiality"],
        "impactedAssets": ["CI/CD pipeline", "GitHub Actions runner", "Repository secrets"],
        "status": "threatIdentified",
        "tags": ["CI-CD", "GitHub-Actions", "Poisoned-Pipeline"],
        "metadata": threat_meta(["T","E","D"], "High",
            "Without branch protection requiring approval before CI runs on fork PRs, a first-time contributor triggers the full workflow. Likelihood: Medium (public repo). Impact: Critical (secrets + artefact tampering). Score: High.")
    },
    # High
    {
        "id": T04, "numericId": 3, "displayOrder": 3,
        "statement": "An unauthenticated attacker who can reach the Worker POST /reset endpoint can delete all telemetry records from the D1 database with a single HTTP request, leading to permanent loss of all operational metrics and audit history, negatively impacting the availability and integrity of telemetry data.",
        "threatSource": "Unauthenticated external attacker",
        "prerequisites": "Worker POST /reset endpoint has no authentication; attacker can reach the Cloudflare Worker URL",
        "threatAction": "send a single HTTP POST to /reset to delete all D1 telemetry records",
        "threatImpact": "permanent loss of all operational metrics and audit history",
        "impactedGoal": ["availability", "integrity"],
        "impactedAssets": ["D1 telemetry database", "Operational metrics"],
        "status": "threatIdentified",
        "tags": ["Worker", "Authentication", "Tampering"],
        "metadata": threat_meta(["T","R","D"], "High",
            "No auth on /reset; a single curl destroys all data. Likelihood: High (trivially exploitable). Impact: High (irreversible data loss). Score: High.")
    },
    {
        "id": T08, "numericId": 4, "displayOrder": 4,
        "statement": "A threat actor who compromises a GitHub Actions maintainer account can silently replace the code behind a mutable tag with malicious code, leading to arbitrary code execution on every subsequent CI run, negatively impacting the integrity of all build artefacts and confidentiality of CI secrets.",
        "threatSource": "Compromised GitHub Actions maintainer account",
        "prerequisites": "CI workflow references Actions by mutable tag rather than full commit SHA",
        "threatAction": "replace the code behind a mutable Actions tag with malicious code",
        "threatImpact": "arbitrary code execution on every subsequent CI run, exfiltration of CI secrets",
        "impactedGoal": ["integrity", "confidentiality"],
        "impactedAssets": ["CI/CD pipeline", "Build artefacts", "CI secrets"],
        "status": "threatIdentified",
        "tags": ["CI-CD", "GitHub-Actions", "Supply-Chain"],
        "metadata": threat_meta(["T","E"], "High",
            "Mutable tags are a well-known vector (e.g. tj-actions/changed-files 2025). SHA pinning (M6) is implemented. Likelihood: Low-Medium. Impact: Critical. Score: High.")
    },
    {
        "id": T13, "numericId": 5, "displayOrder": 5,
        "statement": "A local attacker or malicious dependency running while QuoteService starts can exploit the requirement to run as root to bind port 17, leading to full OS-level privilege escalation, negatively impacting the integrity and availability of the developer environment.",
        "threatSource": "Local attacker or malicious dependency",
        "prerequisites": "QuoteService must run as root to bind privileged port 17 (RFC 865); no capability-based alternative configured",
        "threatAction": "exploit the root process context to escalate privileges or pivot to other system resources",
        "threatImpact": "full OS-level privilege escalation, compromise of developer environment",
        "impactedGoal": ["integrity", "availability"],
        "impactedAssets": ["Developer workstation OS", "QuoteService process"],
        "status": "threatIdentified",
        "tags": ["Privilege-Escalation", "QuoteService", "Port-17"],
        "metadata": threat_meta(["E"], "High",
            "RFC 865 uses port 17 which requires root on Linux. Running a Python TCP server as root is a significant privilege escalation surface. Likelihood: Low (local only). Impact: Critical. Score: High.")
    },
    {
        "id": T19, "numericId": 6, "displayOrder": 6,
        "statement": "A developer who accidentally commits wrangler.local.toml containing the Cloudflare API token and D1 database_id to a public repository exposes credentials that allow an attacker to delete the D1 database or exhaust Cloudflare quota, negatively impacting the confidentiality of credentials and availability of the Worker.",
        "threatSource": "Developer (accidental insider)",
        "prerequisites": "wrangler.local.toml contains live credentials; no pre-commit hook blocking credential patterns",
        "threatAction": "accidentally commit wrangler.local.toml to a public repository via git add -f or IDE tooling",
        "threatImpact": "Cloudflare API token and D1 database_id exposed; attacker can delete database or exhaust quota",
        "impactedGoal": ["confidentiality", "availability"],
        "impactedAssets": ["Cloudflare API token", "D1 database", "Cloudflare account"],
        "status": "threatIdentified",
        "tags": ["Secrets", "Git", "Cloudflare", "Credentials"],
        "metadata": threat_meta(["I","D"], "High",
            "gitignore is the only control; a single git add -f bypasses it. Likelihood: Medium (developer error is common). Impact: High (Cloudflare account takeover). Score: High.")
    },
    # Medium
    {
        "id": T06, "numericId": 7, "displayOrder": 7,
        "statement": "An attacker who registers a typosquatted package name similar to colorama can cause a developer to install the malicious package via a pip install typo, leading to code execution on the developer workstation, negatively impacting the integrity of the development environment and confidentiality of local secrets.",
        "threatSource": "External attacker (typosquatter)",
        "prerequisites": "No hash pinning; developer makes a typo in pip install command",
        "threatAction": "register a typosquatted PyPI package name and wait for a developer to install it",
        "threatImpact": "arbitrary code execution on developer workstation, exfiltration of local secrets",
        "impactedGoal": ["integrity", "confidentiality"],
        "impactedAssets": ["Developer workstation", "Local secrets"],
        "status": "threatIdentified",
        "tags": ["Supply-Chain", "Typosquatting"],
        "metadata": threat_meta(["S","T","E"], "Medium",
            "Hash pinning (M4) eliminates this entirely; pip-audit (M5) catches known malicious packages. Likelihood: Low (requires developer typo). Impact: High. Score: Medium.")
    },
    {
        "id": T09, "numericId": 8, "displayOrder": 8,
        "statement": "A compromised workflow step or malicious PR running in CI with overly broad GitHub token permissions can write to the repository or create releases, leading to persistent supply chain compromise, negatively impacting the integrity of the repository and all downstream consumers.",
        "threatSource": "Compromised CI workflow step or malicious PR author",
        "prerequisites": "GitHub token has write permissions beyond contents: read",
        "threatAction": "use the overly broad GitHub token to write to the repository or create releases",
        "threatImpact": "persistent supply chain compromise, repository integrity violation",
        "impactedGoal": ["integrity"],
        "impactedAssets": ["GitHub repository", "Release artefacts", "Downstream consumers"],
        "status": "threatIdentified",
        "tags": ["CI-CD", "GitHub-Actions", "Least-Privilege"],
        "metadata": threat_meta(["T","E"], "Medium",
            "permissions: contents: read is implemented (M7). Residual risk from any future step requiring broader permissions. Likelihood: Low. Impact: High. Score: Medium.")
    },
    {
        "id": T10, "numericId": 9, "displayOrder": 9,
        "statement": "An attacker who registers a package with the same name as an internal package in a public registry can cause pip to install the malicious public version, leading to code execution in CI and on developer workstations, negatively impacting the integrity of the build pipeline.",
        "threatSource": "External attacker (dependency confusion)",
        "prerequisites": "Private package names are predictable; no hash pinning enforced",
        "threatAction": "register a public PyPI package with the same name as an internal package at a higher version",
        "threatImpact": "arbitrary code execution in CI and on developer workstations",
        "impactedGoal": ["integrity"],
        "impactedAssets": ["Build pipeline", "Developer workstation", "CI runner"],
        "status": "threatIdentified",
        "tags": ["Supply-Chain", "Dependency-Confusion"],
        "metadata": threat_meta(["S","T","E"], "Medium",
            "Relevant if private packages are ever added. All current deps are public PyPI packages. Hash pinning (M4) mitigates this. Likelihood: Low. Impact: High. Score: Medium.")
    },
    {
        "id": T11, "numericId": 10, "displayOrder": 10,
        "statement": "An attacker who crafts a name parameter containing HTML or JavaScript payloads can cause the Worker to reflect unsanitised content in its response, leading to XSS execution in any browser that renders the response as HTML, negatively impacting the confidentiality and integrity of end-user browser sessions.",
        "threatSource": "External attacker (web)",
        "prerequisites": "Worker reflects name parameter in response without html.escape(); no CSP header set",
        "threatAction": "craft a name parameter containing HTML/JavaScript payload and send it to the Worker",
        "threatImpact": "XSS execution in victim browser, session hijacking or credential theft",
        "impactedGoal": ["confidentiality", "integrity"],
        "impactedAssets": ["End-user browser session", "Worker response"],
        "status": "threatIdentified",
        "tags": ["XSS", "Worker", "Input-Validation"],
        "metadata": threat_meta(["T","I"], "Medium",
            "ANSI stripping is implemented but html.escape() and CSP are not yet applied (M19 is IDENTIFIED). JSON responses are not directly rendered as HTML, reducing exploitability. Likelihood: Low-Medium. Impact: Medium. Score: Medium.")
    },
    {
        "id": T21, "numericId": 11, "displayOrder": 11,
        "statement": "An attacker who sends a high volume of requests to the Worker can exhaust Cloudflare Workers free-tier CPU time or request quota, causing the Worker to return errors for all users, negatively impacting the availability of the greeting service.",
        "threatSource": "External attacker (DoS)",
        "prerequisites": "No rate limiting on the Worker; Cloudflare free-tier has CPU and request quotas",
        "threatAction": "send a high volume of HTTP requests to the Worker to exhaust free-tier quota",
        "threatImpact": "Worker returns errors for all users; service unavailability",
        "impactedGoal": ["availability"],
        "impactedAssets": ["Cloudflare Worker", "Greeting service"],
        "status": "threatIdentified",
        "tags": ["DoS", "Worker", "Cloudflare"],
        "metadata": threat_meta(["D"], "Medium",
            "No rate limiting is implemented. Likelihood: Medium (trivial to script). Impact: Medium (service unavailability, not data loss). Score: Medium.")
    },
    {
        "id": T22, "numericId": 12, "displayOrder": 12,
        "statement": "An attacker who injects malicious content into the QuoteProvider corpus can cause the CLI to display attacker-controlled text including ANSI escape sequences, leading to terminal manipulation or social engineering, negatively impacting the integrity of CLI output and user trust.",
        "threatSource": "Attacker with write access to the quote corpus",
        "prerequisites": "QuoteProvider corpus is sourced from an external or user-controlled location; no ANSI stripping on corpus entries",
        "threatAction": "inject ANSI escape sequences or social engineering text into the quote corpus",
        "threatImpact": "terminal manipulation, misleading CLI output, social engineering",
        "impactedGoal": ["integrity"],
        "impactedAssets": ["CLI output", "User trust"],
        "status": "threatIdentified",
        "tags": ["Input-Validation", "QuoteProvider", "Corpus"],
        "metadata": threat_meta(["T","I"], "Medium",
            "QuoteProvider validates length but does not strip ANSI from corpus entries. A malicious corpus could inject terminal control sequences. Likelihood: Low (requires corpus access). Impact: Medium. Score: Medium.")
    },
    {
        "id": T01, "numericId": 13, "displayOrder": 13,
        "statement": "An attacker who passes a name string containing ANSI/VT100 escape sequences to the CLI can manipulate terminal output, hiding text, changing colours, or triggering terminal commands, leading to misleading display or terminal state corruption, negatively impacting the integrity of CLI output.",
        "threatSource": "External attacker or malicious user input",
        "prerequisites": "CLI accepts name parameter from command-line arguments without prior ANSI stripping",
        "threatAction": "pass a name string containing ANSI/VT100 escape sequences to the CLI",
        "threatImpact": "terminal output manipulation, hidden text, terminal state corruption",
        "impactedGoal": ["integrity"],
        "impactedAssets": ["CLI terminal output"],
        "status": "threatIdentified",
        "tags": ["ANSI-Injection", "CLI", "Input-Validation"],
        "metadata": threat_meta(["T","I"], "Medium",
            "Two-pass ANSI stripping (M1) is implemented. Residual risk from edge-case sequences not covered by the current regex. Likelihood: Low (mitigated). Impact: Medium. Score: Medium.")
    },
    {
        "id": T12, "numericId": 14, "displayOrder": 14,
        "statement": "An attacker on the local network who can reach QuoteService (if misconfigured to bind 0.0.0.0) can open many simultaneous TCP connections to exhaust OS file descriptors and thread resources, causing the service to stop accepting connections, negatively impacting the availability of the QuoteService.",
        "threatSource": "Local network attacker",
        "prerequisites": "QuoteService misconfigured to bind 0.0.0.0; no ThreadPoolExecutor cap; attacker has local network access",
        "threatAction": "open many simultaneous TCP connections to exhaust OS file descriptors and thread resources",
        "threatImpact": "QuoteService stops accepting connections; service unavailability",
        "impactedGoal": ["availability"],
        "impactedAssets": ["QuoteService", "OS file descriptors"],
        "status": "threatIdentified",
        "tags": ["DoS", "QuoteService", "TCP"],
        "metadata": threat_meta(["D"], "Medium",
            "Loopback binding (M9) makes this unreachable externally. ThreadPoolExecutor cap (M10) is IDENTIFIED but not yet implemented. Likelihood: Low (requires misconfiguration). Impact: Medium. Score: Medium.")
    },
    # Low
    {
        "id": T02, "numericId": 15, "displayOrder": 15,
        "statement": "An attacker who can manipulate the system clock or pass a crafted hour value to TimeOfDay.from_hour() can cause the greeting to display an incorrect time-of-day salutation, leading to confusing output, negatively impacting the correctness and trustworthiness of the greeting.",
        "threatSource": "Local attacker or misconfigured system clock",
        "prerequisites": "No range validation on hour input to TimeOfDay.from_hour()",
        "threatAction": "pass an out-of-range hour value to TimeOfDay.from_hour() or manipulate the system clock",
        "threatImpact": "incorrect time-of-day salutation displayed; confusing output",
        "impactedGoal": ["integrity"],
        "impactedAssets": ["Greeting output", "TimeOfDay logic"],
        "status": "threatIdentified",
        "tags": ["Input-Validation", "TimeOfDay", "CLI"],
        "metadata": threat_meta(["T"], "Low",
            "No range validation on hour input; out-of-range values silently fall through to NIGHT. Impact is cosmetic only. Likelihood: Low. Impact: Low. Score: Low.")
    },
    {
        "id": T03, "numericId": 16, "displayOrder": 16,
        "statement": "An attacker who submits a name parameter exceeding the expected length limit can cause the CLI to allocate excessive memory or produce oversized output, leading to degraded performance or unexpected truncation behaviour, negatively impacting the availability and correctness of the CLI.",
        "threatSource": "External attacker or malicious user input",
        "prerequisites": "CLI accepts arbitrarily long name strings before truncation is applied",
        "threatAction": "submit a name parameter exceeding the 100-character truncation limit",
        "threatImpact": "excessive memory allocation, degraded performance, unexpected truncation",
        "impactedGoal": ["availability"],
        "impactedAssets": ["CLI process", "Greeting output"],
        "status": "threatIdentified",
        "tags": ["DoS", "CLI", "Input-Validation"],
        "metadata": threat_meta(["D"], "Low",
            "100-char truncation is implemented in M1. Impact is bounded by the truncation limit. Likelihood: Low. Impact: Low. Score: Low.")
    },
    {
        "id": T14, "numericId": 17, "displayOrder": 17,
        "statement": "An attacker who gains read access to server-side logs can extract internal error messages, stack traces, or module paths that reveal implementation details, leading to reconnaissance that aids more targeted attacks, negatively impacting the confidentiality of the system architecture.",
        "threatSource": "Attacker with read access to server logs",
        "prerequisites": "Server-side logs contain stack traces or internal paths; log files are not access-controlled",
        "threatAction": "read server-side log files to extract error messages, stack traces, and module paths",
        "threatImpact": "reconnaissance of system internals, aids more targeted attacks",
        "impactedGoal": ["confidentiality"],
        "impactedAssets": ["Server logs", "System architecture details"],
        "status": "threatIdentified",
        "tags": ["Information-Disclosure", "Logging", "QuoteService"],
        "metadata": threat_meta(["I"], "Low",
            "Errors are logged server-side only and never sent to clients (M12 implemented). Risk is limited to log file access control. Likelihood: Low. Impact: Low. Score: Low.")
    },
    {
        "id": T15, "numericId": 18, "displayOrder": 18,
        "statement": "An attacker who can reach the QuoteService UDP port (if misconfigured to bind 0.0.0.0) can spoof the source IP to redirect UDP quote responses to a victim, using the service as a low-bandwidth UDP reflection amplifier, negatively impacting the availability of the victim network.",
        "threatSource": "External attacker (network)",
        "prerequisites": "QuoteService misconfigured to bind 0.0.0.0 on UDP port; attacker can spoof source IP",
        "threatAction": "send spoofed UDP requests to QuoteService to redirect responses to a victim IP",
        "threatImpact": "victim network flooded with UDP quote responses; low-bandwidth amplification",
        "impactedGoal": ["availability"],
        "impactedAssets": ["Victim network", "QuoteService UDP port"],
        "status": "threatIdentified",
        "tags": ["UDP", "Reflection", "QuoteService"],
        "metadata": threat_meta(["D"], "Low",
            "Loopback binding (M9) makes this unreachable externally. Amplification factor is low. Likelihood: Very Low (requires misconfiguration). Impact: Low. Score: Low.")
    },
    {
        "id": T16, "numericId": 19, "displayOrder": 19,
        "statement": "An attacker who triggers exceptions in the CLI can cause verbose error messages or stack traces to be stored in the SQLite telemetry database, leading to unintended disclosure of internal paths and module structure to anyone with read access to the database file, negatively impacting the confidentiality of system internals.",
        "threatSource": "Attacker with read access to the SQLite telemetry database",
        "prerequisites": "Exceptions store verbose error_msg in SQLite; database file is readable by unintended parties",
        "threatAction": "trigger exceptions in the CLI to populate error_msg, then read the SQLite database",
        "threatImpact": "disclosure of internal paths, module structure, and stack traces",
        "impactedGoal": ["confidentiality"],
        "impactedAssets": ["SQLite telemetry database", "System internals"],
        "status": "threatIdentified",
        "tags": ["SQLite", "Information-Disclosure", "Telemetry"],
        "metadata": threat_meta(["I"], "Low",
            "error_msg is truncated to 500 chars (M13 implemented). Database is local and readable only by the OS user. Likelihood: Low. Impact: Low. Score: Low.")
    },
    {
        "id": T17, "numericId": 20, "displayOrder": 20,
        "statement": "An attacker who controls the db_path parameter passed to TelemetryStore can use path traversal sequences to redirect database writes to arbitrary filesystem locations, leading to file corruption or overwrite of sensitive files, negatively impacting the integrity of the filesystem.",
        "threatSource": "Attacker with control over TelemetryStore configuration",
        "prerequisites": "db_path is sourced from external or user-controlled input without validation",
        "threatAction": "pass a db_path containing path traversal sequences to TelemetryStore",
        "threatImpact": "database writes redirected to arbitrary filesystem locations, file corruption",
        "impactedGoal": ["integrity"],
        "impactedAssets": ["Filesystem", "TelemetryStore database"],
        "status": "threatIdentified",
        "tags": ["Path-Traversal", "SQLite", "TelemetryStore"],
        "metadata": threat_meta(["T"], "Low",
            "pathlib.Path() normalisation is implemented (M14). db_path is currently hardcoded, not user-controlled. Risk only materialises if db_path is ever sourced from external input. Likelihood: Very Low. Impact: Medium. Score: Low.")
    },
    {
        "id": T18, "numericId": 21, "displayOrder": 21,
        "statement": "An unauthenticated caller who can reach the Worker GET /stats endpoint can retrieve aggregate telemetry metrics (total greetings, error counts, timing data), leading to unintended disclosure of operational patterns, negatively impacting the confidentiality of service usage data.",
        "threatSource": "Unauthenticated external caller",
        "prerequisites": "Worker GET /stats endpoint has no authentication; endpoint is publicly reachable",
        "threatAction": "send an HTTP GET to /stats to retrieve aggregate telemetry metrics",
        "threatImpact": "disclosure of operational patterns (greeting counts, error rates, timing data)",
        "impactedGoal": ["confidentiality"],
        "impactedAssets": ["Telemetry metrics", "Operational data"],
        "status": "threatIdentified",
        "tags": ["Worker", "Authentication", "Information-Disclosure"],
        "metadata": threat_meta(["I"], "Low",
            "Intentionally unauthenticated per A5 (demo scope). Data exposed is aggregate metrics only - no PII, no credentials. Must be gated in production. Likelihood: High (trivially accessible). Impact: Low. Score: Low.")
    },
    {
        "id": T20, "numericId": 22, "displayOrder": 22,
        "statement": "An attacker who can write to the QuoteProvider corpus can inject oversized strings that bypass length validation or embed control characters, leading to unexpected CLI behaviour or terminal manipulation, negatively impacting the integrity of the greeting output.",
        "threatSource": "Attacker with write access to the QuoteProvider corpus",
        "prerequisites": "Corpus is sourced from an external or user-controlled location; no ANSI stripping on corpus entries",
        "threatAction": "inject oversized strings or control characters into the QuoteProvider corpus",
        "threatImpact": "unexpected CLI behaviour, terminal manipulation, integrity violation of greeting output",
        "impactedGoal": ["integrity"],
        "impactedAssets": ["Greeting output", "CLI terminal"],
        "status": "threatIdentified",
        "tags": ["Input-Validation", "QuoteProvider", "Corpus"],
        "metadata": threat_meta(["T","I"], "Low",
            "QuoteProvider validates length <= 512 chars (M17 implemented). Corpus is a static list in source - not user-controlled at runtime. Likelihood: Very Low. Impact: Low. Score: Low.")
    },
]

# ── Assumption Links ──────────────────────────────────────────────────────────
# type:"Threat"     → links assumption to a threat
# type:"Mitigation" → links assumption to a mitigation (populates Linked Mitigations column)
# Schema: { type, linkedId, assumptionId }  — NO "id" field
assumption_links = [
    # A1 (loopback only) → threats
    {"type": "Threat",     "linkedId": T11, "assumptionId": A1},
    {"type": "Threat",     "linkedId": T12, "assumptionId": A1},
    {"type": "Threat",     "linkedId": T15, "assumptionId": A1},
    # A1 → mitigations
    {"type": "Mitigation", "linkedId": M9,  "assumptionId": A1},
    {"type": "Mitigation", "linkedId": M10, "assumptionId": A1},
    # A2 (Worker is only internet-facing) → threats
    {"type": "Threat",     "linkedId": T04, "assumptionId": A2},
    {"type": "Threat",     "linkedId": T18, "assumptionId": A2},
    {"type": "Threat",     "linkedId": T21, "assumptionId": A2},
    {"type": "Threat",     "linkedId": T11, "assumptionId": A2},
    # A2 → mitigations
    {"type": "Mitigation", "linkedId": M3,  "assumptionId": A2},
    {"type": "Mitigation", "linkedId": M19, "assumptionId": A2},
    # A3 (SQLite no PII) → threats
    {"type": "Threat",     "linkedId": T16, "assumptionId": A3},
    {"type": "Threat",     "linkedId": T17, "assumptionId": A3},
    # A3 → mitigations
    {"type": "Mitigation", "linkedId": M13, "assumptionId": A3},
    {"type": "Mitigation", "linkedId": M14, "assumptionId": A3},
    # A4 (no secrets in git) → threats
    {"type": "Threat",     "linkedId": T19, "assumptionId": A4},
    # A4 → mitigations
    {"type": "Mitigation", "linkedId": M16, "assumptionId": A4},
    # A5 (/reset and /stats unauthenticated) → threats
    {"type": "Threat",     "linkedId": T04, "assumptionId": A5},
    {"type": "Threat",     "linkedId": T18, "assumptionId": A5},
    # A5 → mitigations
    {"type": "Mitigation", "linkedId": M3,  "assumptionId": A5},
    # A6 (CI runners ephemeral, actions pinned) → threats
    {"type": "Threat",     "linkedId": T07, "assumptionId": A6},
    {"type": "Threat",     "linkedId": T08, "assumptionId": A6},
    {"type": "Threat",     "linkedId": T09, "assumptionId": A6},
    # A6 → mitigations
    {"type": "Mitigation", "linkedId": M6,  "assumptionId": A6},
    {"type": "Mitigation", "linkedId": M7,  "assumptionId": A6},
    {"type": "Mitigation", "linkedId": M8,  "assumptionId": A6},
]

# ── Mitigation Links ──────────────────────────────────────────────────────────
# Schema: { mitigationId, linkedId }  where linkedId is a threat UUID
mitigation_links = [
    {"mitigationId": M1,  "linkedId": T01},
    {"mitigationId": M1,  "linkedId": T03},
    {"mitigationId": M1,  "linkedId": T11},
    {"mitigationId": M2,  "linkedId": T02},
    {"mitigationId": M3,  "linkedId": T04},
    {"mitigationId": M4,  "linkedId": T05},
    {"mitigationId": M4,  "linkedId": T06},
    {"mitigationId": M4,  "linkedId": T10},
    {"mitigationId": M5,  "linkedId": T05},
    {"mitigationId": M5,  "linkedId": T06},
    {"mitigationId": M6,  "linkedId": T08},
    {"mitigationId": M7,  "linkedId": T09},
    {"mitigationId": M8,  "linkedId": T07},
    {"mitigationId": M8,  "linkedId": T09},
    {"mitigationId": M9,  "linkedId": T12},
    {"mitigationId": M9,  "linkedId": T15},
    {"mitigationId": M10, "linkedId": T12},
    {"mitigationId": M11, "linkedId": T13},
    {"mitigationId": M12, "linkedId": T14},
    {"mitigationId": M13, "linkedId": T16},
    {"mitigationId": M14, "linkedId": T17},
    {"mitigationId": M16, "linkedId": T19},
    {"mitigationId": M17, "linkedId": T20},
    {"mitigationId": M17, "linkedId": T22},
    {"mitigationId": M18, "linkedId": T05},
    {"mitigationId": M18, "linkedId": T06},
    {"mitigationId": M19, "linkedId": T11},
]

# ── Assemble and write ────────────────────────────────────────────────────────
doc = {
    "schema": 1,
    "applicationInfo": {
        "name": "Greeting CLI + Cloudflare Worker",
        "description": "Python CLI greeting tool with Cloudflare Worker backend and D1 telemetry. Threat model v1.5.",
    },
    "assumptions":     assumptions,
    "mitigations":     mitigations,
    "threats":         threats,
    "assumptionLinks": assumption_links,
    "mitigationLinks": mitigation_links,
}

OUT.write_text(json.dumps(doc, indent=2))
print(f"Written {OUT}  ({len(threats)} threats, {len(mitigations)} mitigations, "
      f"{len(assumptions)} assumptions, {len(assumption_links)} assumptionLinks, "
      f"{len(mitigation_links)} mitigationLinks)")
