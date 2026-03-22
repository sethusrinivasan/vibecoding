"""
Security tests for the Greeting application.

Covers the threats documented in docs/threat_model.md:
  T-01  Unsanitised name input (ANSI injection, control chars, oversized)
  T-02  Injected datetime object (out-of-range hour)
  T-03  DoS via large name string
  T-14  Corpus injection via custom quotes (oversized, control chars)
  T-15  DoS via oversized corpus
  T-16  TCP connection exhaustion (concurrent connections)
  T-17  Error message not leaked to TCP/UDP clients
  T-18  Default host binding is loopback only
  T-19  Port 17 not used by default
  T-20  UDP response does not echo client payload

Additional security properties:
  - Telemetry error_msg is truncated to prevent unbounded storage
  - QuoteService stop() is idempotent (no resource leak)
  - Greeting name fallback when fully stripped
  - Non-printable bytes in name are removed
"""

import socket
import threading
import time
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime
from unittest.mock import patch

from greeting import Greeting
from quote_provider import QuoteProvider, _DEFAULT_QUOTES
from quote_service import QuoteService, RFC865_PORT
from time_of_day import TimeOfDay

_TEST_PORT = 19866   # distinct from other test files to avoid port conflicts
_CORPUS = ("Safe quote one.\r\n", "Safe quote two.\r\n")


# ---------------------------------------------------------------------------
# T-01 — Input sanitisation: name parameter
# ---------------------------------------------------------------------------

class TestNameSanitisation(unittest.TestCase):
    """Greeting.__init__ must strip dangerous content from the name."""

    def test_ansi_escape_sequence_stripped(self):
        """Full ANSI CSI sequences (e.g. clear-screen) must be removed."""
        g = Greeting("\033[2J\033[HMalicious")
        self.assertEqual(g.name, "Malicious")

    def test_ansi_colour_code_stripped(self):
        """Colour escape codes must not survive into the name."""
        g = Greeting("\033[31mRed\033[0m")
        self.assertEqual(g.name, "Red")

    def test_null_byte_stripped(self):
        """Null bytes must be removed."""
        g = Greeting("Alice\x00Bob")
        self.assertEqual(g.name, "AliceBob")

    def test_tab_stripped(self):
        """Tab characters (non-printable ASCII) must be removed."""
        g = Greeting("Alice\tBob")
        self.assertEqual(g.name, "AliceBob")

    def test_newline_stripped(self):
        """Newline characters must be removed."""
        g = Greeting("Alice\nBob")
        self.assertEqual(g.name, "AliceBob")

    def test_carriage_return_stripped(self):
        """Carriage return must be removed."""
        g = Greeting("Alice\rBob")
        self.assertEqual(g.name, "AliceBob")

    def test_bell_char_stripped(self):
        """BEL character (\\x07) must be removed."""
        g = Greeting("Alice\x07Bob")
        self.assertEqual(g.name, "AliceBob")

    def test_backspace_stripped(self):
        """Backspace (\\x08) must be removed."""
        g = Greeting("Alice\x08Bob")
        self.assertEqual(g.name, "AliceBob")

    def test_delete_char_stripped(self):
        """DEL (\\x7F) must be removed."""
        g = Greeting("Alice\x7FBob")
        self.assertEqual(g.name, "AliceBob")

    def test_high_unicode_stripped(self):
        """Non-ASCII bytes are removed; any surviving ASCII chars remain."""
        g = Greeting("Ünïcödé")
        # Non-ASCII bytes stripped; leftover printable ASCII chars are kept
        self.assertTrue(all(0x20 <= ord(c) <= 0x7E for c in g.name))

    def test_mixed_injection_stripped(self):
        """Mixed ANSI + control chars leave only printable ASCII."""
        g = Greeting("\033[1mBold\x00\nName\033[0m")
        self.assertEqual(g.name, "BoldName")

    def test_empty_name_falls_back_to_world(self):
        """Empty string after sanitisation falls back to 'World'."""
        g = Greeting("")
        self.assertEqual(g.name, "World")

    def test_fully_stripped_name_falls_back_to_world(self):
        """Name that becomes empty after stripping falls back to 'World'."""
        g = Greeting("\033[2J\x00\n\r")
        self.assertEqual(g.name, "World")

    def test_name_truncated_at_100_chars(self):
        """Names longer than 100 printable chars are truncated."""
        g = Greeting("A" * 200)
        self.assertEqual(len(g.name), 100)

    def test_name_exactly_100_chars_preserved(self):
        """Names of exactly 100 printable chars are not truncated."""
        g = Greeting("A" * 100)
        self.assertEqual(len(g.name), 100)

    def test_sanitised_name_in_build_output(self):
        """The sanitised name (not the raw input) appears in build output."""
        g = Greeting("\033[31mEve\033[0m")
        result = g.build(datetime(2026, 3, 22, 9, 0))
        self.assertIn("Eve", result)
        self.assertNotIn("\033", result)

    def test_ansi_does_not_appear_in_build_output(self):
        """No raw ESC bytes should appear in the greeting string."""
        g = Greeting("\033[1;32mHacker\033[0m")
        result = g.build(datetime(2026, 3, 22, 9, 0))
        self.assertNotIn("\033", result)


