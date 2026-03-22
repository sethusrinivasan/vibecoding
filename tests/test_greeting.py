"""
Unit tests for Greeting class.
Dependencies (datetime, print) are mocked to keep tests isolated.
"""
import unittest
from unittest.mock import patch
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from colorama import Fore
from greeting import Greeting
from quote_provider import QuoteProvider


class TestGreetingBuild(unittest.TestCase):
    """build() returns correctly formatted string for each time period."""

    def test_default_name(self):
        result = Greeting().build(datetime(2026, 3, 22, 9, 0))
        self.assertIn("World", result)

    def test_custom_name(self):
        result = Greeting("Alice").build(datetime(2026, 3, 22, 9, 0))
        self.assertIn("Alice", result)

    def test_empty_name(self):
        result = Greeting("").build(datetime(2026, 3, 22, 9, 0))
        self.assertIn("Good morning", result)

    def test_morning_salutation(self):
        self.assertIn("Good morning", Greeting().build(datetime(2026, 3, 22, 8, 0)))

    def test_afternoon_salutation(self):
        self.assertIn("Good afternoon", Greeting().build(datetime(2026, 3, 22, 14, 0)))

    def test_evening_salutation(self):
        self.assertIn("Good evening", Greeting().build(datetime(2026, 3, 22, 19, 0)))

    def test_night_salutation(self):
        self.assertIn("Good night", Greeting().build(datetime(2026, 3, 22, 23, 0)))

    def test_time_format(self):
        result = Greeting().build(datetime(2026, 3, 22, 9, 30))
        self.assertIn("09:30 AM", result)

    def test_build_uses_current_time_when_none(self):
        result = Greeting().build()
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


class TestGreetingRun(unittest.TestCase):
    """run() prints color-prefixed output to stdout."""

    def test_run_prints_morning_in_yellow(self):
        fake_now = datetime(2026, 3, 22, 9, 30)
        with patch('builtins.print') as mock_print:
            Greeting().run(now=fake_now)
            output = mock_print.call_args[0][0]
            self.assertTrue(output.startswith(Fore.YELLOW))

    def test_run_prints_greeting_and_time(self):
        fake_now = datetime(2026, 3, 22, 9, 30)
        with patch('builtins.print') as mock_print:
            Greeting().run(now=fake_now)
            output = mock_print.call_args[0][0]
            self.assertIn("Good morning, World!", output)
            self.assertIn("09:30 AM", output)

    def test_run_uses_current_time_when_none(self):
        with patch('builtins.print'):
            Greeting().run()

    def test_run_without_quote_provider_prints_once(self):
        """No quote_provider → exactly one print call."""
        fake_now = datetime(2026, 3, 22, 9, 30)
        with patch('builtins.print') as mock_print:
            Greeting().run(now=fake_now)
            self.assertEqual(mock_print.call_count, 1)

    def test_run_with_quote_provider_prints_twice(self):
        """quote_provider supplied → two print calls (greeting + quote)."""
        fake_now = datetime(2026, 3, 22, 9, 30)
        provider = QuoteProvider(quotes=("Carpe diem.\r\n",))
        with patch('builtins.print') as mock_print:
            Greeting(quote_provider=provider).run(now=fake_now)
            self.assertEqual(mock_print.call_count, 2)

    def test_run_quote_content_printed(self):
        """The exact quote from the provider appears in the second print call."""
        fake_now = datetime(2026, 3, 22, 9, 30)
        provider = QuoteProvider(quotes=("Carpe diem.\r\n",))
        with patch('builtins.print') as mock_print:
            Greeting(quote_provider=provider).run(now=fake_now)
            quote_output = mock_print.call_args_list[1][0][0]
            self.assertEqual(quote_output, "Carpe diem.\r\n")


class TestGreetingQuoteProviderIntegration(unittest.TestCase):
    """Greeting correctly wires to QuoteProvider."""

    def test_no_provider_by_default(self):
        self.assertIsNone(Greeting().quote_provider)

    def test_provider_stored(self):
        p = QuoteProvider()
        g = Greeting(quote_provider=p)
        self.assertIs(g.quote_provider, p)

    def test_ansi_injection_in_name_stripped(self):
        g = Greeting("\033[2J\033[HMalicious")
        self.assertEqual(g.name, "Malicious")

    def test_name_truncated_at_100_chars(self):
        g = Greeting("A" * 200)
        self.assertEqual(len(g.name), 100)


if __name__ == "__main__":
    unittest.main()
