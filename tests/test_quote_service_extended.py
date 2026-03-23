"""
Extended tests for QuoteService.
Covers telemetry integration, error paths, and edge cases not in test_quote_service.py.
"""
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from quote_provider import QuoteProvider
from quote_service import QuoteService
from telemetry import TelemetryStore

_PORT = 19870  # distinct from other test files
_CORPUS = ("Extended quote one.\r\n", "Extended quote two.\r\n")


class TestQuoteServiceWithTelemetry(unittest.TestCase):
    """QuoteService records telemetry when a store is provided."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.store = TelemetryStore(db_path=Path(tmp.name))
        self.store.start()
        provider = QuoteProvider(quotes=_CORPUS, seed=0)
        self.service = QuoteService(provider=provider, port=_PORT, telemetry=self.store)
        self.thread = threading.Thread(target=self.service.start_tcp, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.service.stop()
        self.thread.join(timeout=3)
        self.store.stop()

    def test_tcp_request_recorded_in_telemetry(self):
        import sqlite3
        with socket.create_connection(("127.0.0.1", _PORT), timeout=3) as s:
            s.recv(1024)
        self.store.flush()
        with sqlite3.connect(self.store.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE event_type='tcp_request'"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][4], 1)  # success=1

    def test_multiple_tcp_requests_all_recorded(self):
        import sqlite3
        for _ in range(3):
            with socket.create_connection(("127.0.0.1", _PORT), timeout=3) as s:
                s.recv(1024)
        self.store.flush()
        with sqlite3.connect(self.store.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM events WHERE event_type='tcp_request'"
            ).fetchone()[0]
        self.assertEqual(count, 3)


class TestQuoteServiceUDPWithTelemetry(unittest.TestCase):
    """QuoteService UDP records telemetry when a store is provided."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.store = TelemetryStore(db_path=Path(tmp.name))
        self.store.start()
        provider = QuoteProvider(quotes=_CORPUS, seed=0)
        self.service = QuoteService(provider=provider, port=_PORT + 1, telemetry=self.store)
        self.thread = threading.Thread(target=self.service.start_udp, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.service.stop()
        self.thread.join(timeout=3)
        self.store.stop()

    def test_udp_request_recorded_in_telemetry(self):
        import sqlite3
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.sendto(b"", ("127.0.0.1", _PORT + 1))
            s.recvfrom(1024)
        self.store.flush()
        with sqlite3.connect(self.store.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE event_type='udp_request'"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][4], 1)  # success=1


class TestQuoteServiceNoTelemetry(unittest.TestCase):
    """QuoteService works correctly when no telemetry store is provided."""

    def setUp(self):
        provider = QuoteProvider(quotes=_CORPUS, seed=0)
        self.service = QuoteService(provider=provider, port=_PORT + 2)
        self.thread = threading.Thread(target=self.service.start_tcp, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.service.stop()
        self.thread.join(timeout=3)

    def test_tcp_works_without_telemetry(self):
        with socket.create_connection(("127.0.0.1", _PORT + 2), timeout=3) as s:
            data = s.recv(1024).decode("ascii")
        self.assertIn(data, _CORPUS)

    def test_telemetry_is_none_by_default(self):
        svc = QuoteService(port=_PORT + 2)
        self.assertIsNone(svc.telemetry)


class TestQuoteServiceStopBehavior(unittest.TestCase):
    """stop() lifecycle edge cases."""

    def test_stop_before_start_is_noop(self):
        svc = QuoteService(port=_PORT + 3)
        svc.stop()  # must not raise

    def test_stop_twice_is_idempotent(self):
        svc = QuoteService(port=_PORT + 3)
        svc.stop()
        svc.stop()  # must not raise

    def test_stop_event_set_after_stop(self):
        svc = QuoteService(port=_PORT + 3)
        svc.stop()
        self.assertTrue(svc._stop_event.is_set())

    def test_tcp_server_stops_within_timeout(self):
        provider = QuoteProvider(quotes=_CORPUS)
        svc = QuoteService(provider=provider, port=_PORT + 4)
        t = threading.Thread(target=svc.start_tcp, daemon=True)
        t.start()
        time.sleep(0.1)
        svc.stop()
        t.join(timeout=3)
        self.assertFalse(t.is_alive(), "TCP server did not stop within 3 seconds")

    def test_udp_server_stops_within_timeout(self):
        provider = QuoteProvider(quotes=_CORPUS)
        svc = QuoteService(provider=provider, port=_PORT + 5)
        t = threading.Thread(target=svc.start_udp, daemon=True)
        t.start()
        time.sleep(0.1)
        svc.stop()
        t.join(timeout=3)
        self.assertFalse(t.is_alive(), "UDP server did not stop within 3 seconds")


class TestQuoteServiceClientDataIgnored(unittest.TestCase):
    """RFC 865: server must ignore all client-sent data."""

    def setUp(self):
        provider = QuoteProvider(quotes=_CORPUS, seed=0)
        self.service = QuoteService(provider=provider, port=_PORT + 6)
        self.thread = threading.Thread(target=self.service.start_tcp, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.service.stop()
        self.thread.join(timeout=3)

    def test_large_client_payload_ignored(self):
        """Sending 64KB to the server must not affect the response."""
        with socket.create_connection(("127.0.0.1", _PORT + 6), timeout=3) as s:
            s.sendall(b"X" * 65536)
            data = s.recv(1024).decode("ascii")
        self.assertIn(data, _CORPUS)

    def test_binary_client_payload_ignored(self):
        """Binary garbage from client must not corrupt the response."""
        with socket.create_connection(("127.0.0.1", _PORT + 6), timeout=3) as s:
            s.sendall(bytes(range(256)))
            data = s.recv(1024).decode("ascii")
        self.assertIn(data, _CORPUS)