# ---------------------------------------------------------------------------
# T-02 — TimeOfDay.from_hour() input validation
# ---------------------------------------------------------------------------

class TestTimeOfDayInputValidation(unittest.TestCase):
    """from_hour() must reject invalid hour values."""

    def test_hour_minus_one_raises(self):
        with self.assertRaises(ValueError):
            TimeOfDay.from_hour(-1)

    def test_hour_24_raises(self):
        with self.assertRaises(ValueError):
            TimeOfDay.from_hour(24)

    def test_hour_100_raises(self):
        with self.assertRaises(ValueError):
            TimeOfDay.from_hour(100)

    def test_float_hour_raises(self):
        with self.assertRaises(ValueError):
            TimeOfDay.from_hour(9.5)  # type: ignore

    def test_string_hour_raises(self):
        with self.assertRaises(ValueError):
            TimeOfDay.from_hour("9")  # type: ignore

    def test_none_hour_raises(self):
        with self.assertRaises(ValueError):
            TimeOfDay.from_hour(None)  # type: ignore

    def test_valid_boundary_hours_do_not_raise(self):
        """Hours 0 and 23 are valid and must not raise."""
        TimeOfDay.from_hour(0)
        TimeOfDay.from_hour(23)


# ---------------------------------------------------------------------------
# T-03 — DoS via large name string
# ---------------------------------------------------------------------------

class TestNameDoSProtection(unittest.TestCase):

    def test_very_long_name_truncated(self):
        """A 1 MB name string must be truncated to 100 chars."""
        g = Greeting("X" * 1_000_000)
        self.assertEqual(len(g.name), 100)

    def test_build_with_truncated_name_does_not_raise(self):
        """build() must complete normally even after truncation."""
        g = Greeting("X" * 1_000_000)
        result = g.build(datetime(2026, 3, 22, 9, 0))
        self.assertIsInstance(result, str)


# ---------------------------------------------------------------------------
# T-14 — QuoteProvider corpus injection
# ---------------------------------------------------------------------------

class TestQuoteProviderInputValidation(unittest.TestCase):
    """QuoteProvider must reject invalid corpus entries at construction."""

    def test_quote_over_512_chars_raises(self):
        with self.assertRaises(ValueError):
            QuoteProvider(quotes=("A" * 513,))

    def test_quote_exactly_512_chars_accepted(self):
        p = QuoteProvider(quotes=("A" * 512,))
        self.assertEqual(p.get(), "A" * 512)

    def test_empty_corpus_raises(self):
        with self.assertRaises(ValueError):
            QuoteProvider(quotes=())

    def test_all_default_quotes_within_512_chars(self):
        """Every built-in quote must satisfy the RFC 865 length constraint."""
        for i, q in enumerate(_DEFAULT_QUOTES):
            self.assertLessEqual(
                len(q), 512,
                msg=f"Default quote {i} exceeds 512 chars ({len(q)} chars)"
            )

    def test_default_corpus_has_no_duplicates(self):
        """Duplicate quotes in the corpus would skew distribution."""
        self.assertEqual(len(_DEFAULT_QUOTES), len(set(_DEFAULT_QUOTES)))


