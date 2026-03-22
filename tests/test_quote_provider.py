"""
Unit tests for QuoteProvider.
All tests are isolated — no network, no filesystem, no randomness leakage.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from quote_provider import QuoteProvider, _DEFAULT_QUOTES


class TestQuoteProviderConstruction(unittest.TestCase):

    def test_default_corpus_loads(self):
        p = QuoteProvider()
        self.assertGreater(len(p), 0)

    def test_custom_corpus(self):
        p = QuoteProvider(quotes=("Hello.\r\n", "World.\r\n"))
        self.assertEqual(len(p), 2)

    def test_empty_corpus_raises(self):
        with self.assertRaises(ValueError):
            QuoteProvider(quotes=())

    def test_quote_exceeding_512_chars_raises(self):
        long_quote = "A" * 513
        with self.assertRaises(ValueError):
            QuoteProvider(quotes=(long_quote,))

    def test_quote_exactly_512_chars_is_valid(self):
        edge = "A" * 512
        p = QuoteProvider(quotes=(edge,))
        self.assertEqual(p.get(), edge)


class TestQuoteProviderGet(unittest.TestCase):

    def test_get_returns_string(self):
        self.assertIsInstance(QuoteProvider().get(), str)

    def test_get_returns_from_corpus(self):
        corpus = ("Alpha.\r\n", "Beta.\r\n", "Gamma.\r\n")
        p = QuoteProvider(quotes=corpus)
        for _ in range(20):
            self.assertIn(p.get(), corpus)

    def test_seeded_provider_is_deterministic(self):
        p1 = QuoteProvider(seed=42)
        p2 = QuoteProvider(seed=42)
        results1 = [p1.get() for _ in range(10)]
        results2 = [p2.get() for _ in range(10)]
        self.assertEqual(results1, results2)

    def test_different_seeds_produce_different_sequences(self):
        p1 = QuoteProvider(seed=1)
        p2 = QuoteProvider(seed=2)
        results1 = [p1.get() for _ in range(10)]
        results2 = [p2.get() for _ in range(10)]
        self.assertNotEqual(results1, results2)

    def test_single_quote_corpus_always_returns_same(self):
        p = QuoteProvider(quotes=("Only one.\r\n",))
        for _ in range(5):
            self.assertEqual(p.get(), "Only one.\r\n")


class TestNonRepeatingBehaviour(unittest.TestCase):
    """Verify the shuffle-deck non-repeat guarantees."""

    def test_no_consecutive_repeat(self):
        """No two back-to-back quotes should be the same (corpus > 1)."""
        p = QuoteProvider(seed=0)
        prev = p.get()
        for _ in range(200):
            curr = p.get()
            self.assertNotEqual(prev, curr, "Consecutive duplicate detected")
            prev = curr

    def test_no_consecutive_repeat_small_corpus(self):
        """Same guarantee holds for a small corpus."""
        corpus = tuple(f"Quote {i}.\r\n" for i in range(3))
        p = QuoteProvider(quotes=corpus, seed=7)
        prev = p.get()
        for _ in range(30):
            curr = p.get()
            self.assertNotEqual(prev, curr)
            prev = curr

    def test_full_cycle_all_unique(self):
        """Drawing exactly N quotes should yield all N distinct quotes."""
        corpus = tuple(f"Q{i}.\r\n" for i in range(10))
        p = QuoteProvider(quotes=corpus, seed=1)
        n = len(corpus)
        drawn = [p.get() for _ in range(n)]
        self.assertEqual(len(set(drawn)), n, "Not all quotes appeared in one cycle")

    def test_cross_cycle_no_repeat(self):
        """The last quote of cycle N must not equal the first of cycle N+1."""
        corpus = tuple(f"Q{i}.\r\n" for i in range(5))
        p = QuoteProvider(quotes=corpus, seed=3)
        n = len(corpus)
        # Draw two full cycles + 1 to observe every cycle boundary
        quotes = [p.get() for _ in range(n * 2 + 1)]
        for i in range(1, len(quotes)):
            self.assertNotEqual(
                quotes[i - 1], quotes[i],
                f"Consecutive repeat at positions {i-1} and {i}"
            )

    def test_two_quote_corpus_alternates(self):
        """With only two quotes, they must strictly alternate."""
        corpus = ("A.\r\n", "B.\r\n")
        p = QuoteProvider(quotes=corpus, seed=0)
        prev = p.get()
        for _ in range(20):
            curr = p.get()
            self.assertNotEqual(prev, curr)
            prev = curr


class TestHistoryTracking(unittest.TestCase):

    def test_history_starts_empty(self):
        p = QuoteProvider()
        self.assertEqual(p.history, [])

    def test_history_grows_with_each_get(self):
        p = QuoteProvider(seed=0)
        for n in range(1, 11):
            p.get()
            self.assertEqual(len(p.history), n)

    def test_history_contains_served_quotes(self):
        corpus = ("X.\r\n", "Y.\r\n", "Z.\r\n")
        p = QuoteProvider(quotes=corpus, seed=0)
        for _ in range(9):
            q = p.get()
            self.assertEqual(p.history[-1], q)

    def test_history_order_matches_serve_order(self):
        p = QuoteProvider(seed=5)
        served = [p.get() for _ in range(15)]
        self.assertEqual(p.history, served)


class TestServedCount(unittest.TestCase):

    def test_served_count_starts_at_zero(self):
        p = QuoteProvider()
        self.assertEqual(p.served_count(), 0)

    def test_served_count_increments(self):
        p = QuoteProvider(seed=0)
        for n in range(1, 11):
            p.get()
            self.assertEqual(p.served_count(), n)

    def test_served_count_equals_history_length(self):
        p = QuoteProvider(seed=0)
        for _ in range(25):
            p.get()
        self.assertEqual(p.served_count(), len(p.history))


class TestDefaultCorpusCompliance(unittest.TestCase):
    """Verify every built-in quote is RFC 865 compliant and corpus is large enough."""

    def test_corpus_has_at_least_100_quotes(self):
        self.assertGreaterEqual(
            len(_DEFAULT_QUOTES), 100,
            f"Expected >=100 quotes, got {len(_DEFAULT_QUOTES)}"
        )

    def test_all_quotes_within_512_chars(self):
        for i, q in enumerate(_DEFAULT_QUOTES):
            self.assertLessEqual(
                len(q), 512,
                msg=f"Default quote {i} exceeds 512 chars: {len(q)}"
            )

    def test_all_quotes_are_non_empty(self):
        for i, q in enumerate(_DEFAULT_QUOTES):
            self.assertTrue(len(q) > 0, msg=f"Default quote {i} is empty")

    def test_all_quotes_are_strings(self):
        for q in _DEFAULT_QUOTES:
            self.assertIsInstance(q, str)

    def test_no_duplicate_quotes_in_corpus(self):
        self.assertEqual(
            len(_DEFAULT_QUOTES), len(set(_DEFAULT_QUOTES)),
            "Duplicate quotes found in default corpus"
        )


if __name__ == "__main__":
    unittest.main()
