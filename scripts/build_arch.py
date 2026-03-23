#!/usr/bin/env python3
"""
Generate docs/arch.svg — Architecture Diagram, Greeting Application.
SVG output: vector format, crisp at any zoom level.

Two deployment targets shown side-by-side:
  Left  — CLI / Local (Python, SQLite, RFC 865 QuoteService)
  Right — Cloudflare Edge (Worker, D1, Wrangler deploy)

Shared layer at top: QuoteProvider corpus + TimeOfDay enum (used by both).
CI/CD pipeline shown at bottom spanning both targets.
"""
import graphviz, pathlib

OUT  = pathlib.Path("docs/arch")
FONT = "Helvetica,Arial,sans-serif"

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "white"
TXT      = "#111111"

# Layer fills
C_SHARED = ("#fffde7", "#f9a825")   # amber  — shared components
C_CLI    = ("#e8f5e9", "#2e7d32")   # green  — CLI / local
C_WORKER = ("#e3f2fd", "#1565c0")   # blue   — Cloudflare Worker
C_INFRA  = ("#fce4ec", "#c62828")   # red    — infrastructure / CI
C_SUB    = ("#f5f5f5", "#9e9e9e")   # grey   — sub-cluster

# Node fills
NF_CLASS  = "#dbeafe"; NB_CLASS  = "#1d4ed8"   # class / module (blue)
NF_ENUM   = "#ede9fe"; NB_ENUM   = "#5b21b6"   # enum (purple)
NF_STORE  = "#fef9c3"; NB_STORE  = "#854d0e"   # data store (yellow)
NF_EXT    = "#f0fdf4"; NB_EXT    = "#166534"   # external entity (green)
NF_INFRA  = "#fff1f2"; NB_INFRA  = "#be123c"   # infra / CI (rose)
NF_WORKER = "#eff6ff"; NB_WORKER = "#1e40af"   # worker entry (blue)

# Edge colours
EC_COMPOSE  = "#1d4ed8"   # composition / owns
EC_USES     = "#166534"   # uses / calls
EC_ASYNC    = "#854d0e"   # async write
EC_NETWORK  = "#be123c"   # network / external
EC_DEPLOY   = "#7c3aed"   # deploy / CI

# ── Graph ─────────────────────────────────────────────────────────────────────
g = graphviz.Digraph(name="Architecture", format="svg")
g.attr(
    rankdir="TB",
    bgcolor=BG,
    fontname=FONT, fontcolor=TXT, fontsize="11",
    size="14.0,10.0!",
    ratio="fill",
    pad="0.4",
    splines="polyline",
    nodesep="0.35",
    ranksep="0.7",
    compound="true",
)

# ── Node helpers ──────────────────────────────────────────────────────────────
def cls(g, nid, lbl, sub=""):
    full = f"{lbl}\n{sub}" if sub else lbl
    g.node(nid, label=full, shape="box", style="filled,rounded",
           fillcolor=NF_CLASS, color=NB_CLASS, fontcolor=TXT,
           fontname=FONT, fontsize="8.5", penwidth="1.6", margin="0.12,0.07")

def enm(g, nid, lbl, sub=""):
    full = f"«enum»\n{lbl}\n{sub}" if sub else f"«enum»\n{lbl}"
    g.node(nid, label=full, shape="box", style="filled,rounded",
           fillcolor=NF_ENUM, color=NB_ENUM, fontcolor=TXT,
           fontname=FONT, fontsize="8.5", penwidth="1.6", margin="0.12,0.07")

def store(g, nid, lbl, sub=""):
    full = f"{lbl}\n{sub}" if sub else lbl
    g.node(nid, label=full, shape="cylinder", style="filled",
           fillcolor=NF_STORE, color=NB_STORE, fontcolor=TXT,
           fontname=FONT, fontsize="8.5", penwidth="1.6", margin="0.12,0.07")

def ext(g, nid, lbl, sub=""):
    full = f"{lbl}\n{sub}" if sub else lbl
    g.node(nid, label=full, shape="rectangle", style="filled",
           fillcolor=NF_EXT, color=NB_EXT, fontcolor=TXT,
           fontname=FONT, fontsize="8.5", penwidth="1.6", margin="0.12,0.07",
           peripheries="2")

