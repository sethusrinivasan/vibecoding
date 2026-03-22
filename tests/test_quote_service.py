"""
Unit and integration tests for QuoteService (RFC 865).

Unit tests mock the socket layer.
Integration tests spin up a real TCP/UDP server on a high ephemeral port
and connect to it, verifying end-to-end protocol behaviour.
"""
import socket
import threading
import time
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from quote_provider import QuoteProvider
from quote_service import QuoteService

# Use a high port so tests run without root privileges
_TEST_PORT = 19865
_CORPUS = ("Test quote one.\r\n", "Test quote two.\r\n")


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestQuoteServiceInit(unittest.TestCase):

    def test_default_provider_created(self):
        svc = QuoteService(port=_TEST_PORT)
        self.assertIsInstance(svc.provider, QuoteProvider)

    def test_custom_provider_stored(self):
        p = QuoteProvider(quotes=_CORPUS)
        svc = QuoteService(provider=p, port=_TEST_PORT)
        self.assertIs(svc.provider, p)

    def test_default_host_is_loopback(self):
        svc = QuoteService(port=_TEST_PORT)
        self.assertEqual(svc.host, "127.0.0.1")

    def test_custom_host_stored(self):
        svc = QuoteService(host="0.0.0.0", port=_TEST_PORT)
        self.assertEqual(svc.host, "0.0.0.0")

    def test_stop_before_start_does_not_raise(self):
        svc = QuoteService(port=_TEST_PORT)
        svc.stop()  # should be a no-op


# ---------------------------------------------------------------------------
# Integration tests — real TCP socket
# ---------------------------------------------------------------------------

class TestQuoteServiceTCP(unittest.TestCase):

    def setUp(self):
        provider = QuoteProvider(quotes=_CORPUS, seed=0)
        self.service = QuoteService(provider=provider, port=_TEST_PORT)
        self.thread = threading.Thread(target=self.service.start_tcp, daemon=True)
        self.thread.start()
        # Give the server a moment to bind
        time.sleep(0.1)

    def tearDown(self):
        self.service.stop()
        self.thread.join(timeout=3)

    def test_tcp_returns_a_quote(self):
        with socket.create_connection(("127.0.0.1", _TEST_PORT), timeout=3) as s:
            data = s.recv(1024).decode("ascii")
        self.assertIn(data, _CORPUS)

    def test_tcp_quote_is_non_empty(self):
        with socket.create_connection(("127.0.0.1", _TEST_PORT), timeout=3) as s:
            data = s.recv(1024).decode("ascii")
        self.assertGreater(len(data), 0)

    def test_tcp_quote_within_512_chars(self):
        with socket.create_connection(("127.0.0.1", _TEST_PORT), timeout=3) as s:
            data = s.recv(1024).decode("ascii")
        self.assertLessEqual(len(data), 512)

    def test_tcp_server_ignores_client_data(self):
        """RFC 865: any data sent by the client must be silently discarded."""
        with socket.create_connection(("127.0.0.1", _TEST_PORT), timeout=3) as s:
            s.sendall(b"ignored payload\r\n")
            data = s.recv(1024).decode("ascii")
        self.assertIn(data, _CORPUS)

    def test_tcp_multiple_sequential_connections(self):
        """Server must handle multiple connections sequentially."""
        for _ in range(3):
            with socket.create_connection(("127.0.0.1", _TEST_PORT), timeout=3) as s:
                data = s.recv(1024).decode("ascii")
            self.assertIn(data, _CORPUS)


# ---------------------------------------------------------------------------
# Integration tests — real UDP socket
# ---------------------------------------------------------------------------

class TestQuoteServiceUDP(unittest.TestCase):

    def setUp(self):
        provider = QuoteProvider(quotes=_CORPUS, seed=0)
        self.service = QuoteService(provider=provider, port=_TEST_PORT + 1)
        self.thread = threading.Thread(target=self.service.start_udp, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.service.stop()
        self.thread.join(timeout=3)

    def test_udp_returns_a_quote(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.sendto(b"", ("127.0.0.1", _TEST_PORT + 1))
            data, _ = s.recvfrom(1024)
        self.assertIn(data.decode("ascii"), _CORPUS)

    def test_udp_quote_within_512_chars(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.sendto(b"", ("127.0.0.1", _TEST_PORT + 1))
            data, _ = s.recvfrom(1024)
        self.assertLessEqual(len(data), 512)

    def test_udp_ignores_datagram_content(self):
        """RFC 865: datagram content is ignored; a quote is always returned."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(3)
            s.sendto(b"this content is ignored", ("127.0.0.1", _TEST_PORT + 1))
            data, _ = s.recvfrom(1024)
        self.assertIn(data.decode("ascii"), _CORPUS)


if __name__ == "__main__":
    unittest.main()