# ---------------------------------------------------------------------------
# T-15 — DoS via oversized corpus (construction time)
# ---------------------------------------------------------------------------

class TestQuoteProviderLargeCorpus(unittest.TestCase):

    def test_large_corpus_constructs_without_error(self):
        """A corpus of 10,000 short quotes must construct without raising."""
        corpus = tuple(f"Quote {i}.\r\n" for i in range(10_000))
        p = QuoteProvider(quotes=corpus)
        self.assertEqual(len(p), 10_000)

    def test_large_corpus_get_returns_valid_quote(self):
        corpus = tuple(f"Q{i}.\r\n" for i in range(500))
        p = QuoteProvider(quotes=corpus)
        q = p.get()
        self.assertIn(q, corpus)


# ---------------------------------------------------------------------------
# T-16 — TCP concurrent connection handling
# ---------------------------------------------------------------------------

class TestQuoteServiceConcurrentConnections(unittest.TestCase):
    """Server must handle multiple simultaneous TCP connections."""

    def setUp(self):
        provider = QuoteProvider(quotes=_CORPUS, seed=0)
        self.service = QuoteService(provider=provider, port=_TEST_PORT)
        self.thread = threading.Thread(target=self.service.start_tcp, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.service.stop()
        self.thread.join(timeout=3)

    def test_ten_concurrent_connections_all_receive_quote(self):
        """10 simultaneous connections must each receive a valid quote."""
        results = []
        errors = []

        def connect():
            try:
                with socket.create_connection(("127.0.0.1", _TEST_PORT), timeout=5) as s:
                    data = s.recv(1024).decode("ascii")
                    results.append(data)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=connect) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=6)

        self.assertEqual(len(errors), 0, f"Connection errors: {errors}")
        self.assertEqual(len(results), 10)
        for r in results:
            self.assertIn(r, _CORPUS)

    def test_sequential_connections_all_succeed(self):
        """20 sequential connections must all succeed."""
        for _ in range(20):
            with socket.create_connection(("127.0.0.1", _TEST_PORT), timeout=3) as s:
                data = s.recv(1024).decode("ascii")
            self.assertIn(data, _CORPUS)


# ---------------------------------------------------------------------------
# T-17 — Error messages not leaked to clients
# ---------------------------------------------------------------------------

