"""
Unit tests for TimeOfDay enum.
Each test isolates a single behaviour of TimeOfDay with no external dependencies.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from colorama import Fore
from time_of_day import TimeOfDay


class TestTimeOfDayFromHour(unittest.TestCase):
    """from_hour() classification including all boundary hours."""

    def test_boundary_start_morning(self):
        self.assertEqual(TimeOfDay.from_hour(6), TimeOfDay.MORNING)

    def test_boundary_end_morning(self):
        self.assertEqual(TimeOfDay.from_hour(11), TimeOfDay.MORNING)

    def test_boundary_start_afternoon(self):
        self.assertEqual(TimeOfDay.from_hour(12), TimeOfDay.AFTERNOON)

    def test_boundary_end_afternoon(self):
        self.assertEqual(TimeOfDay.from_hour(17), TimeOfDay.AFTERNOON)

    def test_boundary_start_evening(self):
        self.assertEqual(TimeOfDay.from_hour(18), TimeOfDay.EVENING)

    def test_boundary_end_evening(self):
        self.assertEqual(TimeOfDay.from_hour(20), TimeOfDay.EVENING)

    def test_boundary_start_night(self):
        self.assertEqual(TimeOfDay.from_hour(21), TimeOfDay.NIGHT)

    def test_midnight(self):
        self.assertEqual(TimeOfDay.from_hour(0), TimeOfDay.NIGHT)

    def test_pre_dawn(self):
        self.assertEqual(TimeOfDay.from_hour(5), TimeOfDay.NIGHT)

    def test_late_night(self):
        self.assertEqual(TimeOfDay.from_hour(23), TimeOfDay.NIGHT)


class TestTimeOfDayColor(unittest.TestCase):
    """color property maps each period to the correct Fore code."""

    def test_morning_color(self):
        self.assertEqual(TimeOfDay.MORNING.color, Fore.YELLOW)

    def test_afternoon_color(self):
        self.assertEqual(TimeOfDay.AFTERNOON.color, Fore.CYAN)

    def test_evening_color(self):
        self.assertEqual(TimeOfDay.EVENING.color, Fore.MAGENTA)

    def test_night_color(self):
        self.assertEqual(TimeOfDay.NIGHT.color, Fore.BLUE)


class TestTimeOfDaySalutation(unittest.TestCase):
    """salutation property returns the correct greeting string."""

    def test_morning_salutation(self):
        self.assertEqual(TimeOfDay.MORNING.salutation, "Good morning")

    def test_afternoon_salutation(self):
        self.assertEqual(TimeOfDay.AFTERNOON.salutation, "Good afternoon")

    def test_evening_salutation(self):
        self.assertEqual(TimeOfDay.EVENING.salutation, "Good evening")

    def test_night_salutation(self):
        self.assertEqual(TimeOfDay.NIGHT.salutation, "Good night")


if __name__ == "__main__":
    unittest.main()
