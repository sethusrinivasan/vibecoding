"""
Extended tests for QuoteProvider.
Covers single-quote corpus, large corpus, and edge cases not in test_quote_provider.py.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from quote_provider import QuoteProvider


class TestSingleQuoteCorpus(unittest.TestCase):
    """Single-quote corpus: repetition is unavoidable but must not raise."""

    def test_single_quote_always_returned(self):
        p = QuoteProvider(quotes=("Only.\r\n",))
        for _ in range(10):
            self.assertEqual(p.get(), "Only.\r\n")

    def test_single_quote_history_grows(self):
        p = QuoteProvider(quotes=("Only.\r\n",))
        for i in range(5):
            p.get()
        self.assertEqual(len(p.history), 5)

    def test_single_quote_served_count(self):
        p = QuoteProvider(quotes=("Only.\r\n",))
        for _ in range(7):
            p.get()
        self.assertEqual(p.served_count(), 7)


class TestLargeCorpus(unittest.TestCase):
    """Large corpus performance and correctness."""

    def test_large_corpus_constructs(self):
        corpus = tuple(f"Quote {i}.\r\n" for i in range(1000))
        p = QuoteProvider(quotes=corpus)
        self.assertEqual(len(p), 1000)

    def test_large_corpus_get_returns_valid_quote(self):
        corpus = tuple(f"Q{i}.\r\n" for i in range(500))
        p = QuoteProvider(quotes=corpus, seed=0)
        for _ in range(50):
            q = p.get()
            self.assertIn(q, corpus)

    def test_large_corpus_full_cycle_all_unique(self):
        n = 50
        corpus = tuple(f"Q{i}.\r\n" for i in range(n))
        p = QuoteProvider(quotes=corpus, seed=42)
        drawn = [p.get() for _ in range(n)]
        self.assertEqual(len(set(drawn)), n)

    def test_large_corpus_no_consecutive_repeat(self):
        corpus = tuple(f"Q{i}.\r\n" for i in range(100))
        p = QuoteProvider(quotes=corpus, seed=7)
        prev = p.get()
        for _ in range(300):
            curr = p.get()
            self.assertNotEqual(prev, curr)
            prev = curr


class TestQuoteProviderEdgeCases(unittest.TestCase):
    """Edge cases in corpus validation and get() behaviour."""

    def test_quote_with_only_crlf_is_valid(self):
        """A quote that is just CRLF is technically valid (non-empty, ≤512)."""
        p = QuoteProvider(quotes=("\r\n",))
        self.assertEqual(p.get(), "\r\n")

    def test_quote_with_spaces_is_valid(self):
        p = QuoteProvider(quotes=("   \r\n",))
        self.assertEqual(p.get(), "   \r\n")

    def test_multiple_cycles_no_consecutive_repeat(self):
        """Across 3 full cycles, no two consecutive quotes should be equal."""
        corpus = tuple(f"C{i}.\r\n" for i in range(4))
        p = QuoteProvider(quotes=corpus, seed=99)
        n = len(corpus)
        quotes = [p.get() for _ in range(n * 3)]
        for i in range(1, len(quotes)):
            self.assertNotEqual(quotes[i - 1], quotes[i],
                                f"Consecutive repeat at index {i}")

    def test_seed_none_produces_valid_quotes(self):
        """seed=None (default) must still produce valid quotes."""
        p = QuoteProvider(seed=None)
        q = p.get()
        self.assertIsInstance(q, str)
        self.assertGreater(len(q), 0)

    def test_history_is_mutable_list(self):
        """history is a plain list — callers can inspect it."""
        p = QuoteProvider(quotes=("A.\r\n", "B.\r\n"), seed=0)
        p.get()
        p.get()
        self.assertIsInstance(p.history, list)
        self.assertEqual(len(p.history), 2)

    def test_len_returns_corpus_size(self):
        corpus = tuple(f"Q{i}.\r\n" for i in range(7))
        p = QuoteProvider(quotes=corpus)
        self.assertEqual(len(p), 7)

    def test_quotes_attribute_is_immutable_tuple(self):
        corpus = ("A.\r\n", "B.\r\n")
        p = QuoteProvider(quotes=corpus)
        self.assertIsInstance(p.quotes, tuple)

    def test_two_corpus_items_both_served_in_cycle(self):
        corpus = ("X.\r\n", "Y.\r\n")
        p = QuoteProvider(quotes=corpus, seed=0)
        seen = set()
        for _ in range(10):
            seen.add(p.get())
        self.assertEqual(seen, {"X.\r\n", "Y.\r\n"})
