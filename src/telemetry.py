"""
telemetry.py
~~~~~~~~~~~~
Async telemetry store backed by a local SQLite database.

Metrics are written via a background queue thread so recording never
blocks the main application flow.  The caller simply calls
:meth:`TelemetryStore.record` and returns immediately — the write
happens asynchronously.

Schema
------
Table ``events``:

.. code-block:: sql

    CREATE TABLE events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT    NOT NULL,   -- ISO-8601 UTC
        event_type  TEXT    NOT NULL,   -- e.g. "greeting", "tcp_request"
        duration_ns INTEGER NOT NULL,   -- wall-clock nanoseconds
        success     INTEGER NOT NULL,   -- 1 = ok, 0 = fault/error
        error_msg   TEXT                -- NULL when success=1
    );

Usage::

    store = TelemetryStore()          # opens / creates greeting_telemetry.db
    store.start()                     # start background writer thread

    with store.measure("greeting") as ctx:
        ...                           # timed block; ctx.fail("msg") on error

    store.stop()                      # flush queue and shut down
"""

import queue
import sqlite3
import threading
import time
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default database path — sits next to the src/ directory
_DEFAULT_DB = Path(__file__).parent.parent / "greeting_telemetry.db"

# Sentinel object that signals the writer thread to exit
_STOP = object()


class _MeasureContext:
    """Context manager returned by :meth:`TelemetryStore.measure`.

    Records wall-clock duration and success/failure state, then enqueues
    the event for async persistence on exit.
    """

    def __init__(self, store: "TelemetryStore", event_type: str) -> None:
        self._store = store
        self._event_type = event_type
        self._start: float = 0.0
        self._error: Optional[str] = None

    def fail(self, message: str) -> None:
        """Mark this measurement as a fault with an optional message.

        Call this inside the ``with`` block when an error occurs.

        :param message: Human-readable error description (≤500 chars).
        """
        self._error = str(message)[:500]

    def __enter__(self) -> "_MeasureContext":
        self._start = time.perf_counter_ns()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        duration_ns = time.perf_counter_ns() - self._start

        # Capture unhandled exceptions as faults automatically
        if exc_type is not None and self._error is None:
            self._error = f"{exc_type.__name__}: {exc_val}"

        self._store._enqueue(
            event_type=self._event_type,
            duration_ns=duration_ns,
            success=self._error is None,
            error_msg=self._error,
        )

        # Do not suppress exceptions — let them propagate normally
        return False


class TelemetryStore:
    """Async telemetry store that persists metrics to a local SQLite database.

    All database writes happen on a dedicated background thread via an
    in-memory queue, ensuring zero latency impact on the calling code.

    :param db_path: Path to the SQLite database file.  Created automatically
                    if it does not exist.  Defaults to ``greeting_telemetry.db``
                    in the project root.

    Example::

        store = TelemetryStore()
        store.start()

        with store.measure("greeting") as ctx:
            result = do_work()
            if result is None:
                ctx.fail("no result returned")

        store.stop()
    """

    def __init__(self, db_path: Path = _DEFAULT_DB) -> None:
        #: Path to the SQLite database file.
        self.db_path = Path(db_path)

        # Unbounded queue — writer thread drains it; main thread never blocks
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise the database schema and start the background writer thread.

        Safe to call multiple times — subsequent calls are no-ops if already
        running.
        """
        if self._running:
            return
        self._init_db()
        self._running = True
        self._thread = threading.Thread(
            target=self._writer_loop,
            name="telemetry-writer",
            daemon=True,   # exits automatically when the main process exits
        )
        self._thread.start()
        logger.debug("TelemetryStore started (db=%s)", self.db_path)

    def reset(self) -> None:
        """Delete all rows from the events table, keeping the schema intact.

        Safe to call whether or not the store has been started.  If the
        database file does not exist yet it is created with an empty schema.

        Typical use: ``make reset`` or ``make run RESET=1`` to start fresh.
        """
        self._init_db()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM events")
            conn.execute("DELETE FROM sqlite_sequence WHERE name='events'")
            conn.commit()
        logger.info("TelemetryStore reset: all events deleted.")

    def flush(self, timeout: float = 2.0) -> None:
        """Block until all queued events have been written to the database.

        Useful when you need to query historic stats immediately after
        recording an event.

        :param timeout: Maximum seconds to wait.
        """
        try:
            self._queue.join()
        except Exception:
            pass

    def stop(self, timeout: float = 5.0) -> None:
        """Flush the queue and stop the background writer thread.

        :param timeout: Maximum seconds to wait for the queue to drain.
        """
        if not self._running:
            return
        self._running = False
        self._queue.put(_STOP)
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.debug("TelemetryStore stopped.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @contextmanager
    def measure(self, event_type: str):
        """Context manager that times a block and records the result.

        :param event_type: A short label for the operation being measured
                           (e.g. ``"greeting"``, ``"tcp_request"``).
        :yields: A :class:`_MeasureContext` — call ``.fail(msg)`` on it
                 to mark the event as a fault.

        Example::

            with store.measure("greeting") as ctx:
                try:
                    do_work()
                except ValueError as e:
                    ctx.fail(str(e))
        """
        ctx = _MeasureContext(self, event_type)
        with ctx:
            yield ctx

    def record(
        self,
        event_type: str,
        duration_ns: int,
        success: bool = True,
        error_msg: Optional[str] = None,
    ) -> None:
        """Enqueue a pre-measured event for async persistence.

        Returns immediately — the write happens on the background thread.

        :param event_type: Short label for the operation.
        :param duration_ns: Wall-clock duration in nanoseconds.
        :param success: ``True`` if the operation succeeded.
        :param error_msg: Optional error description when ``success=False``.
        """
        self._enqueue(event_type, duration_ns, success, error_msg)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enqueue(
        self,
        event_type: str,
        duration_ns: int,
        success: bool,
        error_msg: Optional[str],
    ) -> None:
        """Put an event tuple onto the async write queue."""
        if not self._running:
            return
        timestamp = datetime.now(timezone.utc).isoformat()
        self._queue.put((timestamp, event_type, duration_ns, int(success), error_msg))

    def _init_db(self) -> None:
        """Create the database file and schema if they do not already exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT    NOT NULL,
                    event_type  TEXT    NOT NULL,
                    duration_ns INTEGER NOT NULL,
                    success     INTEGER NOT NULL,
                    error_msg   TEXT
                )
            """)
            # Index for fast per-type and time-range queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type
                ON events (event_type)
            """)
            conn.commit()

    def _writer_loop(self) -> None:
        """Background thread: drain the queue and write rows to SQLite."""
        conn = sqlite3.connect(self.db_path)
        try:
            while True:
                item = self._queue.get()
                if item is _STOP:
                    self._drain(conn)
                    self._queue.task_done()
                    break
                self._write_row(conn, item)
                self._queue.task_done()
        except Exception as exc:
            logger.error("Telemetry writer error: %s", exc)
        finally:
            conn.close()

    def _drain(self, conn: sqlite3.Connection) -> None:
        """Write all remaining queued items without blocking."""
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                if item is not _STOP:
                    self._write_row(conn, item)
            except queue.Empty:
                break

    @staticmethod
    def _write_row(conn: sqlite3.Connection, item: tuple) -> None:
        """Insert a single event row and commit."""
        try:
            conn.execute(
                "INSERT INTO events (timestamp, event_type, duration_ns, success, error_msg) "
                "VALUES (?, ?, ?, ?, ?)",
                item,
            )
            conn.commit()
        except sqlite3.Error as exc:
            logger.warning("Telemetry write failed: %s", exc)
