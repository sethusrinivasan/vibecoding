"""
Tests for the Greeting Worker local logic.

Tests run against local_server.py's helper functions directly (no HTTP
server needed) and against the routing logic via a lightweight fake
request/response harness — no pywrangler or Node required.
"""

import json
import sys
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

# Make worker/src importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import local_server as ls
from time_of_day import TimeOfDay
from quote_provider import QuoteProvider
from cf_telemetry import CfTelemetry, _compute_summary


# ---------------------------------------------------------------------------
# TimeOfDay (worker edition — CSS colours, no colorama)
# ---------------------------------------------------------------------------

class TestWorkerTimeOfDay(unittest.TestCase):

    def test_from_hour_morning(self):
        self.assertEqual(TimeOfDay.from_hour(9), TimeOfDay.MORNING)

    def test_from_hour_afternoon(self):
        self.assertEqual(TimeOfDay.from_hour(14), TimeOfDay.AFTERNOON)

    def test_from_hour_evening(self):
        self.assertEqual(TimeOfDay.from_hour(19), TimeOfDay.EVENING)

    def test_from_hour_night(self):
        self.assertEqual(TimeOfDay.from_hour(23), TimeOfDay.NIGHT)

    def test_color_is_css_hex(self):
        """Worker TimeOfDay.color must return CSS hex strings, not ANSI codes."""
        for period in TimeOfDay:
            self.assertTrue(
                period.color.startswith("#"),
                f"{period} color should be a CSS hex, got {period.color!r}"
            )
            self.assertNotIn("\033", period.color)

    def test_all_salutations_present(self):
        for period in TimeOfDay:
            self.assertIn("Good", period.salutation)

    def test_invalid_hour_raises(self):
        with self.assertRaises(ValueError):
            TimeOfDay.from_hour(24)

    def test_negative_hour_raises(self):
        with self.assertRaises(ValueError):
            TimeOfDay.from_hour(-1)


# ---------------------------------------------------------------------------
# Name sanitisation
# ---------------------------------------------------------------------------

class TestWorkerNameSanitisation(unittest.TestCase):

    def test_ansi_stripped(self):
        self.assertEqual(ls._sanitise_name("\033[31mEve\033[0m"), "Eve")

    def test_null_byte_stripped(self):
        self.assertEqual(ls._sanitise_name("Alice\x00Bob"), "AliceBob")

    def test_newline_stripped(self):
        self.assertEqual(ls._sanitise_name("Alice\nBob"), "AliceBob")

    def test_truncated_at_100(self):
        self.assertEqual(len(ls._sanitise_name("A" * 200)), 100)

    def test_empty_falls_back_to_world(self):
        self.assertEqual(ls._sanitise_name(""), "World")

    def test_fully_stripped_falls_back_to_world(self):
        self.assertEqual(ls._sanitise_name("\033[2J\x00"), "World")

    def test_printable_ascii_preserved(self):
        self.assertEqual(ls._sanitise_name("Alice Smith"), "Alice Smith")


# ---------------------------------------------------------------------------
# _build_greeting
# ---------------------------------------------------------------------------

class TestBuildGreeting(unittest.TestCase):

    def test_returns_dict_with_required_keys(self):
        data = ls._build_greeting("Alice")
        for key in ("greeting", "period", "color", "quote", "timestamp"):
            self.assertIn(key, data)

    def test_greeting_contains_name(self):
        data = ls._build_greeting("Alice")
        self.assertIn("Alice", data["greeting"])

    def test_greeting_contains_salutation(self):
        data = ls._build_greeting("Alice")
        self.assertTrue(data["greeting"].startswith("Good "))

    def test_color_is_css_hex(self):
        data = ls._build_greeting("Alice")
        self.assertTrue(data["color"].startswith("#"))

    def test_quote_is_non_empty_string(self):
        data = ls._build_greeting("Alice")
        self.assertIsInstance(data["quote"], str)
        self.assertGreater(len(data["quote"]), 0)

    def test_timestamp_is_iso8601(self):
        data = ls._build_greeting("Alice")
        # Should parse without error
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_world_default(self):
        data = ls._build_greeting("World")
        self.assertIn("World", data["greeting"])


