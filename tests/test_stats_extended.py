"""
Extended tests for StatsReporter and StatsSummary.
Covers edge cases and boundary conditions not in test_telemetry.py.
"""
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from telemetry import TelemetryStore
from stats import StatsReporter, StatsSummary


def _tmp_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    store = TelemetryStore(db_path=Path(tmp.name))
    store.start()
    return store


class TestStatsSummarySuccessRate(unittest.TestCase):
    """StatsSummary.success_rate edge cases."""

    def test_success_rate_zero_count(self):
        s = StatsSummary("t", 0, 0, 0, 0, 0.0, 0.0, 0, 0)
        self.assertAlmostEqual(s.success_rate, 100.0)

    def test_success_rate_all_faults(self):
        s = StatsSummary("t", 4, 0, 0, 0, 0.0, 0.0, 0, 0, fault_count=4)
        self.assertAlmostEqual(s.success_rate, 0.0)

    def test_success_rate_mixed(self):
        s = StatsSummary("t", 10, 0, 0, 0, 0.0, 0.0, 0, 0, fault_count=3, error_count=2)
        self.assertAlmostEqual(s.success_rate, 50.0)

    def test_success_rate_boundary_99(self):
        s = StatsSummary("t", 100, 0, 0, 0, 0.0, 0.0, 0, 0, fault_count=1)
        self.assertAlmostEqual(s.success_rate, 99.0)

    def test_success_rate_boundary_95(self):
        s = StatsSummary("t", 100, 0, 0, 0, 0.0, 0.0, 0, 0, fault_count=5)
        self.assertAlmostEqual(s.success_rate, 95.0)


class TestStatsReporterPercentiles(unittest.TestCase):
    """Percentile boundary and edge cases."""

    def setUp(self):
        self.store = _tmp_store()
        self.reporter = StatsReporter(self.store)

    def tearDown(self):
        self.store.stop()

    def test_percentile_single_value(self):
        s = self.reporter.session_summary([999])
        self.assertEqual(s.p95_ns, 999)
        self.assertEqual(s.p99_ns, 999)
        self.assertEqual(s.min_ns, 999)
        self.assertEqual(s.max_ns, 999)

    def test_percentile_two_values(self):
        s = self.reporter.session_summary([100, 200])
        self.assertGreaterEqual(s.p95_ns, 100)
        self.assertLessEqual(s.p95_ns, 200)

    def test_percentile_large_dataset(self):
        data = list(range(1, 1001))  # 1..1000
        s = self.reporter.session_summary(data)
        self.assertGreaterEqual(s.p95_ns, 940)
        self.assertLessEqual(s.p95_ns, 960)
        self.assertGreaterEqual(s.p99_ns, 980)
        self.assertLessEqual(s.p99_ns, 1000)

    def test_total_ns_correct(self):
        data = [100, 200, 300]
        s = self.reporter.session_summary(data)
        self.assertEqual(s.total_ns, 600)

    def test_median_even_count(self):
        s = self.reporter.session_summary([10, 20, 30, 40])
        # median of [10,20,30,40] = 25.0
        self.assertAlmostEqual(s.median_ns, 25.0)

    def test_median_odd_count(self):
        s = self.reporter.session_summary([10, 20, 30])
        self.assertAlmostEqual(s.median_ns, 20.0)


class TestStatsReporterFormatSummary(unittest.TestCase):
    """format_summary output content and colour thresholds."""

    def setUp(self):
        self.store = _tmp_store()
        self.reporter = StatsReporter(self.store)

    def tearDown(self):
        self.store.stop()

    def test_format_contains_success_rate(self):
        s = self.reporter.session_summary([1000])
        out = self.reporter.format_summary(s)
        self.assertIn("success", out)

    def test_format_custom_label_overrides(self):
        s = self.reporter.session_summary([1000], label="original")
        out = self.reporter.format_summary(s, label="override")
        self.assertIn("override", out)

    def test_format_units_ns(self):
        s = self.reporter.session_summary([500])  # 500 ns
        out = self.reporter.format_summary(s)
        self.assertIn("ns", out)

    def test_format_units_us(self):
        s = self.reporter.session_summary([5_000])  # 5 µs
        out = self.reporter.format_summary(s)
        self.assertIn("µs", out)

    def test_format_units_ms(self):
        s = self.reporter.session_summary([5_000_000])  # 5 ms
        out = self.reporter.format_summary(s)
        self.assertIn("ms", out)

    def test_format_units_s(self):
        s = self.reporter.session_summary([2_000_000_000])  # 2 s
        out = self.reporter.format_summary(s)
        self.assertIn(" s", out)

    def test_format_fault_count_shown(self):
        s = self.reporter.session_summary([1000, 2000], fault_count=1)
        out = self.reporter.format_summary(s)
        self.assertIn("faults=1", out)


class TestStatsReporterHistoricQuery(unittest.TestCase):
    """historic_summary reads from DB correctly."""

    def setUp(self):
        self.store = _tmp_store()
        self.reporter = StatsReporter(self.store)

    def tearDown(self):
        self.store.stop()

    def test_historic_only_counts_matching_type(self):
        self.store.record("greeting", 1000)
        self.store.record("tcp_request", 2000)
        self.store.flush()
        s = self.reporter.historic_summary("greeting")
        self.assertEqual(s.count, 1)

    def test_historic_counts_faults(self):
        self.store.record("greeting", 1000, success=True)
        self.store.record("greeting", 2000, success=False, error_msg="err")
        self.store.flush()
        s = self.reporter.historic_summary("greeting")
        self.assertEqual(s.count, 2)
        self.assertGreater(s.fault_count + s.error_count, 0)

    def test_historic_summary_bad_db_path_returns_empty(self):
        """If DB is inaccessible, historic_summary returns empty summary gracefully."""
        from stats import StatsReporter as SR

        class FakeStore:
            db_path = Path("/nonexistent/path/db.sqlite")

        reporter = SR(FakeStore())
        s = reporter.historic_summary("greeting")
        self.assertEqual(s.count, 0)
