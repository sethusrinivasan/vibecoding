"""
greeting.py
~~~~~~~~~~~
Provides the :class:`Greeting` class which composes a time-aware, colourised
greeting message and optionally appends a Quote of the Day (RFC 865).

Telemetry is recorded asynchronously via :class:`~telemetry.TelemetryStore`
when a store is supplied — the main flow is never blocked.

Typical usage::

    from greeting import Greeting
    Greeting("Alice").run()
    # => "Good morning, Alice!  [09:30 AM]"

    from greeting import Greeting
    from quote_provider import QuoteProvider
    Greeting("Alice", quote_provider=QuoteProvider()).run()
    # => "Good morning, Alice!  [09:30 AM]"
    #    "The only way to do great work is to love what you do."
"""

import re
import time
from datetime import datetime
from typing import Optional
from colorama import init
from time_of_day import TimeOfDay
from quote_provider import QuoteProvider
from telemetry import TelemetryStore
from stats import StatsReporter

# Ensure colorama resets colour codes automatically after each print call
# so subsequent terminal output is not affected.
init(autoreset=True)

# Strip ANSI/VT100 escape sequences (e.g. \033[2J) then non-printable chars (T-01)
# Pattern matches ESC followed by optional [ and parameter/command bytes
_ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
_SAFE_NAME_RE = re.compile(r'[^\x20-\x7E]')
_MAX_NAME_LEN = 100


class Greeting:
    """Builds and displays a time-aware greeting for a named recipient.

    The greeting salutation and terminal colour are determined by the
    :class:`~time_of_day.TimeOfDay` period derived from the current (or
    supplied) hour.

    Optionally appends a Quote of the Day sourced from a
    :class:`~quote_provider.QuoteProvider` instance, implementing the
    spirit of :rfc:`865` for terminal display.

    :param name: The recipient's name. Defaults to ``"World"``.
    :param quote_provider: An optional :class:`~quote_provider.QuoteProvider`.
                           When supplied, :meth:`run` prints a quote below
                           the greeting. Defaults to ``None`` (no quote).

    Example::

        >>> from quote_provider import QuoteProvider
        >>> g = Greeting("Dev", quote_provider=QuoteProvider(seed=0))
        >>> g.build(datetime(2026, 3, 22, 9, 30))
        'Good morning, Dev!  [09:30 AM]'
    """

    def __init__(
        self,
        name: str = "World",
        quote_provider: Optional[QuoteProvider] = None,
        telemetry: Optional[TelemetryStore] = None,
    ) -> None:
        # First strip full ANSI escape sequences (e.g. \033[2J), then any
        # remaining non-printable bytes, then enforce max length (T-01, T-03)
        sanitised = _ANSI_ESCAPE_RE.sub('', str(name))
        sanitised = _SAFE_NAME_RE.sub('', sanitised)[:_MAX_NAME_LEN]
        #: The name of the person being greeted.
        self.name: str = sanitised if sanitised else "World"

        #: Optional quote provider; when set, run() appends a daily quote.
        self.quote_provider: Optional[QuoteProvider] = quote_provider

        #: Optional telemetry store; when set, run() records metrics async.
        self.telemetry: Optional[TelemetryStore] = telemetry

    def build(self, now: datetime = None) -> str:
        """Construct the greeting string for the given datetime.

        Combines the :attr:`~time_of_day.TimeOfDay.salutation` for the
        current period with the recipient name and a formatted timestamp.

        :param now: The datetime to use for period and time-string resolution.
                    Defaults to :func:`datetime.now` when ``None``.
        :returns: A formatted greeting string, e.g.
                  ``"Good morning, World!  [09:30 AM]"``.
        """
        # Fall back to the real current time if no datetime is injected
        if now is None:
            now = datetime.now()

        # Resolve which period of the day we are in
        period = TimeOfDay.from_hour(now.hour)

        # Format the clock time as a human-readable 12-hour string
        time_str = now.strftime("%I:%M %p")

        return f"{period.salutation}, {self.name}!  [{time_str}]"

    def run(self, now: datetime = None) -> None:
        """Print the colourised greeting to stdout.

        Measures wall-clock response time and records it asynchronously via
        :attr:`telemetry` (if set).  After printing, a per-request statistical
        summary and the all-time historic summary are printed to stdout.

        :param now: The datetime to use. Defaults to :func:`datetime.now`
                    when ``None``, making this method use the live system clock.
        """
        # Fall back to the real current time if no datetime is injected
        if now is None:
            now = datetime.now()

        # Determine the period once so both color and build use the same hour
        period = TimeOfDay.from_hour(now.hour)

        # --- Timed block: measure greeting + quote output ---
        t_start = time.perf_counter_ns()
        error: Optional[str] = None
        try:
            # colorama autoreset ensures the colour does not bleed into later output
            print(period.color + self.build(now))

            # Optionally append a Quote of the Day (RFC 865) below the greeting
            if self.quote_provider is not None:
                quote = self.quote_provider.get()
                print(quote)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration_ns = time.perf_counter_ns() - t_start

            # Fire-and-forget async telemetry write — never blocks main flow
            if self.telemetry is not None:
                self.telemetry.record(
                    event_type="greeting",
                    duration_ns=duration_ns,
                    success=error is None,
                    error_msg=error,
                )
                # Flush the async queue so the current event is persisted
                # before we query the historic summary
                self.telemetry.flush()
                # Print per-request and historic stats summaries
                reporter = StatsReporter(self.telemetry)
                session = reporter.session_summary(
                    [duration_ns],
                    label="this request",
                    fault_count=0 if error is None else 1,
                )
                print(reporter.format_summary(session))
                historic = reporter.historic_summary("greeting")
                print(reporter.format_summary(historic, label="all-time greeting"))


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "World"
    store = TelemetryStore()
    store.start()
    Greeting(name=name, quote_provider=QuoteProvider(), telemetry=store).run()
    store.stop()
