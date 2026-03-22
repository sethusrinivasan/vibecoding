"""
Integration tests for Greeting + TimeOfDay + QuoteProvider working together.
No mocking — tests the real interaction between all classes.
"""
import unittest
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from colorama import Fore
from time_of_day import TimeOfDay
from greeting import Greeting
from quote_provider import QuoteProvider


class TestGreetingTimeOfDayIntegration(unittest.TestCase):
    """Greeting.build() produces output consistent with TimeOfDay properties."""

    def _assert_greeting(self, hour, expected_salutation, expected_color):
        now = datetime(2026, 3, 22, hour, 0)
        g = Greeting("Dev")
        result = g.build(now)
        period = TimeOfDay.from_hour(hour)

        self.assertIn(expected_salutation, result)
        self.assertEqual(period.color, expected_color)
        self.assertIn("Dev", result)

    def test_morning_full_flow(self):
        self._assert_greeting(8, "Good morning", Fore.YELLOW)

    def test_afternoon_full_flow(self):
        self._assert_greeting(13, "Good afternoon", Fore.CYAN)

    def test_evening_full_flow(self):
        self._assert_greeting(19, "Good evening", Fore.MAGENTA)

    def test_night_full_flow(self):
        self._assert_greeting(22, "Good night", Fore.BLUE)

    def test_salutation_in_build_matches_time_of_day(self):
        """Salutation in Greeting.build() must always match TimeOfDay.salutation."""
        for hour in range(24):
            now = datetime(2026, 3, 22, hour, 0)
            period = TimeOfDay.from_hour(hour)
            result = Greeting().build(now)
            self.assertIn(period.salutation, result,
                msg=f"Hour {hour}: expected '{period.salutation}' in '{result}'")

    def test_all_hours_produce_valid_output(self):
        """Greeting.build() must not raise for any hour 0-23."""
        for hour in range(24):
            now = datetime(2026, 3, 22, hour, 0)
            result = Greeting().build(now)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)


class TestGreetingWithQuoteIntegration(unittest.TestCase):
    """Greeting + QuoteProvider full end-to-end without mocks."""

    def test_greeting_with_quote_produces_two_outputs(self):
        """run() with a provider emits greeting line + quote line."""
        from unittest.mock import patch
        provider = QuoteProvider(seed=0)
        g = Greeting("Dev", quote_provider=provider)
        now = datetime(2026, 3, 22, 9, 0)
        with patch('builtins.print') as mock_print:
            g.run(now=now)
        self.assertEqual(mock_print.call_count, 2)

    def test_quote_comes_from_provider_corpus(self):
        """The printed quote must be one of the provider's quotes."""
        from unittest.mock import patch
        corpus = ("Alpha.\r\n", "Beta.\r\n")
        provider = QuoteProvider(quotes=corpus)
        g = Greeting(quote_provider=provider)
        now = datetime(2026, 3, 22, 9, 0)
        with patch('builtins.print') as mock_print:
            g.run(now=now)
        printed_quote = mock_print.call_args_list[1][0][0]
        self.assertIn(printed_quote, corpus)

    def test_greeting_without_provider_has_no_quote(self):
        """run() without a provider emits exactly one line."""
        from unittest.mock import patch
        g = Greeting("Dev")
        now = datetime(2026, 3, 22, 9, 0)
        with patch('builtins.print') as mock_print:
            g.run(now=now)
        self.assertEqual(mock_print.call_count, 1)


if __name__ == "__main__":
    unittest.main()