# ---------------------------------------------------------------------------
# In-memory telemetry (_record / _stats_summary)
# ---------------------------------------------------------------------------

class TestInMemoryTelemetry(unittest.TestCase):

    def setUp(self):
        ls._events.clear()

    def test_record_appends_event(self):
        ls._record("greeting", 12500, True)
        self.assertEqual(len(ls._events), 1)
        self.assertEqual(ls._events[0]["event_type"], "greeting")

    def test_record_truncates_error_msg(self):
        ls._record("greeting", 1000, False, "E" * 10_000)
        self.assertLessEqual(len(ls._events[0]["error_msg"]), 500)

    def test_stats_empty(self):
        s = ls._stats_summary("greeting")
        self.assertEqual(s["count"], 0)

    def test_stats_count(self):
        for ns in [10000, 20000, 30000]:
            ls._record("greeting", ns, True)
        s = ls._stats_summary("greeting")
        self.assertEqual(s["count"], 3)

    def test_stats_mean(self):
        for ns in [10000, 20000, 30000]:
            ls._record("greeting", ns, True)
        s = ls._stats_summary("greeting")
        self.assertAlmostEqual(s["mean_ns"], 20000.0, places=0)

    def test_stats_success_rate_all_ok(self):
        for ns in [1000, 2000]:
            ls._record("greeting", ns, True)
        s = ls._stats_summary("greeting")
        self.assertAlmostEqual(s["success_rate"], 100.0)

    def test_stats_success_rate_with_faults(self):
        ls._record("greeting", 1000, True)
        ls._record("greeting", 2000, False)
        s = ls._stats_summary("greeting")
        self.assertAlmostEqual(s["success_rate"], 50.0)

    def test_stats_only_counts_matching_event_type(self):
        ls._record("greeting", 10000, True)
        ls._record("tcp_request", 5000, True)
        s = ls._stats_summary("greeting")
        self.assertEqual(s["count"], 1)


# ---------------------------------------------------------------------------
# CfTelemetry no-op mode (db=None)
# ---------------------------------------------------------------------------

class TestCfTelemetryNoOp(unittest.IsolatedAsyncioTestCase):

    async def test_record_does_not_raise_without_db(self):
        t = CfTelemetry(db=None)
        await t.record("greeting", 10.0, success=True)  # must not raise

    async def test_reset_does_not_raise_without_db(self):
        t = CfTelemetry(db=None)
        await t.reset()

    async def test_historic_summary_returns_empty_without_db(self):
        t = CfTelemetry(db=None)
        s = await t.historic_summary("greeting")
        self.assertEqual(s.count, 0)
        self.assertAlmostEqual(s.success_rate, 100.0)

    async def test_summary_to_dict_has_required_keys(self):
        t = CfTelemetry(db=None)
        s = await t.historic_summary("greeting")
        d = s.to_dict()
        for key in ("label", "count", "success_rate", "mean_ns", "p95_ns", "p99_ns"):
            self.assertIn(key, d)


# ---------------------------------------------------------------------------
# _compute_summary (pure stats logic)
# ---------------------------------------------------------------------------

class TestCfComputeSummary(unittest.TestCase):

    def test_empty_list(self):
        s = _compute_summary([], "test")
        self.assertEqual(s.count, 0)

    def test_single_value(self):
        s = _compute_summary([42000], "test")
        self.assertEqual(s.count, 1)
        self.assertAlmostEqual(s.mean_ns, 42000.0)
        self.assertAlmostEqual(s.p95_ns, 42000)

    def test_mean(self):
        s = _compute_summary([10000, 20000, 30000], "test")
        self.assertAlmostEqual(s.mean_ns, 20000.0)

    def test_fault_count(self):
        s = _compute_summary([1000, 2000], "test", fault_count=1)
        self.assertAlmostEqual(s.success_rate, 50.0)

    def test_to_dict_rounds_values(self):
        s = _compute_summary([1123456], "test")
        d = s.to_dict()
        self.assertEqual(d["mean_ns"], round(1123456, 1))


