"""
entry.py
~~~~~~~~
Cloudflare Worker entry point for the Greeting service.

HTTP API
--------
GET  /                      — greeting for "World"
GET  /?name=Alice           — greeting for "Alice"
GET  /quote                 — random inspirational quote (RFC 865 corpus)
GET  /stats?event=greeting  — historic telemetry summary (JSON)
POST /reset                 — wipe all telemetry data (returns 204)

All responses are JSON by default.  Pass ``Accept: text/html`` to receive
a minimal HTML page with colour-coded output.

Cloudflare bindings required (wrangler.toml)
--------------------------------------------
- DB  — D1 database (greeting-telemetry)

Local development (without pywrangler)
---------------------------------------
Run the bundled local HTTP server::

    python3 worker/src/local_server.py          # serves on http://localhost:8787
    python3 worker/src/local_server.py 9000     # custom port
"""

import json
import re
import time
from datetime import datetime, timezone
from typing import Optional

from workers import Response, WorkerEntrypoint  # type: ignore[import]

from time_of_day import TimeOfDay
from quote_provider import QuoteProvider
from cf_telemetry import CfTelemetry

# ---------------------------------------------------------------------------
# Input sanitisation (mirrors src/greeting.py — T-01, T-03)
# ---------------------------------------------------------------------------
_ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
_SAFE_NAME_RE   = re.compile(r'[^\x20-\x7E]')
_MAX_NAME_LEN   = 100

# One shared QuoteProvider instance per isolate (stateful shuffle-deck)
_provider = QuoteProvider()


def _sanitise_name(raw: str) -> str:
    """Strip ANSI sequences and non-printable chars; enforce max length."""
    s = _ANSI_ESCAPE_RE.sub('', str(raw))
    s = _SAFE_NAME_RE.sub('', s)[:_MAX_NAME_LEN]
    return s if s else "World"


def _build_greeting(name: str, now: Optional[datetime] = None) -> dict:
    """Return a dict with greeting text, period, colour, quote, and timestamp."""
    if now is None:
        now = datetime.now(timezone.utc)
    period   = TimeOfDay.from_hour(now.hour)
    time_str = now.strftime("%I:%M %p")
    quote    = _provider.get()
    return {
        "greeting":  f"{period.salutation}, {name}!  [{time_str}]",
        "period":    period.value,
        "color":     period.color,
        "quote":     quote.strip(),
        "timestamp": now.isoformat(),
        "_name":     name,
    }


def _json_response(data: dict, status: int = 200) -> "Response":
    # Strip internal keys (prefixed with _) before serialising
    clean = {k: v for k, v in data.items() if not k.startswith("_")}
    return Response(
        json.dumps(clean),
        status=status,
        headers={"Content-Type": "application/json"},
    )


