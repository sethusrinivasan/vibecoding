"""
Extended tests for TelemetryStore.
Covers concurrency, error paths, and edge cases not in test_telemetry.py.
"""
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from telemetry import TelemetryStore


def _tmp_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    store = TelemetryStore(db_path=Path(tmp.name))
    store.start()
    return store


class TestTelemetryConcurrency(unittest.TestCase):
    """record() must be safe to call from multiple threads simultaneously."""

    def test_concurrent_records_all_persisted(self):
        store = _tmp_store()
        n_threads = 20
        n_per_thread = 10

        def worker():
            for i in range(n_per_thread):
                store.record("greeting", i * 1000, success=True)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        store.flush()
        store.stop()

        with sqlite3.connect(store.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.assertEqual(count, n_threads * n_per_thread)

    def test_concurrent_measure_contexts(self):
        store = _tmp_store()
        errors = []

        def worker():
            try:
                with store.measure("op"):
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        store.flush()
        store.stop()
        self.assertEqual(errors, [])

        with sqlite3.connect(store.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.assertEqual(count, 15)


class TestTelemetryErrorPaths(unittest.TestCase):
    """Error handling and edge cases."""

    def test_error_msg_truncated_via_measure_fail(self):
        """_MeasureContext.fail() truncates error_msg to 500 chars."""
        store = _tmp_store()
        with store.measure("greeting") as ctx:
            ctx.fail("E" * 10_000)
        store.flush()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute("SELECT error_msg FROM events").fetchone()
        self.assertLessEqual(len(row[0]), 500)

    def test_record_stores_full_error_msg(self):
        """record() stores error_msg as-is (truncation is caller's responsibility)."""
        store = _tmp_store()
        store.record("greeting", 1000, success=False, error_msg="short error")
        store.flush()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute("SELECT error_msg FROM events").fetchone()
        self.assertEqual(row[0], "short error")

    def test_unicode_in_error_msg_stored(self):
        store = _tmp_store()
        store.record("greeting", 1000, success=False, error_msg="Ünïcödé error: 日本語")
        store.flush()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute("SELECT error_msg FROM events").fetchone()
        self.assertIsNotNone(row[0])

    def test_zero_duration_stored(self):
        store = _tmp_store()
        store.record("greeting", 0, success=True)
        store.flush()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute("SELECT duration_ns FROM events").fetchone()
        self.assertEqual(row[0], 0)

    def test_very_large_duration_stored(self):
        store = _tmp_store()
        large_ns = 10 ** 15  # ~11.5 days in nanoseconds
        store.record("greeting", large_ns, success=True)
        store.flush()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute("SELECT duration_ns FROM events").fetchone()
        self.assertEqual(row[0], large_ns)

    def test_measure_records_duration_greater_than_zero(self):
        store = _tmp_store()
        with store.measure("op"):
            time.sleep(0.005)
        store.flush()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute("SELECT duration_ns FROM events").fetchone()
        self.assertGreater(row[0], 0)

    def test_flush_with_no_pending_events(self):
        """flush() on an empty queue must not block or raise."""
        store = _tmp_store()
        store.flush(timeout=1.0)  # should return immediately
        store.stop()

    def test_multiple_event_types_stored_independently(self):
        store = _tmp_store()
        store.record("greeting", 1000)
        store.record("tcp_request", 2000)
        store.record("udp_request", 3000)
        store.flush()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            types = {r[0] for r in conn.execute("SELECT DISTINCT event_type FROM events")}
        self.assertEqual(types, {"greeting", "tcp_request", "udp_request"})

    def test_index_exists_on_event_type(self):
        store = _tmp_store()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            indexes = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )}
        self.assertIn("idx_event_type", indexes)
