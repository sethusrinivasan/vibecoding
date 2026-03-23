#!/usr/bin/env python3
"""
Generate docs/dfd.svg — Data Flow Diagram, Greeting Application.
SVG output: vector format, infinitely scalable, crisp at any zoom level.
Optimised for A4 Landscape layout (297×210mm).

Layout: rankdir=LR, 5 trust-boundary columns left→right.
  TB-1 Internet | TB-2 CI/CD | TB-3 Cloudflare | TB-4 Workstation | TB-5 Secrets
Legend: HTML-table node, rank=sink, centered under the diagram.
"""
import graphviz, pathlib

OUT  = pathlib.Path("docs/dfd")
FONT = "Helvetica,Arial,sans-serif"
BG   = "white"
TXT  = "#111111"

# Trust boundary: (fill, border, label-colour, label)
TB = {
    1: ("#fff5f5", "#cc2222", "#cc2222", "TB-1  Untrusted Internet"),
    2: ("#f5fff5", "#1a6e1a", "#1a6e1a", "TB-2  CI/CD Pipeline\n(GitHub Actions)"),
    3: ("#eef3ff", "#1a3acc", "#1a3acc", "TB-3  Cloudflare Edge"),
    4: ("#f0fffd", "#0e6b5a", "#0e6b5a", "TB-4  Developer Workstation"),
    5: ("#fffbf0", "#996600", "#996600", "TB-5  Secrets / Config\n(gitignored)"),
}
SUB  = ("#f8f8f8", "#999999")
EXT_F, EXT_P = "#ffffff", "#444466"
PRC_F, PRC_P = "#dbeafe", "#1d4ed8"
STR_F, STR_P = "#ede9fe", "#5b21b6"
FU = "#cc2222"; FP = "#cc6600"; FI = "#166534"; FO = "#1e40af"; FS = "#92400e"

# ── Graph ─────────────────────────────────────────────────────────────────────
g = graphviz.Digraph(name="DFD", format="svg")
g.attr(
    rankdir="LR",
    bgcolor=BG,
    fontname=FONT, fontcolor=TXT, fontsize="11",
    # A4 landscape in inches = 11.69 × 8.27; leave margin → 11.0 × 7.5
    size="11.0,7.5!",
    ratio="fill",
    pad="0.35",
    splines="spline",
    nodesep="0.28",
    ranksep="0.95",
    compound="true",
)

def ext(g, nid, lbl):
    g.node(nid, label=lbl, shape="rectangle", style="filled",
           fillcolor=EXT_F, color=EXT_P, fontcolor=TXT, fontname=FONT,
           fontsize="8", penwidth="1.4", margin="0.10,0.06", peripheries="2")

def proc(g, nid, lbl):
    g.node(nid, label=lbl, shape="ellipse", style="filled",
           fillcolor=PRC_F, color=PRC_P, fontcolor=TXT, fontname=FONT,
           fontsize="8", penwidth="1.6", margin="0.10,0.06")

def store(g, nid, lbl):
    g.node(nid, label=lbl, shape="cylinder", style="filled",
           fillcolor=STR_F, color=STR_P, fontcolor=TXT, fontname=FONT,
           fontsize="8", penwidth="1.6", margin="0.10,0.06")

def flow(src, dst, lbl="", color=FI, style="solid", pw="1.2",
         ltail=None, lhead=None):
    a = dict(color=color, fontcolor=color, fontname=FONT, fontsize="7.5",
             style=style, penwidth=pw, arrowsize="0.6")
    if lbl:   a["label"] = f" {lbl} "
    if ltail: a["ltail"] = ltail
    if lhead: a["lhead"] = lhead
    g.edge(src, dst, **a)

def tb_attr(n):
    fill, pen, fc, lbl = TB[n]
    return dict(label=lbl, style="dashed,filled", fillcolor=fill,
                color=pen, fontcolor=fc, fontname=FONT,
                fontsize="9", penwidth="2.0")

# ── TB-1  Untrusted Internet ──────────────────────────────────────────────────
with g.subgraph(name="cluster_tb1") as c:
    c.attr(**tb_attr(1))
    ext(c, "http_client",    "HTTP Client\n(Browser / curl)\nEP-13, EP-14")
    ext(c, "tcp_udp_client", "TCP/UDP Client\n(RFC 865)\nEP-8, EP-9")
    ext(c, "pypi",           "PyPI Registry\nEP-4")

# ── TB-2  CI/CD Pipeline ─────────────────────────────────────────────────────
with g.subgraph(name="cluster_tb2") as c:
    c.attr(**tb_attr(2))
    ext(c,  "gh_action_code", "3rd-party Action\ncode  EP-6\n(SHA-pinned)")
    proc(c, "ci_runner",      "CI Runner\n(ubuntu-latest)")
    proc(c, "pip_install",    "pip install\n--require-hashes")
    proc(c, "pip_audit",      "pip-audit\n(CVE scan)")