def _html_response(data: dict, refresh_secs: int = 60) -> "Response":
    """HTML page with colour-coded greeting, client/server time, and countdown refresh."""
    color    = data.get("color", "#ffffff")
    quote    = data.get("quote", "")
    server_ts = data.get("timestamp", "")
    name     = data.get("_name", "World")

    # Period salutations and their color map — mirrors TimeOfDay on the client
    # so the greeting heading can be corrected to the client's local time.
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{refresh_secs}">
  <title>Greeting Service</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee;
           display: flex; align-items: center; justify-content: center;
           min-height: 100vh; margin: 0; }}
    .card {{ background: #16213e; border-radius: 12px; padding: 2rem 3rem;
             max-width: 640px; width: 100%; text-align: center;
             box-shadow: 0 4px 24px #0004; }}
    h1 {{ font-size: 2rem; margin: 0 0 .5rem; }}
    .quote {{ color: #aaa; font-style: italic; margin: 1rem 0; line-height: 1.6; }}
    .times {{ display: flex; justify-content: center; gap: 2rem;
              margin-top: 1.5rem; flex-wrap: wrap; }}
    .time-box {{ background: #0d1b2a; border-radius: 8px; padding: .6rem 1.2rem;
                 font-size: .8rem; min-width: 180px; }}
    .time-box .label {{ color: #555; text-transform: uppercase;
                        letter-spacing: .08em; font-size: .7rem; margin-bottom: .25rem; }}
    .time-box .value {{ color: #ccc; font-variant-numeric: tabular-nums; }}
    .countdown {{ margin-top: 1.5rem; font-size: .85rem; color: #666; }}
    .countdown span {{ font-weight: bold; font-variant-numeric: tabular-nums; }}
  </style>
</head>
<body>
  <div class="card">
    <h1 id="greeting"></h1>
    <p class="quote">"{quote}"</p>
    <div class="times">
      <div class="time-box">
        <div class="label">Your local time</div>
        <div class="value" id="client-time">—</div>
        <div class="value" id="client-tz" style="color:#555;font-size:.7rem;margin-top:.2rem"></div>
      </div>
      <div class="time-box">
        <div class="label">Server time (UTC)</div>
        <div class="value" id="server-time">—</div>
      </div>
    </div>
    <p class="countdown">Next quote in <span id="cd" style="color:{color}">{refresh_secs}</span>s</p>
  </div>
  <script>
  (function() {{
    var REFRESH = {refresh_secs};
    var name    = {json.dumps(name)};
    var serverTs = {json.dumps(server_ts)};

    // Period boundaries (hour, 24h) → salutation + color
    var PERIODS = [
      {{ from:  5, to: 12, label: 'morning',   sal: 'Good morning',   color: '#ffb300' }},
      {{ from: 12, to: 17, label: 'afternoon',  sal: 'Good afternoon', color: '#ff7043' }},
      {{ from: 17, to: 21, label: 'evening',    sal: 'Good evening',   color: '#7e57c2' }},
      {{ from: 21, to: 24, label: 'night',      sal: 'Good night',     color: '#5c6bc0' }},
      {{ from:  0, to:  5, label: 'night',      sal: 'Good night',     color: '#5c6bc0' }},
    ];

    function periodFor(hour) {{
      for (var i = 0; i < PERIODS.length; i++) {{
        var p = PERIODS[i];
        if (hour >= p.from && hour < p.to) return p;
      }}
      return PERIODS[0];
    }}

    function fmt(d) {{
      var h = d.getHours(), m = d.getMinutes();
      var ampm = h >= 12 ? 'PM' : 'AM';
      var h12  = h % 12 || 12;
      return (h12 < 10 ? '0' : '') + h12 + ':' +
             (m  < 10 ? '0' : '') + m  + ' ' + ampm;
    }}

    function fmtFull(d) {{
      return d.toLocaleString(undefined, {{
        weekday: 'short', year: 'numeric', month: 'short',
        day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
      }});
    }}

    function fmtUTC(d) {{
      return d.toLocaleString('en-GB', {{
        weekday: 'short', year: 'numeric', month: 'short',
        day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZone: 'UTC', timeZoneName: 'short'
      }});
    }}

    // Render client-local greeting
    var now    = new Date();
    var period = periodFor(now.getHours());
    var h1     = document.getElementById('greeting');
    h1.style.color = period.color;
    h1.textContent = period.sal + ', ' + name + '!  [' + fmt(now) + ']';

    // Client time display
    document.getElementById('client-time').textContent = fmtFull(now);
    try {{
      document.getElementById('client-tz').textContent =
        Intl.DateTimeFormat().resolvedOptions().timeZone;
    }} catch(e) {{}}

    // Server time display — always shown in UTC, independent of client timezone
    try {{
      var sd = new Date(serverTs);
      document.getElementById('server-time').textContent = fmtUTC(sd);
    }} catch(e) {{
      document.getElementById('server-time').textContent = serverTs;
    }}

    // Countdown
    var secs = REFRESH;
    var cdEl = document.getElementById('cd');
    var iv = setInterval(function() {{
      secs -= 1;
      if (secs <= 0) {{ clearInterval(iv); cdEl.textContent = '0'; location.reload(); return; }}
      cdEl.textContent = secs;
    }}, 1000);
  }})();
  </script>
</body>
</html>"""
    return Response(html, status=200, headers={"Content-Type": "text/html;charset=utf-8"})


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------

class Default(WorkerEntrypoint):
    """Cloudflare Worker entry point — handles all incoming HTTP requests."""

    async def fetch(self, request) -> "Response":
        url    = request.url
        method = request.method.upper()

        # Parse path and query string from the URL
        if "?" in url:
            path, qs = url.split("?", 1)
        else:
            path, qs = url, ""

        # Strip scheme + host to get just the path
        path = "/" + path.split("/", 3)[-1] if path.count("/") >= 3 else "/"

        # Parse query params manually (no urllib in Workers runtime)
        params: dict[str, str] = {}
        for part in qs.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v.replace("+", " ")

        telemetry = CfTelemetry(getattr(self.env, "DB", None))

        # ----------------------------------------------------------------
        # POST /reset — wipe telemetry
        # ----------------------------------------------------------------
        if path == "/reset" and method == "POST":
            await telemetry.reset()
            return Response(None, status=204)

        # ----------------------------------------------------------------
        # GET /stats — historic telemetry summary
        # ----------------------------------------------------------------
        if path == "/stats" and method == "GET":
            event_type = params.get("event", "greeting")
            summary    = await telemetry.historic_summary(event_type)
            return _json_response(summary.to_dict())

        # ----------------------------------------------------------------
        # GET /quote — single random quote
        # ----------------------------------------------------------------
        if path == "/quote" and method == "GET":
            quote = _provider.get()
            return _json_response({"quote": quote.strip()})

        # ----------------------------------------------------------------
        # GET / — greeting (default route)
        # ----------------------------------------------------------------
        if method == "GET":
            raw_name = params.get("name", "World")
            name     = _sanitise_name(raw_name)

            t_start = time.perf_counter_ns()
            try:
                data = _build_greeting(name)
            except Exception as exc:
                duration_ns = time.perf_counter_ns() - t_start
                await telemetry.record(
                    "greeting", duration_ns, success=False,
                    error_msg=f"{type(exc).__name__}: {exc}"
                )
                return _json_response({"error": "Internal error"}, status=500)

            duration_ns = time.perf_counter_ns() - t_start
            await telemetry.record("greeting", duration_ns, success=True)

            # Return HTML if browser (Accept: text/html) or no explicit JSON request
            accept = ""
            try:
                accept = request.headers.get("Accept", "")
            except Exception:
                pass

            if "text/html" in accept or "application/json" not in accept:
                return _html_response(data)
            return _json_response(data)

        return _json_response({"error": "Not found"}, status=404)
