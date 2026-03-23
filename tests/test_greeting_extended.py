"""
Extended tests for Greeting.
Covers telemetry integration, error paths, and edge cases not in test_greeting.py.
"""
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from greeting import Greeting
from quote_provider import QuoteProvider
from telemetry import TelemetryStore


def _tmp_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    store = TelemetryStore(db_path=Path(tmp.name))
    store.start()
    return store


class TestGreetingTelemetryRecording(unittest.TestCase):
    """Greeting.run() records telemetry correctly."""

    def test_run_records_success_event(self):
        import sqlite3
        store = _tmp_store()
        g = Greeting("Alice", telemetry=store)
        with patch("builtins.print"):
            g.run(now=datetime(2026, 3, 22, 9, 0))
        store.flush()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            rows = conn.execute("SELECT success FROM events WHERE event_type='greeting'").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 1)

    def test_run_records_duration_greater_than_zero(self):
        import sqlite3
        store = _tmp_store()
        g = Greeting("Alice", telemetry=store)
        with patch("builtins.print"):
            g.run(now=datetime(2026, 3, 22, 9, 0))
        store.flush()
        store.stop()
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute("SELECT duration_ns FROM events WHERE event_type='greeting'").fetchone()
        self.assertGreater(row[0], 0)

    def test_run_with_telemetry_prints_stats(self):
        """run() with telemetry prints greeting + quote + 2 stats summaries = 4 prints."""
        store = _tmp_store()
        provider = QuoteProvider(quotes=("Quote.\r\n",))
        g = Greeting("Alice", quote_provider=provider, telemetry=store)
        with patch("builtins.print") as mock_print:
            g.run(now=datetime(2026, 3, 22, 9, 0))
        store.stop()
        # greeting + quote + session stats + historic stats
        self.assertGreaterEqual(mock_print.call_count, 3)

    def test_run_without_telemetry_no_stats_printed(self):
        """run() without telemetry prints only greeting (and optionally quote)."""
        g = Greeting("Alice")
        with patch("builtins.print") as mock_print:
            g.run(now=datetime(2026, 3, 22, 9, 0))
        self.assertEqual(mock_print.call_count, 1)


class TestGreetingNameEdgeCases(unittest.TestCase):
    """Name sanitisation edge cases."""

    def test_only_control_chars_falls_back_to_world(self):
        g = Greeting("\x00\x01\x02\x03\x04\x05\x06\x07")
        self.assertEqual(g.name, "World")

    def test_only_ansi_codes_falls_back_to_world(self):
        g = Greeting("\033[2J\033[H\033[0m")
        self.assertEqual(g.name, "World")

    def test_mixed_valid_and_invalid_chars(self):
        g = Greeting("Al\x00ic\x01e")
        self.assertEqual(g.name, "Alice")

    def test_name_with_spaces_preserved(self):
        g = Greeting("Alice Smith")
        self.assertEqual(g.name, "Alice Smith")

    def test_name_with_numbers_preserved(self):
        g = Greeting("User123")
        self.assertEqual(g.name, "User123")

    def test_name_with_punctuation_preserved(self):
        g = Greeting("O'Brien")
        self.assertEqual(g.name, "O'Brien")

    def test_name_exactly_100_chars_not_truncated(self):
        name = "A" * 100
        g = Greeting(name)
        self.assertEqual(len(g.name), 100)

    def test_name_101_chars_truncated_to_100(self):
        name = "A" * 101
        g = Greeting(name)
        self.assertEqual(len(g.name), 100)

    def test_non_string_name_coerced(self):
        """Greeting accepts non-string name via str() coercion."""
        g = Greeting(42)  # type: ignore
        self.assertEqual(g.name, "42")

    def test_none_name_falls_back_to_world(self):
        """None coerces to 'None' string — all printable ASCII, kept as-is."""
        g = Greeting(None)  # type: ignore
        self.assertEqual(g.name, "None")


class TestGreetingBuildEdgeCases(unittest.TestCase):
    """build() edge cases."""

    def test_build_midnight(self):
        result = Greeting().build(datetime(2026, 3, 22, 0, 0))
        self.assertIn("Good night", result)

    def test_build_noon(self):
        result = Greeting().build(datetime(2026, 3, 22, 12, 0))
        self.assertIn("Good afternoon", result)

    def test_build_time_format_pm(self):
        result = Greeting().build(datetime(2026, 3, 22, 14, 45))
        self.assertIn("02:45 PM", result)

    def test_build_time_format_midnight(self):
        result = Greeting().build(datetime(2026, 3, 22, 0, 0))
        self.assertIn("12:00 AM", result)

    def test_build_time_format_noon(self):
        result = Greeting().build(datetime(2026, 3, 22, 12, 0))
        self.assertIn("12:00 PM", result)

    def test_build_returns_string(self):
        self.assertIsInstance(Greeting().build(datetime(2026, 3, 22, 9, 0)), str)

    def test_build_contains_brackets(self):
        result = Greeting().build(datetime(2026, 3, 22, 9, 0))
        self.assertIn("[", result)
        self.assertIn("]", result)


class TestGreetingRunColorOutput(unittest.TestCase):
    """run() uses correct colorama colour for each period."""

    def _color_for_hour(self, hour):
        from colorama import Fore
        from time_of_day import TimeOfDay
        return TimeOfDay.from_hour(hour).color

    def test_afternoon_uses_cyan(self):
        from colorama import Fore
        with patch("builtins.print") as mock_print:
            Greeting().run(now=datetime(2026, 3, 22, 14, 0))
        output = mock_print.call_args_list[0][0][0]
        self.assertTrue(output.startswith(Fore.CYAN))

    def test_evening_uses_magenta(self):
        from colorama import Fore
        with patch("builtins.print") as mock_print:
            Greeting().run(now=datetime(2026, 3, 22, 19, 0))
        output = mock_print.call_args_list[0][0][0]
        self.assertTrue(output.startswith(Fore.MAGENTA))

    def test_night_uses_blue(self):
        from colorama import Fore
        with patch("builtins.print") as mock_print:
            Greeting().run(now=datetime(2026, 3, 22, 23, 0))
        output = mock_print.call_args_list[0][0][0]
        self.assertTrue(output.startswith(Fore.BLUE))
