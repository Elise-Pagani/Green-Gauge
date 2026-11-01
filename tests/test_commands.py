"""Routing typed / spoken text, and finding plant names in it.

Run from the project folder: python3 -m unittest discover -s tests
"""
import unittest

from commands import Command, find_plant, handle_command
from plant_db import init_db


def setUpModule():
    init_db()


class RoutingTests(unittest.TestCase):
    def check(self, text, kind, plant):
        self.assertEqual(handle_command(text), Command(kind, plant), text)

    def test_selection_statements(self):
        self.check("I'm planting basil", "select", "Basil")
        self.check("growing Tomatoes this year", "select", "Tomato")
        self.check("switch to cacti", "select", "Cactus")
        self.check("Change to lettuce please", "select", "Lettuce")
        self.check("my plant is mint", "select", "Mint")
        self.check("I want to grow strawberries", "select", "Strawberry")
        self.check("select orchid", "select", "Orchid")

    def test_just_the_plant_name(self):
        self.check("basil", "select", "Basil")
        self.check("tomatoes", "select", "Tomato")
        self.check("  Bell Peppers! ", "select", "Bell Pepper")

    def test_questions_are_asked(self):
        self.check("Tell me about basil", "ask", "Basil")
        self.check("what about bell peppers?", "ask", "Bell Pepper")
        self.check("How humid should it be for lettuce", "ask", "Lettuce")
        self.check("Should I grow basil?", "ask", "Basil")
        self.check("Is it too hot in here?", "ask", None)

    def test_other_text_is_asked(self):
        self.check("thanks", "ask", None)
        self.check("I'm planting dragon fruit", "ask", None)
        self.check("my basil plant is wilting", "ask", "Basil")

    def test_dropdown_message_is_gone(self):
        self.assertEqual(len(handle_command("dragon fruit")), 2)   # just (kind, plant)


class FindPlantTests(unittest.TestCase):
    def test_plurals(self):
        cases = {
            "basils": "Basil",
            "tomatoes": "Tomato",
            "cucumbers": "Cucumber",
            "strawberries": "Strawberry",
            "cacti": "Cactus",
            "cactuses": "Cactus",
            "bell peppers": "Bell Pepper",
            "lettuces": "Lettuce",
        }
        for text, plant in cases.items():
            self.assertEqual(find_plant(text), plant, text)

    def test_aliases(self):
        for text in ("pepper", "peppers", "capsicum"):
            self.assertEqual(find_plant(text), "Bell Pepper", text)
        for text in ("phalaenopsis", "orchids"):
            self.assertEqual(find_plant(text), "Orchid", text)

    def test_case_insensitive(self):
        self.assertEqual(find_plant("I LOVE STRAWBERRIES"), "Strawberry")

    def test_whole_words_only(self):
        self.assertIsNone(find_plant("peppermint"))
        self.assertIsNone(find_plant("some peppermint tea"))
        self.assertIsNone(find_plant("basilica"))
        self.assertIsNone(find_plant("cactusy"))

    def test_longest_match_first(self):
        self.assertEqual(find_plant("bell peppers"), "Bell Pepper")
        self.assertEqual(find_plant("mint and bell peppers"), "Bell Pepper")

    def test_no_plant(self):
        self.assertIsNone(find_plant("dragon fruit"))
        self.assertIsNone(find_plant(""))


if __name__ == "__main__":
    unittest.main()