def infra(g, nid, lbl, sub=""):
    full = f"{lbl}\n{sub}" if sub else lbl
    g.node(nid, label=full, shape="box", style="filled",
           fillcolor=NF_INFRA, color=NB_INFRA, fontcolor=TXT,
           fontname=FONT, fontsize="8.5", penwidth="1.6", margin="0.12,0.07")

def edge(g, src, dst, lbl="", color=EC_USES, style="solid", pw="1.2",
         ltail=None, lhead=None, constraint="true"):
    a = dict(color=color, fontcolor=color, fontname=FONT, fontsize="7.5",
             style=style, penwidth=pw, arrowsize="0.55", constraint=constraint)
    if lbl:    a["label"] = f" {lbl} "
    if ltail:  a["ltail"] = ltail
    if lhead:  a["lhead"] = lhead
    g.edge(src, dst, **a)

def cluster_attr(fill, pen, lbl):
    return dict(label=lbl, style="dashed,filled", fillcolor=fill,
                color=pen, fontcolor=pen, fontname=FONT,
                fontsize="9.5", penwidth="2.0")

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 0 — Shared Components (top, spans both targets)
# ═══════════════════════════════════════════════════════════════════════════════
with g.subgraph(name="cluster_shared") as c:
    c.attr(**cluster_attr(C_SHARED[0], C_SHARED[1],
                          "Shared Components  (used by CLI and Worker)"))
    enm(c, "time_of_day",   "TimeOfDay",      "time_of_day.py\nMORNING/AFTERNOON/EVENING/NIGHT\n.salutation  .color")
    cls(c, "quote_provider","QuoteProvider",  "quote_provider.py\nShuffle-deck, 100+ RFC 865 quotes\n.get() → str")

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — CLI / Local Deployment  (left column)
# ═══════════════════════════════════════════════════════════════════════════════
with g.subgraph(name="cluster_cli") as cli:
    cli.attr(**cluster_attr(C_CLI[0], C_CLI[1], "CLI / Local Deployment"))

    # Entry
    ext(cli, "cli_caller", "__main__ / Caller", "python3 -m src.greeting Alice")

    # Core class
    cls(cli, "greeting",   "Greeting",          "greeting.py\n.build(now) → str\n.run(now) → None")

    # RFC 865 sub-cluster
    with cli.subgraph(name="cluster_qsvc") as q:
        q.attr(label="RFC 865 QuoteService  (TCP+UDP port 17)",
               style="solid,filled", fillcolor=C_SUB[0], color=C_SUB[1],
               fontcolor=C_CLI[1], fontname=FONT, fontsize="8.5", penwidth="1.3")
        cls(q, "quote_svc",  "QuoteService",   "quote_service.py\n.start_tcp()  .start_udp()\n.stop()")
        ext(q, "tcp_client", "TCP/UDP Client",  "RFC 865 port 17\n(loopback default)")

    # Telemetry sub-cluster
    with cli.subgraph(name="cluster_tel") as t:
        t.attr(label="Local Telemetry",
               style="solid,filled", fillcolor=C_SUB[0], color=C_SUB[1],
               fontcolor=C_CLI[1], fontname=FONT, fontsize="8.5", penwidth="1.3")
        cls(t, "telemetry",  "TelemetryStore", "telemetry.py\nAsync queue writer\n.record()  .measure()  .flush()")
        cls(t, "stats",      "StatsReporter",  "stats.py\n.session_summary()\n.historic_summary()\n.format_summary()")
        store(t, "sqlite",   "SQLite DB",       "greeting_telemetry.db\nevents(id, timestamp,\nevent_type, duration_ns,\nsuccess, error_msg)")

    # Terminal output
    ext(cli, "terminal",   "Terminal (stdout)", "colourised greeting\np50/p95/p99 stats")

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — Cloudflare Edge Deployment  (right column)
# ═══════════════════════════════════════════════════════════════════════════════
with g.subgraph(name="cluster_cf") as cf:
    cf.attr(**cluster_attr(C_WORKER[0], C_WORKER[1], "Cloudflare Edge Deployment"))

    # HTTP clients
    ext(cf, "browser",     "Browser / curl",    "HTTPS GET /?name=Alice\nAccept: text/html | application/json")

    # Worker entry
    g.node("worker", label="Worker  entry.py\nDefault.fetch(request)\nGET /  GET /quote\nGET /stats  POST /reset",
           shape="box", style="filled,rounded",
           fillcolor=NF_WORKER, color=NB_WORKER, fontcolor=TXT,
           fontname=FONT, fontsize="8.5", penwidth="2.0", margin="0.14,0.08")

    # CF Telemetry sub-cluster
    with cf.subgraph(name="cluster_cftel") as ct:
        ct.attr(label="Cloudflare Telemetry",
                style="solid,filled", fillcolor=C_SUB[0], color=C_SUB[1],
                fontcolor=C_WORKER[1], fontname=FONT, fontsize="8.5", penwidth="1.3")
        cls(ct, "cf_telemetry", "CfTelemetry",    "cf_telemetry.py\n.record()  .reset()\n.historic_summary()")
        store(ct, "d1_db",      "D1 Database",     "Cloudflare D1 (cloud)\nevents table\n(same schema as SQLite)")

    # Wrangler / deploy
    infra(cf, "wrangler_cfg", "wrangler.local.toml", "CF API token\nD1 database_id\n(gitignored)")

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — CI/CD Pipeline  (bottom, spans both)
# ═══════════════════════════════════════════════════════════════════════════════
with g.subgraph(name="cluster_ci") as ci:
    ci.attr(**cluster_attr(C_INFRA[0], C_INFRA[1], "CI/CD Pipeline  (GitHub Actions)"))
    infra(ci, "gh_push",    "git push / PR",       "GitHub")
    infra(ci, "ci_runner",  "CI Runner",            "ubuntu-latest\npython3 -m unittest\npytest / coverage")
    infra(ci, "pip_audit",  "pip-audit",            "CVE scan\n--require-hashes")
    infra(ci, "cf_deploy",  "wrangler deploy",      "--config wrangler.local.toml\nCloudflare Worker deploy")
    ext(ci,   "pypi",       "PyPI Registry",        "pip install\n--require-hashes")