# ── TB-3  Cloudflare Edge ─────────────────────────────────────────────────────
with g.subgraph(name="cluster_tb3") as c:
    c.attr(**tb_attr(3))
    proc(c,  "worker",       "Worker\nentry.py")
    proc(c,  "cf_telemetry", "CfTelemetry\ncf_telemetry.py")
    store(c, "d1_db",        "D1 Database\n(cloud telemetry)")

# ── TB-4  Developer Workstation ───────────────────────────────────────────────
with g.subgraph(name="cluster_tb4") as tb4:
    tb4.attr(**tb_attr(4))
    ext(tb4, "caller",   "__main__ / Caller\nEP-1, EP-2")
    ext(tb4, "os_clock", "System Clock\nEP-3")
    ext(tb4, "terminal", "Terminal\n(stdout)")

    with tb4.subgraph(name="cluster_tb4a") as c:
        c.attr(label="TB-4a  CLI Subsystem", style="solid,filled",
               fillcolor=SUB[0], color=SUB[1], fontcolor=TB[4][2],
               fontname=FONT, fontsize="8", penwidth="1.3")
        proc(c, "greeting",    "Greeting\ngreeting.py")
        proc(c, "time_of_day", "TimeOfDay\ntime_of_day.py")
        proc(c, "quote_prov",  "QuoteProvider\nquote_provider.py")

    with tb4.subgraph(name="cluster_tb4b") as c:
        c.attr(label="TB-4b  RFC 865 QuoteService\n(loopback 127.0.0.1 default)",
               style="solid,filled", fillcolor=SUB[0], color=SUB[1],
               fontcolor=TB[4][2], fontname=FONT, fontsize="8", penwidth="1.3")
        proc(c, "quote_svc", "QuoteService\nquote_service.py\nTCP+UDP port 17")

    with tb4.subgraph(name="cluster_tb4c") as c:
        c.attr(label="TB-4c  Local Telemetry", style="solid,filled",
               fillcolor=SUB[0], color=SUB[1], fontcolor=TB[4][2],
               fontname=FONT, fontsize="8", penwidth="1.3")
        proc(c,  "telemetry", "TelemetryStore\ntelemetry.py")
        proc(c,  "stats",     "StatsReporter\nstats.py")
        store(c, "sqlite_db", "SQLite\ngreeting_telemetry.db")

# ── TB-5  Secrets / Config ────────────────────────────────────────────────────
with g.subgraph(name="cluster_tb5") as c:
    c.attr(**tb_attr(5))
    store(c, "wrangler_cfg", "wrangler.local.toml\nCF API token\nD1 database_id")
    # Padding node so TB-5 has similar visual weight to other columns
    g.node("_tb5_pad", style="invis", width="0.01", height="0.01", label="")
    c.node("_tb5_pad")

# ── Column ordering: invisible high-weight edges keep L→R sequence ────────────
for src, dst in [("http_client", "ci_runner"),
                 ("ci_runner",   "worker"),
                 ("worker",      "greeting"),
                 ("greeting",    "wrangler_cfg")]:
    g.edge(src, dst, style="invis", weight="80")

# ── Data flows ────────────────────────────────────────────────────────────────
flow("http_client",    "worker",        "HTTPS /?name=",              FU, pw="1.9")
flow("worker",         "http_client",   "JSON / HTML",                FO, style="dashed")
flow("worker",         "cf_telemetry",  "record()",                   FI)
flow("cf_telemetry",   "d1_db",         "D1 INSERT",                  FI)
flow("d1_db",          "cf_telemetry",  "D1 SELECT",                  FI, style="dashed")
flow("cf_telemetry",   "worker",        "stats result",               FI, style="dashed")
flow("tcp_udp_client", "quote_svc",     "TCP/UDP\n⚠ if not loopback", FU, style="dashed", pw="1.4")
flow("quote_svc",      "tcp_udp_client","quote bytes",                FO, style="dashed")
flow("pypi",           "pip_install",   "packages  EP-4",             FP, pw="1.6")
flow("gh_action_code", "ci_runner",     "action code  EP-6",          FP, pw="1.6")
flow("pip_install",    "ci_runner",     "installed deps",             FI)
flow("pip_install",    "pip_audit",     "dep list",                   FI)
flow("pip_audit",      "ci_runner",     "CVE report",                 FI, style="dashed")
flow("caller",         "greeting",      "name: str  EP-1,2",          FU)
flow("os_clock",       "greeting",      "datetime.now()  EP-3",       FI)
flow("greeting",       "time_of_day",   "hour: int",                  FI)
flow("time_of_day",    "greeting",      "TimeOfDay enum",             FI, style="dashed")
flow("greeting",       "quote_prov",    "get()",                      FI)
flow("quote_prov",     "greeting",      "quote: str",                 FI, style="dashed")
flow("greeting",       "terminal",      "greeting + quote",           FO)
flow("greeting",       "telemetry",     "duration_ns, error_msg",     FI)
flow("telemetry",      "sqlite_db",     "INSERT (async)",             FI)
flow("sqlite_db",      "stats",         "SELECT metrics",             FI, style="dashed")
flow("stats",          "terminal",      "p50/p95/p99",                FO, style="dashed")
flow("quote_svc",      "quote_prov",    "get()",                      FI)
flow("quote_prov",     "quote_svc",     "quote: str",                 FI, style="dashed")
flow("wrangler_cfg",   "worker",        "CF token\n(deploy only)",    FS, style="dashed", pw="1.4")

