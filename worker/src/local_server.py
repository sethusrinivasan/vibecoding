"""
local_server.py
~~~~~~~~~~~~~~~
Lightweight local HTTP development server for the Greeting Worker.

Runs the same routing logic as ``entry.py`` using Python's built-in
``http.server`` — no Node, no pywrangler, no Cloudflare account needed.

Usage::

    python3 worker/src/local_server.py           # http://localhost:8787
    python3 worker/src/local_server.py 9000      # custom port

Endpoints mirror the Worker exactly:

    GET  /                      greeting for "World"
    GET  /?name=Alice           greeting for "Alice"
    GET  /quote                 random quote
    GET  /stats?event=greeting  telemetry summary (in-memory, resets on restart)
    POST /reset                 wipe in-memory telemetry

Telemetry is stored in-memory (no D1 available locally).  For persistent
local telemetry use the main CLI: ``make run NAME="Alice"``.
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Bootstrap: add worker/src to path so imports resolve without installation
# ---------------------------------------------------------------------------
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from time_of_day import TimeOfDay
from quote_provider import QuoteProvider

# ---------------------------------------------------------------------------
# In-memory telemetry (replaces D1 for local dev)
# ---------------------------------------------------------------------------
_events: list[dict] = []


def _record(event_type: str, duration_ns: int, success: bool, error_msg: Optional[str] = None) -> None:
    _events.append({
        "event_type":  event_type,
        "duration_ns": duration_ns,
        "success":     success,
        "error_msg":   str(error_msg)[:500] if error_msg else None,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    })


def _stats_summary(event_type: str) -> dict:
    import statistics as _stats
    rows = [e for e in _events if e["event_type"] == event_type]
    if not rows:
        return {"label": f"historic:{event_type}", "count": 0}
    durations   = [r["duration_ns"] for r in rows]
    fault_count = sum(1 for r in rows if not r["success"])
    s = sorted(durations)
    n = len(s)

    def pct(p: int) -> float:
        idx = max(0, int((p / 100.0) * n) - 1)
        return round(s[min(idx, n - 1)], 3)

    return {
        "label":        f"historic:{event_type}",
        "count":        n,
        "success_rate": round(100.0 * (n - fault_count) / n, 1),
        "total_ns":     sum(s),
        "min_ns":       s[0],
        "mean_ns":      round(_stats.mean(s), 1),
        "median_ns":    round(_stats.median(s), 1),
        "p95_ns":       pct(95),
        "p99_ns":       pct(99),
        "max_ns":       s[-1],
        "fault_count":  fault_count,
    }


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
_ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
_SAFE_NAME_RE   = re.compile(r'[^\x20-\x7E]')
_MAX_NAME_LEN   = 100
_provider       = QuoteProvider()


def _sanitise_name(raw: str) -> str:
    s = _ANSI_ESCAPE_RE.sub('', str(raw))
    s = _SAFE_NAME_RE.sub('', s)[:_MAX_NAME_LEN]
    return s if s else "World"


def _build_greeting(name: str) -> dict:
    now      = datetime.now(timezone.utc)
    period   = TimeOfDay.from_hour(now.hour)
    time_str = now.strftime("%I:%M %p")
    quote    = _provider.get()
    return {
        "greeting":  f"{period.salutation}, {name}!  [{time_str}]",
        "period":    period.value,
        "color":     period.color,
        "quote":     quote.strip(),
        "timestamp": now.isoformat(),
    }


def _html_page(data: dict) -> str:
    color    = data.get("color", "#ffffff")
    greeting = data.get("greeting", "")
    quote    = data.get("quote", "")
    period   = data.get("period", "")
    ts       = data.get("timestamp", "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Greeting Service</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee;
           display: flex; align-items: center; justify-content: center;
           min-height: 100vh; margin: 0; }}
    .card {{ background: #16213e; border-radius: 12px; padding: 2rem 3rem;
             max-width: 600px; text-align: center; box-shadow: 0 4px 24px #0004; }}
    h1 {{ color: {color}; font-size: 2rem; margin: 0 0 .5rem; }}
    .quote {{ color: #aaa; font-style: italic; margin: 1rem 0; line-height: 1.6; }}
    .meta {{ color: #555; font-size: .8rem; margin-top: 1.5rem; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{greeting}</h1>
    <p class="quote">"{quote}"</p>
    <p class="meta">{period} &bull; {ts}</p>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class GreetingHandler(BaseHTTPRequestHandler):
    """Handles GET and POST requests, routing to the same logic as entry.py."""

    log_message = lambda self, fmt, *args: print(f"  {self.address_string()} {fmt % args}")

    def _send(self, body: str, status: int = 200, content_type: str = "application/json") -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _json(self, data: dict, status: int = 200) -> None:
        self._send(json.dumps(data, indent=2), status, "application/json")

    def _html(self, data: dict) -> None:
        self._send(_html_page(data), 200, "text/html;charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/reset":
            _events.clear()
            self.send_response(204)
            self.end_headers()
        else:
            self._json({"error": "Not found"}, 404)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path   = parsed.path
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        accept = self.headers.get("Accept", "")

        if path == "/stats":
            event_type = params.get("event", "greeting")
            self._json(_stats_summary(event_type))
            return

        if path == "/quote":
            self._json({"quote": _provider.get().strip()})
            return

        if path == "/":
            name = _sanitise_name(params.get("name", "World"))
            t_start = time.perf_counter_ns()
            try:
                data    = _build_greeting(name)
                success = True
                error   = None
            except Exception as exc:
                success = False
                error   = f"{type(exc).__name__}: {exc}"
                self._json({"error": "Internal error"}, 500)
                return
            finally:
                duration_ns = time.perf_counter_ns() - t_start
                _record("greeting", duration_ns, success, error)

            if "text/html" in accept:
                self._html(data)
            else:
                self._json(data)
            return

        self._json({"error": "Not found"}, 404)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    server = HTTPServer(("127.0.0.1", port), GreetingHandler)
    print(f"Greeting Worker (local dev) listening on http://127.0.0.1:{port}")
    print("  GET  /              — greeting")
    print("  GET  /?name=Alice   — named greeting")
    print("  GET  /quote         — random quote")
    print("  GET  /stats         — telemetry summary")
    print("  POST /reset         — wipe telemetry")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
