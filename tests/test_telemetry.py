"""
Unit and integration tests for TelemetryStore and StatsReporter.
"""
import time
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from telemetry import TelemetryStore
from stats import StatsReporter, StatsSummary


def _tmp_store() -> TelemetryStore:
    """Return a TelemetryStore backed by a fresh temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    store = TelemetryStore(db_path=Path(tmp.name))
    store.start()
    return store


class TestTelemetryStoreLifecycle(unittest.TestCase):

    def test_start_creates_db_file(self):
        store = _tmp_store()
        self.assertTrue(store.db_path.exists())
        store.stop()

    def test_double_start_is_safe(self):
        store = _tmp_store()
        store.start()  # second call — should be a no-op
        store.stop()

    def test_stop_before_start_is_safe(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        store = TelemetryStore(db_path=path)
        store.stop()  # should not raise

    def test_schema_created(self):
        store = _tmp_store()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertIn("events", tables)

    def test_reset_clears_all_rows(self):
        store = _tmp_store()
        for i in range(5):
            store.record("greeting", i * 1000)
        store.flush()
        store.reset()
        with sqlite3.connect(store.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.assertEqual(count, 0)
        store.stop()

    def test_reset_before_start_does_not_raise(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        store = TelemetryStore(db_path=path)
        store.reset()  # should create schema and clear — no raise

    def test_reset_preserves_schema(self):
        store = _tmp_store()
        store.record("greeting", 1000)
        store.flush()
        store.reset()
        # Should still be able to record after reset
        store.record("greeting", 2000)
        store.flush()
        with sqlite3.connect(store.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.assertEqual(count, 1)
        store.stop()

    def test_reset_resets_autoincrement(self):
        store = _tmp_store()
        store.record("greeting", 1000)
        store.flush()
        store.reset()
        store.record("greeting", 2000)
        store.flush()
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute("SELECT id FROM events").fetchone()
        # After reset, first new row should have id=1
        self.assertEqual(row[0], 1)
        store.stop()


class TestTelemetryStoreRecord(unittest.TestCase):

    def setUp(self):
        self.store = _tmp_store()

    def tearDown(self):
        self.store.stop()

    def _rows(self, event_type=None):
        """Fetch all rows, optionally filtered by event_type."""
        time.sleep(0.05)  # allow async writer to flush
        with sqlite3.connect(self.store.db_path) as conn:
            if event_type:
                return conn.execute(
                    "SELECT * FROM events WHERE event_type=?", (event_type,)
                ).fetchall()
            return conn.execute("SELECT * FROM events").fetchall()

    def test_record_success(self):
        self.store.record("greeting", 12500, success=True)
        rows = self._rows("greeting")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][4], 1)   # success=1
        self.assertIsNone(rows[0][5])     # error_msg=NULL

    def test_record_failure(self):
        self.store.record("greeting", 5000, success=False, error_msg="timeout")
        rows = self._rows("greeting")
        self.assertEqual(rows[0][4], 0)
        self.assertEqual(rows[0][5], "timeout")

    def test_record_multiple(self):
        for i in range(5):
            self.store.record("greeting", i * 1000)
        rows = self._rows("greeting")
        self.assertEqual(len(rows), 5)

    def test_measure_context_success(self):
        with self.store.measure("test_op"):
            time.sleep(0.01)
        rows = self._rows("test_op")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][4], 1)
        self.assertGreater(rows[0][3], 0)  # duration_ns > 0

    def test_measure_context_fail(self):
        with self.store.measure("test_op") as ctx:
            ctx.fail("something went wrong")
        rows = self._rows("test_op")
        self.assertEqual(rows[0][4], 0)
        self.assertEqual(rows[0][5], "something went wrong")

    def test_measure_captures_exception(self):
        try:
            with self.store.measure("test_op"):
                raise ValueError("boom")
        except ValueError:
            pass
        rows = self._rows("test_op")
        self.assertEqual(rows[0][4], 0)
        self.assertIn("ValueError", rows[0][5])

    def test_measure_does_not_suppress_exception(self):
        with self.assertRaises(RuntimeError):
            with self.store.measure("test_op"):
                raise RuntimeError("not suppressed")

    def test_record_after_stop_is_silent(self):
        self.store.stop()
        # Should not raise even though writer is stopped
        self.store.record("greeting", 1000)


class TestStatsReporter(unittest.TestCase):

    def setUp(self):
        self.store = _tmp_store()
        self.reporter = StatsReporter(self.store)

    def tearDown(self):
        self.store.stop()

    def test_session_summary_basic(self):
        s = self.reporter.session_summary([10, 20, 30])
        self.assertEqual(s.count, 3)
        self.assertAlmostEqual(s.mean_ns, 20.0)
        self.assertAlmostEqual(s.min_ns, 10)
        self.assertAlmostEqual(s.max_ns, 30)

    def test_session_summary_empty(self):
        s = self.reporter.session_summary([])
        self.assertEqual(s.count, 0)
        self.assertEqual(s.mean_ns, 0.0)

    def test_session_summary_single(self):
        s = self.reporter.session_summary([42])
        self.assertEqual(s.count, 1)
        self.assertAlmostEqual(s.median_ns, 42)
        self.assertAlmostEqual(s.p95_ns, 42)
        self.assertAlmostEqual(s.p99_ns, 42)

    def test_success_rate_all_ok(self):
        s = self.reporter.session_summary([1.0, 2.0], fault_count=0)
        self.assertAlmostEqual(s.success_rate, 100.0)

    def test_success_rate_with_faults(self):
        s = self.reporter.session_summary([1.0, 2.0, 3.0, 4.0], fault_count=1)
        self.assertAlmostEqual(s.success_rate, 75.0)

    def test_historic_summary_empty(self):
        s = self.reporter.historic_summary("nonexistent")
        self.assertEqual(s.count, 0)

    def test_historic_summary_from_db(self):
        for ns in [10, 20, 30, 40, 50]:
            self.store.record("greeting", ns)
        time.sleep(0.1)
        s = self.reporter.historic_summary("greeting")
        self.assertEqual(s.count, 5)
        self.assertAlmostEqual(s.mean_ns, 30.0)

    def test_format_summary_contains_key_fields(self):
        s = self.reporter.session_summary([10.0, 20.0])
        output = self.reporter.format_summary(s, label="test")
        self.assertIn("count", output)
        self.assertIn("mean", output)
        self.assertIn("p95", output)
        self.assertIn("p99", output)
        self.assertIn("test", output)

    def test_percentile_p95(self):
        # 100 values 1..100 ns; p95 should be near 95
        data = list(range(1, 101))
        s = self.reporter.session_summary(data)
        self.assertGreaterEqual(s.p95_ns, 94)
        self.assertLessEqual(s.p95_ns, 96)


class TestGreetingTelemetryIntegration(unittest.TestCase):
    """Verify Greeting.run() records telemetry asynchronously."""

    def test_run_records_greeting_event(self):
        from datetime import datetime
        from unittest.mock import patch
        from greeting import Greeting
        from quote_provider import QuoteProvider

        store = _tmp_store()
        g = Greeting(quote_provider=QuoteProvider(seed=0), telemetry=store)
        fake_now = datetime(2026, 3, 22, 9, 0)
        with patch('builtins.print'):
            g.run(now=fake_now)
        time.sleep(0.1)
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE event_type='greeting'"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][4], 1)  # success

    def test_run_without_telemetry_does_not_raise(self):
        from datetime import datetime
        from unittest.mock import patch
        from greeting import Greeting

        g = Greeting()
        with patch('builtins.print'):
            g.run(now=datetime(2026, 3, 22, 9, 0))  # no telemetry — should be fine


if __name__ == "__main__":
    unittest.main()