# ═══════════════════════════════════════════════════════════════════════════════
# Rank constraints — keep layers top→bottom
# ═══════════════════════════════════════════════════════════════════════════════
with g.subgraph() as s:
    s.attr(rank="source")
    s.node("time_of_day")
    s.node("quote_provider")

with g.subgraph() as s:
    s.attr(rank="sink")
    s.node("gh_push")
    s.node("ci_runner")
    s.node("pip_audit")
    s.node("cf_deploy")
    s.node("pypi")

# ═══════════════════════════════════════════════════════════════════════════════
# Edges — CLI / Local
# ═══════════════════════════════════════════════════════════════════════════════
edge(g, "cli_caller",    "greeting",      "name: str",          EC_COMPOSE)
edge(g, "greeting",      "time_of_day",   "from_hour()",        EC_USES)
edge(g, "greeting",      "quote_provider","get()",              EC_USES)
edge(g, "quote_provider","quote_svc",     "TCP get()",          EC_NETWORK, style="dashed")
edge(g, "quote_svc",     "tcp_client",    "quote bytes",        EC_NETWORK, style="dashed")
edge(g, "greeting",      "telemetry",     "record(duration_ns)",EC_ASYNC,   style="dashed")
edge(g, "telemetry",     "sqlite",        "INSERT async",       EC_ASYNC,   style="dashed")
edge(g, "sqlite",        "stats",         "SELECT metrics",     EC_USES,    style="dashed")
edge(g, "stats",         "terminal",      "p50/p95/p99",        EC_USES)
edge(g, "greeting",      "terminal",      "greeting string",    EC_USES)

