"""
stats.py
~~~~~~~~
Provides the :class:`StatsReporter` class which queries the telemetry
SQLite database and computes statistical summaries of response times.

Two report types are supported:

* **Session** — statistics for a single list of durations (e.g. the
  current request batch).
* **Historic** — aggregate statistics across all recorded events of a
  given type, queried directly from the database.

Statistics computed
-------------------
- count, total_ns
- min, max, mean
- median (p50), p95, p99

All durations are stored and reported in **nanoseconds** for sub-millisecond
granularity.

Usage::

    from telemetry import TelemetryStore
    from stats import StatsReporter

    store = TelemetryStore()
    reporter = StatsReporter(store)

    summary = reporter.session_summary([12300, 8700, 15100])
    print(reporter.format_summary(summary, label="current request"))

    historic = reporter.historic_summary("greeting")
    print(reporter.format_summary(historic, label="all-time greeting"))
"""

import sqlite3
import statistics
from dataclasses import dataclass, field
from typing import Optional
from colorama import Fore, Style, init

init(autoreset=True)


@dataclass
class StatsSummary:
    """Holds computed statistics for a set of response-time measurements.

    All time values are in nanoseconds.
    """
    label: str
    count: int
    total_ns: int
    min_ns: int
    max_ns: int
    mean_ns: float
    median_ns: float
    p95_ns: int
    p99_ns: int
    fault_count: int = 0
    error_count: int = 0

    @property
    def success_rate(self) -> float:
        """Percentage of successful events (0–100)."""
        if self.count == 0:
            return 100.0
        return 100.0 * (self.count - self.fault_count - self.error_count) / self.count


class StatsReporter:
    """Computes and formats statistical summaries from telemetry data.

    :param store: The :class:`~telemetry.TelemetryStore` whose database
                  will be queried for historic summaries.
    """

    def __init__(self, store) -> None:
        #: Reference to the telemetry store (used for DB path).
        self.store = store

    # ------------------------------------------------------------------
    # Summary builders
    # ------------------------------------------------------------------

    def session_summary(
        self,
        durations_ns: list,
        label: str = "session",
        fault_count: int = 0,
        error_count: int = 0,
    ) -> StatsSummary:
        """Build a :class:`StatsSummary` from an in-memory list of durations.

        :param durations_ns: List of response times in nanoseconds.
        :param label: Human-readable label for the summary.
        :param fault_count: Number of fault events in this session.
        :param error_count: Number of error events in this session.
        :returns: A populated :class:`StatsSummary`.
        """
        return self._compute(durations_ns, label, fault_count, error_count)

    def historic_summary(self, event_type: str) -> StatsSummary:
        """Build a :class:`StatsSummary` by querying all stored events of
        the given type from the SQLite database.

        :param event_type: The event type label to aggregate
                           (e.g. ``"greeting"``, ``"tcp_request"``).
        :returns: A populated :class:`StatsSummary`.
        """
        rows = self._query(event_type)
        durations = [r[0] for r in rows]
        faults    = sum(1 for r in rows if r[1] == 0 and r[2] is None)
        errors    = sum(1 for r in rows if r[1] == 0 and r[2] is not None)
        return self._compute(durations, f"historic:{event_type}", faults, errors)

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_summary(self, summary: StatsSummary, label: str = None) -> str:
        """Render a :class:`StatsSummary` as a human-readable coloured string.

        :param summary: The summary to render.
        :param label: Override label (defaults to ``summary.label``).
        :returns: A multi-line formatted string ready for printing.
        """
        title = label or summary.label
        sep = "─" * 48

        # Colour the success rate: green ≥ 99%, yellow ≥ 95%, red otherwise
        sr = summary.success_rate
        if sr >= 99.0:
            sr_colour = Fore.GREEN
        elif sr >= 95.0:
            sr_colour = Fore.YELLOW
        else:
            sr_colour = Fore.RED

        def _fmt(ns) -> str:
            """Format nanoseconds as the most readable unit."""
            if ns >= 1_000_000_000:
                return f"{ns / 1_000_000_000:.3f} s"
            if ns >= 1_000_000:
                return f"{ns / 1_000_000:.3f} ms"
            if ns >= 1_000:
                return f"{ns / 1_000:.3f} µs"
            return f"{ns} ns"

        lines = [
            f"{Fore.CYAN}{sep}",
            f"  {Style.BRIGHT}Telemetry — {title}",
            f"{Fore.CYAN}{sep}",
            f"  count      : {summary.count}",
            f"  success    : {sr_colour}{sr:.1f}%{Fore.RESET}  "
            f"(faults={summary.fault_count}, errors={summary.error_count})",
            f"  total      : {_fmt(summary.total_ns)}",
            f"  min        : {_fmt(summary.min_ns)}",
            f"  mean       : {_fmt(summary.mean_ns)}",
            f"  median(p50): {_fmt(summary.median_ns)}",
            f"  p95        : {_fmt(summary.p95_ns)}",
            f"  p99        : {_fmt(summary.p99_ns)}",
            f"  max        : {_fmt(summary.max_ns)}",
            f"{Fore.CYAN}{sep}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute(
        self,
        durations: list,
        label: str,
        fault_count: int,
        error_count: int,
    ) -> StatsSummary:
        """Compute statistics from a list of durations (nanoseconds)."""
        if not durations:
            return StatsSummary(
                label=label, count=0, total_ns=0,
                min_ns=0, max_ns=0, mean_ns=0.0,
                median_ns=0.0, p95_ns=0, p99_ns=0,
                fault_count=fault_count, error_count=error_count,
            )

        sorted_d = sorted(durations)
        n = len(sorted_d)

        return StatsSummary(
            label=label,
            count=n,
            total_ns=sum(sorted_d),
            min_ns=sorted_d[0],
            max_ns=sorted_d[-1],
            mean_ns=statistics.mean(sorted_d),
            median_ns=statistics.median(sorted_d),
            p95_ns=self._percentile(sorted_d, 95),
            p99_ns=self._percentile(sorted_d, 99),
            fault_count=fault_count,
            error_count=error_count,
        )

    @staticmethod
    def _percentile(sorted_data: list[float], pct: int) -> float:
        """Return the *pct*-th percentile of a pre-sorted list."""
        if not sorted_data:
            return 0.0
        n = len(sorted_data)
        # Nearest-rank method
        idx = max(0, int((pct / 100.0) * n) - 1)
        return sorted_data[min(idx, n - 1)]

    def _query(self, event_type: str) -> list:
        """Query (duration_ns, success, error_msg) rows from the database."""
        try:
            with sqlite3.connect(self.store.db_path) as conn:
                cursor = conn.execute(
                    "SELECT duration_ns, success, error_msg "
                    "FROM events WHERE event_type = ? ORDER BY id",
                    (event_type,),
                )
                return cursor.fetchall()
        except sqlite3.Error as exc:
            import logging
            logging.getLogger(__name__).warning("Stats query failed: %s", exc)
            return []
