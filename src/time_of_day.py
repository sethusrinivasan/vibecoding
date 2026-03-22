"""
time_of_day.py
~~~~~~~~~~~~~~
Defines the :class:`TimeOfDay` enum which classifies a 24-hour clock hour
into one of four named periods and exposes the associated terminal color
and greeting salutation for each period.
"""

from enum import Enum
from colorama import Fore


class TimeOfDay(Enum):
    """Represents a broad period of the day derived from the current hour.

    Each member carries two properties:

    * :attr:`color`      – a colorama ``Fore`` escape code for terminal output.
    * :attr:`salutation` – a human-readable greeting prefix (e.g. "Good morning").

    Periods and their hour ranges::

        MORNING   06:00 – 11:59   (yellow)
        AFTERNOON 12:00 – 17:59   (cyan)
        EVENING   18:00 – 20:59   (magenta)
        NIGHT     21:00 – 05:59   (blue)
    """

    MORNING   = "morning"
    AFTERNOON = "afternoon"
    EVENING   = "evening"
    NIGHT     = "night"

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_hour(cls, hour: int) -> "TimeOfDay":
        """Return the :class:`TimeOfDay` member that corresponds to *hour*.

        :param hour: An integer in the range 0–23 representing the hour of day.
        :returns: The matching :class:`TimeOfDay` member.

        Example::

            >>> TimeOfDay.from_hour(9)
            <TimeOfDay.MORNING: 'morning'>
            >>> TimeOfDay.from_hour(22)
            <TimeOfDay.NIGHT: 'night'>
        """
        if not isinstance(hour, int) or not (0 <= hour <= 23):
            raise ValueError(f"hour must be an integer 0–23, got {hour!r}")
        if 6 <= hour < 12:
            return cls.MORNING
        elif 12 <= hour < 18:
            return cls.AFTERNOON
        elif 18 <= hour < 21:
            return cls.EVENING
        else:
            # Covers 21:00–23:59 and the pre-dawn hours 00:00–05:59
            return cls.NIGHT

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def color(self) -> str:
        """The colorama ``Fore`` escape code associated with this period.

        Used to colorise terminal output so the greeting visually reflects
        the time of day.

        :returns: A colorama ``Fore.*`` string constant.
        """
        # Map each period to a distinct, intuitive terminal colour
        return {
            TimeOfDay.MORNING:   Fore.YELLOW,   # warm sunrise tone
            TimeOfDay.AFTERNOON: Fore.CYAN,     # bright midday tone
            TimeOfDay.EVENING:   Fore.MAGENTA,  # warm sunset tone
            TimeOfDay.NIGHT:     Fore.BLUE,     # cool night tone
        }[self]

    @property
    def salutation(self) -> str:
        """The greeting prefix for this period (e.g. ``"Good morning"``).

        :returns: A plain string without punctuation or a recipient name.
        """
        return {
            TimeOfDay.MORNING:   "Good morning",
            TimeOfDay.AFTERNOON: "Good afternoon",
            TimeOfDay.EVENING:   "Good evening",
            TimeOfDay.NIGHT:     "Good night",
        }[self]