# ---------------------------------------------------------------------------
# HTML page generation
# ---------------------------------------------------------------------------

class TestHtmlPage(unittest.TestCase):

    def _data(self):
        return {
            "greeting":  "Good morning, Alice!  [09:30 AM]",
            "period":    "morning",
            "color":     "#e6b800",
            "quote":     "Carpe diem.",
            "timestamp": "2026-03-22T09:30:00+00:00",
        }

    def test_html_contains_greeting(self):
        html = ls._html_page(self._data())
        self.assertIn("Good morning, Alice!", html)

    def test_html_contains_quote(self):
        html = ls._html_page(self._data())
        self.assertIn("Carpe diem.", html)

    def test_html_contains_color(self):
        html = ls._html_page(self._data())
        self.assertIn("#e6b800", html)

    def test_html_is_valid_structure(self):
        html = ls._html_page(self._data())
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("</html>", html)

    def test_html_no_ansi_codes(self):
        html = ls._html_page(self._data())
        self.assertNotIn("\033", html)


# ---------------------------------------------------------------------------
# HTTP handler integration (real server on a random port)
# ---------------------------------------------------------------------------

import threading
import urllib.request
import urllib.error
from http.server import HTTPServer


def _start_test_server() -> tuple:
    """Start a GreetingHandler server on a random OS-assigned port.
    Returns (server, thread, base_url).
    """
    server = HTTPServer(("127.0.0.1", 0), ls.GreetingHandler)
    port   = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{port}"


def _get(url: str, accept: str = "application/json") -> tuple:
    """Return (status, body_str) for a GET request."""
    req = urllib.request.Request(url, headers={"Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _post(url: str) -> int:
    """Return status code for a POST request."""
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


class TestGreetingHandlerRouting(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server, cls.thread, cls.base = _start_test_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        ls._events.clear()

    def test_get_root_returns_200(self):
        status, _ = _get(self.base + "/")
        self.assertEqual(status, 200)

    def test_get_root_json_has_greeting_key(self):
        _, body = _get(self.base + "/")
        data = json.loads(body)
        self.assertIn("greeting", data)

    def test_get_root_with_name(self):
        _, body = _get(self.base + "/?name=Alice")
        data = json.loads(body)
        self.assertIn("Alice", data["greeting"])

    def test_get_quote_returns_quote(self):
        _, body = _get(self.base + "/quote")
        data = json.loads(body)
        self.assertIn("quote", data)
        self.assertGreater(len(data["quote"]), 0)

    def test_get_stats_returns_summary(self):
        ls._record("greeting", 10.0, True)
        _, body = _get(self.base + "/stats")
        data = json.loads(body)
        self.assertIn("count", data)

    def test_post_reset_returns_204(self):
        ls._record("greeting", 10.0, True)
        status = _post(self.base + "/reset")
        self.assertEqual(status, 204)
        self.assertEqual(len(ls._events), 0)

    def test_unknown_path_returns_404(self):
        status, _ = _get(self.base + "/nonexistent")
        self.assertEqual(status, 404)

    def test_get_root_html_accept_returns_html(self):
        _, body = _get(self.base + "/", accept="text/html")
        self.assertIn("<!DOCTYPE html>", body)

    def test_ansi_injection_in_name_param(self):
        # %1B%5B2J = ESC[2J (clear screen)
        _, body = _get(self.base + "/?name=%1B%5B2JMalicious")
        data = json.loads(body)
        self.assertNotIn("\033", data["greeting"])

    def test_get_records_telemetry(self):
        ls._events.clear()
        _get(self.base + "/")
        self.assertEqual(len(ls._events), 1)
        self.assertEqual(ls._events[0]["event_type"], "greeting")
        self.assertIn("duration_ns", ls._events[0])


if __name__ == "__main__":
    unittest.main()
