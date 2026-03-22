"""
quote_service.py
~~~~~~~~~~~~~~~~
Implements the Quote of the Day protocol as specified in :rfc:`865`.

Protocol summary
----------------
- TCP: server listens on port 17 (configurable), sends one quote per
  connection, ignores any received data, then closes the connection.
- UDP: server listens on port 17 (configurable), responds to any incoming
  datagram with a quote datagram, ignores datagram content.

.. note::
   Port 17 requires root/administrator privileges on most operating systems.
   Use ``port=1717`` (or any port > 1023) for unprivileged development use.

Usage::

    from quote_service import QuoteService
    service = QuoteService(port=1717)
    service.start_tcp()   # blocking — run in a thread for non-blocking use
"""

import socket
import threading
import logging
from quote_provider import QuoteProvider
from telemetry import TelemetryStore

logger = logging.getLogger(__name__)

# RFC 865 canonical port
RFC865_PORT: int = 17

# Maximum UDP datagram payload (RFC 865 quotes are ≤512 chars; add headroom)
_UDP_BUFFER: int = 1024


class QuoteService:
    """RFC 865 Quote of the Day server supporting TCP and UDP transports.

    :param provider: A :class:`~quote_provider.QuoteProvider` instance.
                     Defaults to a new provider with the built-in corpus.
    :param host: Interface to bind to. Defaults to ``"127.0.0.1"`` (loopback).
                 Use ``"0.0.0.0"`` to listen on all interfaces.
    :param port: Port number to bind to. Defaults to :data:`RFC865_PORT` (17).
                 Use a port > 1023 for unprivileged operation.

    Example — TCP server in a background thread::

        import threading
        from quote_service import QuoteService

        service = QuoteService(port=1717)
        t = threading.Thread(target=service.start_tcp, daemon=True)
        t.start()
    """

    def __init__(
        self,
        provider: QuoteProvider = None,
        host: str = "127.0.0.1",
        port: int = RFC865_PORT,
        telemetry: TelemetryStore = None,
    ) -> None:
        #: Quote source used to serve responses.
        self.provider: QuoteProvider = provider or QuoteProvider()
        #: Network interface the service binds to.
        self.host: str = host
        #: Port the service listens on.
        self.port: int = port
        #: Optional telemetry store for async metric recording.
        self.telemetry: TelemetryStore = telemetry

        # Internal stop event — set to signal both TCP and UDP loops to exit
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # TCP transport (RFC 865 §TCP)
    # ------------------------------------------------------------------

    def start_tcp(self) -> None:
        """Start the TCP Quote of the Day server (blocking).

        Listens for incoming TCP connections on :attr:`host`/:attr:`port`.
        For each connection: sends one quote, ignores any received data,
        closes the connection.  Runs until :meth:`stop` is called.

        :raises OSError: If the port cannot be bound (e.g. already in use,
                         or insufficient privileges for port < 1024).
        """
        self._stop_event.clear()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            # Allow rapid restart without waiting for TIME_WAIT to expire
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.port))
            srv.listen(5)
            # Non-blocking accept loop so stop() can interrupt cleanly
            srv.settimeout(1.0)
            logger.info("TCP QOTD listening on %s:%d", self.host, self.port)

            while not self._stop_event.is_set():
                try:
                    conn, addr = srv.accept()
                except socket.timeout:
                    # Timeout lets us re-check the stop event each second
                    continue
                # Handle each connection in its own thread so the accept
                # loop is never blocked by a slow client
                threading.Thread(
                    target=self._handle_tcp,
                    args=(conn, addr),
                    daemon=True,
                ).start()

        logger.info("TCP QOTD server stopped.")

    def _handle_tcp(self, conn: socket.socket, addr: tuple) -> None:
        """Send one quote to a connected TCP client then close the connection.

        Per RFC 865: any data received from the client is silently discarded.
        Response time and faults are recorded asynchronously via telemetry.

        :param conn: The accepted client socket.
        :param addr: The client's ``(host, port)`` address tuple.
        """
        with conn:
            if self.telemetry:
                with self.telemetry.measure("tcp_request") as ctx:
                    try:
                        quote = self.provider.get()
                        conn.sendall(quote.encode("ascii", errors="replace"))
                        logger.debug("TCP quote sent to %s:%d", *addr)
                    except OSError as exc:
                        ctx.fail(str(exc))
                        logger.warning("TCP send error to %s:%d — %s", *addr, exc)
            else:
                try:
                    quote = self.provider.get()
                    conn.sendall(quote.encode("ascii", errors="replace"))
                    logger.debug("TCP quote sent to %s:%d", *addr)
                except OSError as exc:
                    logger.warning("TCP send error to %s:%d — %s", *addr, exc)

    # ------------------------------------------------------------------
    # UDP transport (RFC 865 §UDP)
    # ------------------------------------------------------------------

    def start_udp(self) -> None:
        """Start the UDP Quote of the Day server (blocking).

        Listens for incoming UDP datagrams on :attr:`host`/:attr:`port`.
        For each datagram received: sends a quote datagram back to the
        sender, ignores the datagram content.  Runs until :meth:`stop`
        is called.

        :raises OSError: If the port cannot be bound.
        """
        self._stop_event.clear()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as srv:
            srv.bind((self.host, self.port))
            srv.settimeout(1.0)
            logger.info("UDP QOTD listening on %s:%d", self.host, self.port)

            while not self._stop_event.is_set():
                try:
                    # Receive and discard client data (RFC 865: data is ignored)
                    _, client_addr = srv.recvfrom(_UDP_BUFFER)
                except socket.timeout:
                    continue
                if self.telemetry:
                    with self.telemetry.measure("udp_request") as ctx:
                        try:
                            quote = self.provider.get()
                            srv.sendto(quote.encode("ascii", errors="replace"), client_addr)
                            logger.debug("UDP quote sent to %s:%d", *client_addr)
                        except OSError as exc:
                            ctx.fail(str(exc))
                            logger.warning("UDP send error to %s:%d — %s", *client_addr, exc)
                else:
                    try:
                        quote = self.provider.get()
                        srv.sendto(quote.encode("ascii", errors="replace"), client_addr)
                        logger.debug("UDP quote sent to %s:%d", *client_addr)
                    except OSError as exc:
                        logger.warning("UDP send error to %s:%d — %s", *client_addr, exc)

        logger.info("UDP QOTD server stopped.")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Signal both TCP and UDP server loops to exit cleanly.

        The loops check the stop event once per second (socket timeout),
        so shutdown completes within ~1 second of calling this method.
        """
        self._stop_event.set()
        logger.info("QOTD stop requested.")
