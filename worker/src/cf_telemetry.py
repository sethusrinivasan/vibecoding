"""
cf_telemetry.py
~~~~~~~~~~~~~~~
Cloudflare D1-backed telemetry adapter for use inside a Python Worker.
"""

import time
import logging
import statistics
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class CfStatsSummary:
    """Lightweight stats container returned by :class:`CfTelemetry`."""

    def __init__(
        self,
        label: str,
        count: int,
        total_ns: int,
        min_ns: int,
        max_ns: int,
        mean_ns: float,
        median_ns: float,
        p95_ns: int,
        p99_ns: int,
        fault_count: int = 0,
    ) -> None:
        self.label       = label
        self.count       = count
        self.total_ns    = total_ns
        self.min_ns      = min_ns
        self.max_ns      = max_ns
        self.mean_ns     = mean_ns
        self.median_ns   = median_ns
        self.p95_ns      = p95_ns
        self.p99_ns      = p99_ns
        self.fault_count = fault_count

    @property
    def success_rate(self) -> float:
        if self.count == 0:
            return 100.0
        return 100.0 * (self.count - self.fault_count) / self.count

    def to_dict(self) -> dict:
        return {
            "label":        self.label,
            "count":        self.count,
            "success_rate": round(self.success_rate, 1),
            "total_ns":     self.total_ns,
            "min_ns":       self.min_ns,
            "mean_ns":      round(self.mean_ns, 1),
            "median_ns":    round(self.median_ns, 1),
            "p95_ns":       self.p95_ns,
            "p99_ns":       self.p99_ns,
            "max_ns":       self.max_ns,
            "fault_count":  self.fault_count,
        }


def _percentile(sorted_data: list, pct: int) -> float:
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    idx = max(0, int((pct / 100.0) * n) - 1)
    return sorted_data[min(idx, n - 1)]


def _compute_summary(durations: list, label: str, fault_count: int = 0) -> CfStatsSummary:
    if not durations:
        return CfStatsSummary(label, 0, 0, 0, 0, 0.0, 0.0, 0, 0)
    s = sorted(durations)
    return CfStatsSummary(
        label=label,
        count=len(s),
        total_ns=sum(s),
        min_ns=s[0],
        max_ns=s[-1],
        mean_ns=statistics.mean(s),
        median_ns=statistics.median(s),
        p95_ns=_percentile(s, 95),
        p99_ns=_percentile(s, 99),
        fault_count=fault_count,
    )


def _rows_to_python(result) -> list:
    """Convert D1 result rows (JsProxy objects) to plain Python dicts.

    D1 returns JS objects via Pyodide's JsProxy. We use the object's
    own keys to extract values into a native Python dict.
    """
    rows = []
    try:
        js_rows = result.results
        for row in js_rows:
            try:
                # JsProxy supports attribute access — extract known columns
                rows.append({
                    "duration_ns": int(row.duration_ns),
                    "success":     bool(row.success),
                })
            except Exception:
                pass
    except Exception:
        pass
    return rows


class CfTelemetry:
    """D1-backed telemetry store for Cloudflare Workers."""

    def __init__(self, db=None) -> None:
        self._db = db

    async def record(
        self,
        event_type: str,
        duration_ns: int,
        success: bool = True,
        error_msg: Optional[str] = None,
    ) -> None:
        if self._db is None:
            return
        timestamp  = datetime.now(timezone.utc).isoformat()
        safe_error = str(error_msg)[:500] if error_msg else None
        try:
            if safe_error is not None:
                stmt  = self._db.prepare(
                    "INSERT INTO events (timestamp, event_type, duration_ns, success, error_msg) "
                    "VALUES (?, ?, ?, ?, ?)"
                )
                bound = stmt.bind(timestamp, event_type, duration_ns, int(success), safe_error)
            else:
                stmt  = self._db.prepare(
                    "INSERT INTO events (timestamp, event_type, duration_ns, success) "
                    "VALUES (?, ?, ?, ?)"
                )
                bound = stmt.bind(timestamp, event_type, duration_ns, int(success))
            await bound.run()
        except Exception as exc:
            logger.warning("D1 telemetry write failed: %s", exc)

    async def reset(self) -> None:
        if self._db is None:
            return
        try:
            await self._db.prepare("DELETE FROM events").run()
        except Exception as exc:
            logger.warning("D1 reset failed: %s", exc)

    async def historic_summary(self, event_type: str) -> CfStatsSummary:
        if self._db is None:
            return _compute_summary([], f"historic:{event_type}")
        try:
            stmt   = self._db.prepare(
                "SELECT duration_ns, success FROM events WHERE event_type = ? ORDER BY id"
            )
            result = await stmt.bind(event_type).run()
            rows   = _rows_to_python(result)
            durations   = [r["duration_ns"] for r in rows]
            fault_count = sum(1 for r in rows if not r["success"])
            return _compute_summary(durations, f"historic:{event_type}", fault_count)
        except Exception as exc:
            logger.warning("D1 stats query failed: %s", exc)
            return _compute_summary([], f"historic:{event_type}")