# ── Legend — HTML table, rank=sink, centered ──────────────────────────────────
# Sized to span roughly the same width as the main diagram.
legend_html = (
    '<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="3" CELLPADDING="4" '
    'BGCOLOR="#f9f9f9" COLOR="#bbbbbb" STYLE="ROUNDED">'
    # Row 1: title
    '<TR><TD COLSPAN="5" ALIGN="CENTER">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="9" COLOR="#333333">'
    '<B>Legend</B></FONT></TD></TR>'
    # Row 2: node types + flow colours
    '<TR>'
    '<TD BGCOLOR="#ffffff" BORDER="2" COLOR="#444466" ALIGN="CENTER" WIDTH="90">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#111111">'
    'External Entity<BR/>(double border)</FONT></TD>'
    '<TD BGCOLOR="#dbeafe" BORDER="2" COLOR="#1d4ed8" ALIGN="CENTER" WIDTH="90">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#111111">'
    'Process<BR/>(ellipse)</FONT></TD>'
    '<TD BGCOLOR="#ede9fe" BORDER="2" COLOR="#5b21b6" ALIGN="CENTER" WIDTH="90">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#111111">'
    'Data Store<BR/>(cylinder)</FONT></TD>'
    '<TD COLSPAN="2" ALIGN="LEFT">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#cc2222">'
    '&#x2500;&#x2500; Untrusted boundary crossing</FONT><BR/>'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#cc6600">'
    '&#x2500;&#x2500; Partially-trusted crossing</FONT><BR/>'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#166534">'
    '&#x2500;&#x2500; Trusted internal flow</FONT><BR/>'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#1e40af">'
    '- - Response / output flow</FONT><BR/>'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#92400e">'
    '- - Secrets / config (deploy-time)</FONT>'
    '</TD></TR>'
    # Row 3: TB colour key
    '<TR>'
    '<TD BGCOLOR="#fff5f5" BORDER="2" COLOR="#cc2222" ALIGN="CENTER">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#cc2222">'
    'TB-1 Untrusted Internet</FONT></TD>'
    '<TD BGCOLOR="#f5fff5" BORDER="2" COLOR="#1a6e1a" ALIGN="CENTER">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#1a6e1a">'
    'TB-2 CI/CD Pipeline</FONT></TD>'
    '<TD BGCOLOR="#eef3ff" BORDER="2" COLOR="#1a3acc" ALIGN="CENTER">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#1a3acc">'
    'TB-3 Cloudflare Edge</FONT></TD>'
    '<TD BGCOLOR="#f0fffd" BORDER="2" COLOR="#0e6b5a" ALIGN="CENTER">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#0e6b5a">'
    'TB-4 Developer Workstation</FONT></TD>'
    '<TD BGCOLOR="#fffbf0" BORDER="2" COLOR="#996600" ALIGN="CENTER">'
    '<FONT FACE="Helvetica,Arial,sans-serif" POINT-SIZE="7.5" COLOR="#996600">'
    'TB-5 Secrets / Config</FONT></TD>'
    '</TR></TABLE>>'
)
g.node("legend", label=legend_html, shape="none", margin="0")

# Invisible sink anchors — pull legend under the main diagram, not just TB-5
g.node("_sink", style="invis", width="0", height="0", label="")
for anchor in ("terminal", "sqlite_db", "pip_audit", "d1_db", "wrangler_cfg"):
    g.edge(anchor, "_sink", style="invis", weight="2")
g.edge("_sink", "legend", style="invis", weight="2")
with g.subgraph() as s:
    s.attr(rank="sink")
    s.node("_sink")
    s.node("legend")

# ── Render ────────────────────────────────────────────────────────────────────
g.render(str(OUT), cleanup=True)
print(f"Written {OUT}.svg")