# ═══════════════════════════════════════════════════════════════════════════════
# Edges — Cloudflare Worker
# ═══════════════════════════════════════════════════════════════════════════════
edge(g, "browser",       "worker",        "HTTPS GET",          EC_NETWORK, pw="1.8")
edge(g, "worker",        "browser",       "JSON / HTML",        EC_NETWORK, style="dashed")
edge(g, "worker",        "time_of_day",   "from_hour()",        EC_USES,    constraint="false")
edge(g, "worker",        "quote_provider","get()",              EC_USES,    constraint="false")
edge(g, "worker",        "cf_telemetry",  "record()",           EC_ASYNC,   style="dashed")
edge(g, "cf_telemetry",  "d1_db",         "D1 INSERT",          EC_ASYNC,   style="dashed")
edge(g, "d1_db",         "cf_telemetry",  "D1 SELECT",          EC_USES,    style="dashed")
edge(g, "cf_telemetry",  "worker",        "stats dict",         EC_USES,    style="dashed")
edge(g, "wrangler_cfg",  "worker",        "deploy config",      EC_DEPLOY,  style="dashed")

# ═══════════════════════════════════════════════════════════════════════════════
# Edges — CI/CD
# ═══════════════════════════════════════════════════════════════════════════════
edge(g, "gh_push",   "ci_runner",  "trigger",           EC_DEPLOY)
edge(g, "pypi",      "ci_runner",  "pip install",       EC_NETWORK, pw="1.5")
edge(g, "ci_runner", "pip_audit",  "dep list",          EC_DEPLOY)
edge(g, "ci_runner", "cf_deploy",  "on: push main",     EC_DEPLOY)
edge(g, "cf_deploy", "worker",     "deploy",            EC_DEPLOY, pw="1.8")

# ═══════════════════════════════════════════════════════════════════════════════
# Legend
# ═══════════════════════════════════════════════════════════════════════════════
legend_html = (
    '<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="3" CELLPADDING="5" '
    'BGCOLOR="#fafafa" COLOR="#cccccc" STYLE="ROUNDED">'
    '<TR><TD COLSPAN="6" ALIGN="CENTER">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="9" COLOR="#333333">'
    '<B>Legend</B></FONT></TD></TR>'
    # Node types
    '<TR>'
    '<TD BGCOLOR="#dbeafe" BORDER="2" COLOR="#1d4ed8" ALIGN="CENTER" WIDTH="100">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5">Class / Module</FONT></TD>'
    '<TD BGCOLOR="#ede9fe" BORDER="2" COLOR="#5b21b6" ALIGN="CENTER" WIDTH="100">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5">«enum»</FONT></TD>'
    '<TD BGCOLOR="#fef9c3" BORDER="2" COLOR="#854d0e" ALIGN="CENTER" WIDTH="100">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5">Data Store</FONT></TD>'
    '<TD BGCOLOR="#f0fdf4" BORDER="2" COLOR="#166534" ALIGN="CENTER" WIDTH="100">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5">External Entity</FONT></TD>'
    '<TD BGCOLOR="#fff1f2" BORDER="2" COLOR="#be123c" ALIGN="CENTER" WIDTH="100">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5">Infra / CI</FONT></TD>'
    '<TD ALIGN="LEFT">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#1d4ed8">'
    '&#x2500;&#x2500; composition / owns</FONT><BR/>'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#166534">'
    '&#x2500;&#x2500; uses / calls</FONT><BR/>'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#854d0e">'
    '- - async write</FONT><BR/>'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#be123c">'
    '&#x2500;&#x2500; network / external</FONT><BR/>'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#7c3aed">'
    '- - deploy / CI</FONT>'
    '</TD></TR>'
    '</TABLE>>'
)
g.node("legend", label=legend_html, shape="none", margin="0")
g.edge("terminal", "legend", style="invis", weight="1")
g.edge("d1_db",    "legend", style="invis", weight="1")
with g.subgraph() as s:
    s.attr(rank="sink")
    s.node("legend")

# ── Render ────────────────────────────────────────────────────────────────────
g.render(str(OUT), cleanup=True)
print(f"Written {OUT}.svg")
