"""
Benchmark tests for Greeting and TimeOfDay.
Uses timeit to assert operations complete within acceptable time thresholds.
These are not correctness tests — they guard against performance regressions.
"""
import unittest
import timeit
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from time_of_day import TimeOfDay
from greeting import Greeting
from quote_provider import QuoteProvider


class TestTimeOfDayBenchmark(unittest.TestCase):

    def test_from_hour_performance(self):
        """TimeOfDay.from_hour() should resolve 10,000 calls in under 0.1s."""
        elapsed = timeit.timeit(
            lambda: TimeOfDay.from_hour(14),
            number=10_000
        )
        self.assertLess(elapsed, 0.1, f"from_hour too slow: {elapsed:.4f}s")

    def test_color_property_performance(self):
        """color property lookup should handle 10,000 calls in under 0.1s."""
        period = TimeOfDay.MORNING
        elapsed = timeit.timeit(lambda: period.color, number=10_000)
        self.assertLess(elapsed, 0.1, f"color property too slow: {elapsed:.4f}s")

    def test_salutation_property_performance(self):
        """salutation property lookup should handle 10,000 calls in under 0.1s."""
        period = TimeOfDay.AFTERNOON
        elapsed = timeit.timeit(lambda: period.salutation, number=10_000)
        self.assertLess(elapsed, 0.1, f"salutation property too slow: {elapsed:.4f}s")


class TestGreetingBenchmark(unittest.TestCase):

    def test_build_performance(self):
        """Greeting.build() should handle 10,000 calls in under 0.5s."""
        g = Greeting("World")
        now = datetime(2026, 3, 22, 9, 30)
        elapsed = timeit.timeit(lambda: g.build(now), number=10_000)
        self.assertLess(elapsed, 0.5, f"build() too slow: {elapsed:.4f}s")


class TestQuoteProviderBenchmark(unittest.TestCase):

    def test_get_performance(self):
        """QuoteProvider.get() should handle 10,000 calls in under 0.1s."""
        p = QuoteProvider()
        elapsed = timeit.timeit(lambda: p.get(), number=10_000)
        self.assertLess(elapsed, 0.1, f"QuoteProvider.get() too slow: {elapsed:.4f}s")

    def test_construction_performance(self):
        """QuoteProvider() construction should complete 1,000 times in under 0.5s."""
        elapsed = timeit.timeit(lambda: QuoteProvider(), number=1_000)
        self.assertLess(elapsed, 0.5, f"QuoteProvider() construction too slow: {elapsed:.4f}s")


if __name__ == "__main__":
    unittest.main()
