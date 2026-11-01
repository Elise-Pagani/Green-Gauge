"""How readings, ranges and warnings are written (units.py, check_conditions)."""
import unittest

import units
from plant_db import check_conditions

PLANT = {"name": "Tomato", "min_temp": 18, "max_temp": 27, "min_hum": 50, "max_hum": 70}


class UnitsTests(unittest.TestCase):
    def test_readings_have_one_decimal(self):
        self.assertEqual(units.reading(24.31), "24.3")
        self.assertEqual(units.reading(24), "24.0")
        self.assertEqual(units.temperature(24.3), "24.3 °C")
        self.assertEqual(units.humidity(61), "61.0% RH")

    def test_ranges_use_an_en_dash(self):
        self.assertEqual(units.DASH, "–")
        self.assertEqual(units.temperature_range(18, 27), "18–27 °C")
        self.assertEqual(units.humidity_range(50, 70), "50–70% RH")
        self.assertEqual(units.ph_range(6, 6.5), "pH 6.0–6.5")

    def test_range_ends_are_whole_unless_they_have_a_half(self):
        self.assertEqual(units.temperature_range(18.0, 27.0), "18–27 °C")
        self.assertEqual(units.temperature_range(18.5, 27), "18.5–27 °C")
        self.assertEqual(units.humidity_range(40, 62.5), "40–62.5% RH")

    def test_missing_ends_give_a_dash(self):
        for write in (units.temperature_range, units.humidity_range, units.ph_range):
            self.assertEqual(write(None, None), "–", write.__name__)
            self.assertEqual(write(6, None), "–", write.__name__)
            self.assertEqual(write(None, 7), "–", write.__name__)

    def test_ideal_ranges(self):
        self.assertEqual(units.ideal_ranges(PLANT), "18–27 °C, 50–70% RH")

    def test_ellipsis_is_one_character(self):
        self.assertEqual(units.ELLIPSIS, "…")


class CheckConditionsTests(unittest.TestCase):
    def test_ideal(self):
        self.assertEqual(check_conditions(PLANT, 24, 60), (True, []))
        # The range ends themselves are still ideal
        self.assertEqual(check_conditions(PLANT, 18, 70), (True, []))

    def test_hot_and_humid(self):
        ok, messages = check_conditions(PLANT, 33, 85)
        self.assertFalse(ok)
        self.assertEqual(messages, ["Too hot (33.0 °C, ideal 18–27 °C)",
                                    "Too humid (85.0% RH, ideal 50–70% RH)"])

    def test_cold_and_dry(self):
        ok, messages = check_conditions(PLANT, 12.46, 31.5)
        self.assertFalse(ok)
        self.assertEqual(messages, ["Too cold (12.5 °C, ideal 18–27 °C)",
                                    "Too dry (31.5% RH, ideal 50–70% RH)"])

    def test_one_problem_only(self):
        self.assertEqual(check_conditions(PLANT, 24, 45),
                         (False, ["Too dry (45.0% RH, ideal 50–70% RH)"]))


if __name__ == "__main__":
    unittest.main()