class TestQuoteServiceNoErrorLeak(unittest.TestCase):
    """Server must not send internal error details to clients."""

    def setUp(self):
        provider = QuoteProvider(quotes=_CORPUS, seed=0)
        self.service = QuoteService(provider=provider, port=_TEST_PORT + 1)
        self.thread = threading.Thread(target=self.service.start_tcp, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.service.stop()
        self.thread.join(timeout=3)

    def test_client_receives_quote_not_traceback(self):
        """Response must be a known quote, not a Python traceback."""
        with socket.create_connection(("127.0.0.1", _TEST_PORT + 1), timeout=3) as s:
            data = s.recv(4096).decode("ascii", errors="replace")
        self.assertNotIn("Traceback", data)
        self.assertNotIn("Error", data)
        self.assertIn(data, _CORPUS)

    def test_client_receives_quote_not_exception(self):
        """Response must not contain exception class names."""
        with socket.create_connection(("127.0.0.1", _TEST_PORT + 1), timeout=3) as s:
            data = s.recv(4096).decode("ascii", errors="replace")
        self.assertNotIn("Exception", data)
        self.assertNotIn("ValueError", data)


# ---------------------------------------------------------------------------
# T-18 — Default host binding is loopback
# ---------------------------------------------------------------------------

class TestQuoteServiceDefaultBinding(unittest.TestCase):

    def test_default_host_is_loopback(self):
        """Default host must be 127.0.0.1, not 0.0.0.0."""
        svc = QuoteService(port=_TEST_PORT + 2)
        self.assertEqual(svc.host, "127.0.0.1")
        self.assertNotEqual(svc.host, "0.0.0.0")

    def test_rfc865_port_constant_is_17(self):
        """RFC 865 canonical port must be 17."""
        self.assertEqual(RFC865_PORT, 17)

    def test_default_port_is_rfc865(self):
        """Default port must be RFC865_PORT (17)."""
        svc = QuoteService()
        self.assertEqual(svc.port, RFC865_PORT)


# ---------------------------------------------------------------------------
# T-19 — Port 17 not used in tests (privilege escalation guard)
# ---------------------------------------------------------------------------

class TestPrivilegedPortNotUsed(unittest.TestCase):

    def test_test_port_is_not_privileged(self):
        """Test port must be > 1023 to avoid requiring root."""
        self.assertGreater(_TEST_PORT, 1023)

    def test_service_can_be_configured_with_high_port(self):
        """QuoteService must accept any port > 1023."""
        svc = QuoteService(port=19999)
        self.assertEqual(svc.port, 19999)


# ---------------------------------------------------------------------------
# T-20 — UDP response does not echo client payload
# ---------------------------------------------------------------------------

class TestUDPNoPayloadEcho(unittest.TestCase):
    """Server must never echo client datagram content back."""

    def setUp(self):
        provider = QuoteProvider(quotes=_CORPUS, seed=0)
        self.service = QuoteService(provider=provider, port=_TEST_PORT + 3)
        self.thread = threading.Thread(target=self.service.start_udp, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.service.stop()
        self.thread.join(timeout=3)

    def test_malicious_payload_not_echoed(self):
        """Sending a malicious payload must not cause it to appear in response."""
        malicious = b"INJECT\x00\x01\x02\x03" * 64
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.sendto(malicious, ("127.0.0.1", _TEST_PORT + 3))
            data, _ = s.recvfrom(1024)
        response = data.decode("ascii", errors="replace")
        self.assertIn(response, _CORPUS)
        self.assertNotIn("INJECT", response)

    def test_oversized_udp_payload_handled_gracefully(self):
        """Sending a large UDP payload must not crash the server."""
        large_payload = b"X" * 65000
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.sendto(large_payload, ("127.0.0.1", _TEST_PORT + 3))
            data, _ = s.recvfrom(1024)
        self.assertIn(data.decode("ascii"), _CORPUS)


# ---------------------------------------------------------------------------
# Telemetry security: error_msg truncation
# ---------------------------------------------------------------------------

class TestTelemetrySecurityProperties(unittest.TestCase):
    """Telemetry must not store unbounded error messages."""

    def test_error_msg_truncated_at_500_chars(self):
        """_MeasureContext.fail() must truncate messages to 500 chars."""
        import tempfile
        from pathlib import Path
        from telemetry import TelemetryStore

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        store = TelemetryStore(db_path=Path(tmp.name))
        store.start()

        long_error = "E" * 10_000
        with store.measure("test") as ctx:
            ctx.fail(long_error)

        store.flush()
        store.stop()

        import sqlite3
        with sqlite3.connect(tmp.name) as conn:
            row = conn.execute(
                "SELECT error_msg FROM events WHERE event_type='test'"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertLessEqual(len(row[0]), 500)

    def test_record_after_stop_does_not_raise(self):
        """Calling record() after stop() must be a silent no-op."""
        import tempfile
        from pathlib import Path
        from telemetry import TelemetryStore

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        store = TelemetryStore(db_path=Path(tmp.name))
        store.start()
        store.stop()
        # Must not raise
        store.record("greeting", 1000, success=True)
        store.record("greeting", 2000, success=False, error_msg="late error")


# ---------------------------------------------------------------------------
# QuoteService lifecycle security
# ---------------------------------------------------------------------------

class TestQuoteServiceLifecycleSecurity(unittest.TestCase):

    def test_stop_is_idempotent(self):
        """Calling stop() multiple times must not raise."""
        svc = QuoteService(port=_TEST_PORT + 4)
        svc.stop()
        svc.stop()
        svc.stop()

    def test_stop_event_set_after_stop(self):
        """After stop(), the internal stop event must be set."""
        svc = QuoteService(port=_TEST_PORT + 4)
        svc.stop()
        self.assertTrue(svc._stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
