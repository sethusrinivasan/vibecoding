"""
time_of_day.py  (worker edition)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Colorama-free version of TimeOfDay for use in Cloudflare Workers and the
local HTTP dev server.  The ``color`` property returns a plain CSS colour
name instead of a terminal escape code.
"""

from enum import Enum


class TimeOfDay(Enum):
    """Classifies a 24-hour clock hour into one of four named periods.

    Periods and their hour ranges::

        MORNING   06:00 – 11:59
        AFTERNOON 12:00 – 17:59
        EVENING   18:00 – 20:59
        NIGHT     21:00 – 05:59
    """

    MORNING   = "morning"
    AFTERNOON = "afternoon"
    EVENING   = "evening"
    NIGHT     = "night"

    @classmethod
    def from_hour(cls, hour: int) -> "TimeOfDay":
        """Return the period for *hour* (0–23)."""
        if not isinstance(hour, int) or not (0 <= hour <= 23):
            raise ValueError(f"hour must be an integer 0–23, got {hour!r}")
        if 6 <= hour < 12:
            return cls.MORNING
        elif 12 <= hour < 18:
            return cls.AFTERNOON
        elif 18 <= hour < 21:
            return cls.EVENING
        else:
            return cls.NIGHT

    @property
    def color(self) -> str:
        """CSS colour name for HTML responses."""
        return {
            TimeOfDay.MORNING:   "#e6b800",   # warm yellow
            TimeOfDay.AFTERNOON: "#00bcd4",   # cyan
            TimeOfDay.EVENING:   "#e040fb",   # magenta
            TimeOfDay.NIGHT:     "#5c6bc0",   # indigo-blue
        }[self]

    @property
    def salutation(self) -> str:
        """Greeting prefix, e.g. ``"Good morning"``."""
        return {
            TimeOfDay.MORNING:   "Good morning",
            TimeOfDay.AFTERNOON: "Good afternoon",
            TimeOfDay.EVENING:   "Good evening",
            TimeOfDay.NIGHT:     "Good night",
        }[self]
