"""The assistant controller, with the LLM stubbed out (Ollama is never called).

Run from the project folder: python3 -m unittest discover -s tests
"""
import unittest
from unittest import mock

import assistant
from assistant import (Assistant, MOCK_PHRASES, LISTEN_FRAMES, HEARD_FRAMES,
                       HISTORY_PAIRS)
from plant_db import init_db


def setUpModule():
    init_db()


class Harness:
    """An Assistant whose background work waits until run() is called.
    Acts like the app: on_plant makes the plant active and tells the
    assistant about it."""

    def __init__(self, active="Basil"):
        self.questions = []
        self.plants = []
        self.pending = []
        self.active = active
        self.fail = False
        self.assistant = Assistant(
            get_context=lambda: (self.active, (24.0, 60.0)),
            on_plant=self.set_active,
            ask=self.fake_ask,
            run_in_background=self.pending.append,
        )

    def set_active(self, name):
        self.plants.append(name)
        self.active = name
        self.assistant.plant_changed(name)

    def fake_ask(self, question, plant, reading, history):
        self.questions.append((question, plant, reading, list(history)))
        if self.fail:
            return False, "Can't reach Ollama."
        return True, f"answer to {question}"

    def run(self):
        """Finish the background work and let the assistant pick it up."""
        while self.pending:
            self.pending.pop(0)()
        self.assistant.poll()

    def ask(self, question):
        self.assistant.submit(question)
        self.run()

    def tick(self, count):
        for _ in range(count):
            self.assistant.tick()


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.a = self.h.assistant

    def test_typed_question_thinks_then_answers(self):
        self.assertTrue(self.a.submit("What does basil like?"))
        self.assertEqual(self.a.mode, "thinking")
        self.assertEqual(self.a.note, "Sprout is thinking…")
        self.assertEqual(self.a.question, "What does basil like?")
        self.h.run()
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(self.a.note, "")
        self.assertEqual(self.a.answer, "answer to What does basil like?")
        self.assertEqual(self.h.questions,
                         [("What does basil like?", "Basil", (24.0, 60.0), [])])

    def test_mic_goes_listening_heard_thinking_idle(self):
        self.a.tap_mic()
        self.assertEqual(self.a.mode, "listening")
        self.h.tick(LISTEN_FRAMES - 1)
        self.assertEqual(self.a.mode, "listening")
        self.h.tick(1)
        self.assertEqual(self.a.mode, "heard")
        self.assertEqual(self.a.question, MOCK_PHRASES[0])   # shown as the question
        self.h.tick(HEARD_FRAMES)
        self.assertEqual(self.a.mode, "thinking")
        self.h.run()
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(self.a.answer, f"answer to {MOCK_PHRASES[0]}")

    def test_tap_while_thinking_cancels(self):
        self.a.submit("What does basil like?")
        self.a.tap_mic()
        self.assertEqual(self.a.mode, "idle")

    def test_tap_while_listening_cancels(self):
        self.a.tap_mic()
        self.h.tick(5)
        self.a.tap_mic()
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual((self.a.question, self.a.answer, self.a.note), ("", "", ""))

    def test_view_matches_state(self):
        self.a.tap_mic()
        self.h.tick(3)
        view = self.a.view()
        self.assertEqual((view.mode, view.frame), ("listening", 3))
        self.assertEqual(view.note, "Listening…")

    def test_on_change_is_called(self):
        changes = []
        a = Assistant(get_context=lambda: (None, None), on_plant=lambda name: None,
                      on_change=lambda: changes.append(1),
                      ask=lambda *args: (True, ""),
                      run_in_background=lambda work: None)
        a.tap_mic()
        a.tick()
        self.assertEqual(len(changes), 2)


class BusyTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.a = self.h.assistant

    def test_submit_while_thinking_is_refused(self):
        self.a.submit("What does basil like?")
        self.assertFalse(self.a.submit("And mint?"))
        self.assertEqual(self.a.note, "Sprout is still answering…")
        self.assertEqual(self.a.question, "What does basil like?")
        self.assertEqual(len(self.h.pending), 1)   # no second LLM call

    def test_submit_while_listening_is_refused(self):
        self.a.tap_mic()
        self.assertFalse(self.a.submit("What does basil like?"))
        self.assertEqual(self.a.mode, "listening")
        self.assertEqual(self.a.note, "Sprout is still listening…")
        self.assertEqual(self.h.pending, [])

    def test_empty_submit_is_a_no_op(self):
        self.h.ask("What does basil like?")
        for text in ("", "   ", "\t\n"):
            self.assertFalse(self.a.submit(text))
        self.assertEqual(self.a.answer, "answer to What does basil like?")
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(len(self.h.questions), 1)


class CancelTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.a = self.h.assistant

    def test_canceled_answer_is_dropped(self):
        self.a.submit("What does basil like?")
        self.a.cancel()
        self.h.run()   # the late answer arrives after the cancel
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(self.a.answer, "")

    def test_late_answer_does_not_replace_the_next_one(self):
        self.a.submit("first?")
        late = self.h.pending.pop()
        self.a.cancel()
        self.a.submit("second?")
        late()              # the canceled request finishes first
        self.a.poll()
        self.assertEqual(self.a.mode, "thinking")
        self.h.run()
        self.assertEqual(self.a.answer, "answer to second?")

    def test_failing_ask_still_answers(self):
        def broken(*args):
            raise OSError("boom")
        a = Assistant(get_context=lambda: (None, None), on_plant=lambda name: None,
                      ask=broken, run_in_background=lambda work: work())
        with mock.patch("traceback.print_exc"):   # keep the test output quiet
            a.submit("What does basil like?")
        a.poll()
        self.assertEqual(a.mode, "idle")
        self.assertTrue(a.answer)
        self.assertEqual(a.history, [])


class SuggestionTests(unittest.TestCase):
    """Sprout suggests a plant; only the user's Yes makes it theirs."""

    def setUp(self):
        self.h = Harness()
        self.a = self.h.assistant

    def test_plant_statement_suggests_without_llm(self):
        self.assertTrue(self.a.submit("I'm planting tomatoes"))
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(self.a.suggestion, "Tomato")
        self.assertEqual(self.h.plants, [])     # not set yet
        self.assertEqual(self.h.pending, [])    # no LLM call

    def test_yes_sets_the_plant(self):
        self.a.submit("I'm planting tomatoes")
        self.a.accept_suggestion()
        self.assertEqual(self.h.plants, ["Tomato"])
        self.assertIsNone(self.a.suggestion)
        self.assertEqual(self.a.switched_to, "Tomato")

    def test_no_just_hides_it(self):
        self.a.submit("I'm planting tomatoes")
        self.a.decline_suggestion()
        self.assertEqual(self.h.plants, [])
        self.assertIsNone(self.a.suggestion)
        self.assertIsNone(self.a.switched_to)

    def test_same_plant_is_not_suggested(self):
        self.a.submit("I'm planting basil")
        self.assertIsNone(self.a.suggestion)
        self.assertEqual(self.a.note, "Sprout is already watching Basil.")

    def test_question_about_other_plant_suggests_after_the_answer(self):
        self.a.submit("Tell me about mint")
        self.assertIsNone(self.a.suggestion)    # not while thinking
        self.h.run()
        self.assertEqual(self.a.suggestion, "Mint")
        self.assertEqual(self.h.plants, [])

    def test_question_about_active_plant_suggests_nothing(self):
        self.h.ask("Tell me about basil")
        self.assertIsNone(self.a.suggestion)

    def test_failed_answer_suggests_nothing(self):
        self.h.fail = True
        self.h.ask("Tell me about mint")
        self.assertIsNone(self.a.suggestion)

    def test_new_submission_hides_the_suggestion(self):
        self.a.submit("I'm planting tomatoes")
        self.h.ask("thanks")
        self.assertIsNone(self.a.suggestion)
        self.a.submit("I'm planting tomatoes")
        self.a.tap_mic()                        # the mic counts too
        self.assertIsNone(self.a.suggestion)

    def test_nothing_sets_the_plant_without_yes(self):
        for text in ("I'm planting tomatoes", "tomatoes", "Tell me about mint",
                     "switch to cacti"):
            self.h.ask(text)
        self.assertEqual(self.h.plants, [])

    def test_mock_mic_planting_ends_in_a_suggestion(self):
        planting = MOCK_PHRASES.index("I'm planting tomatoes")
        self.a.next_phrase = planting
        self.a.tap_mic()
        self.h.tick(LISTEN_FRAMES + HEARD_FRAMES)
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(self.a.suggestion, "Tomato")
        self.assertEqual(self.h.pending, [])


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.a = self.h.assistant

    def test_history_is_sent_in_order(self):
        self.h.ask("What humidity does basil like?")
        self.h.ask("And what temperature?")
        self.assertEqual(self.h.questions[1][3], [
            ("What humidity does basil like?",
             "answer to What humidity does basil like?")])

    def test_history_is_capped(self):
        for number in range(5):
            self.h.ask(f"question {number}?")
        self.assertEqual(len(self.a.history), HISTORY_PAIRS)
        self.assertEqual(HISTORY_PAIRS, 2)
        self.assertEqual([q for q, _a in self.a.history],
                         ["question 3?", "question 4?"])
        self.assertEqual(len(self.h.questions[-1][3]), HISTORY_PAIRS)

    def test_failed_answers_are_not_stored(self):
        self.h.ask("first?")
        self.h.fail = True
        self.h.ask("second?")
        self.assertEqual(self.a.history, [("first?", "answer to first?")])

    def test_canceled_answers_are_not_stored(self):
        self.a.submit("first?")
        self.a.cancel()
        self.h.run()
        self.assertEqual(self.a.history, [])

    def test_plant_change_clears_history(self):
        self.h.ask("What humidity does basil like?")
        self.a.submit("I'm planting tomatoes")
        self.a.accept_suggestion()
        self.assertEqual(self.a.history, [])
        self.assertFalse(self.a.view().has_history)

    def test_plant_change_from_plants_page_clears_history(self):
        self.h.ask("What humidity does basil like?")
        self.h.set_active("Mint")   # what the Plants page button does
        self.assertEqual(self.a.history, [])

    def test_answer_in_flight_during_plant_change_is_not_stored(self):
        self.a.submit("What humidity does basil like?")
        self.h.set_active("Mint")
        self.h.run()
        self.assertEqual(self.a.answer, "answer to What humidity does basil like?")
        self.assertEqual(self.a.history, [])

    def test_clear_forgets_and_empties_the_page(self):
        self.h.ask("What humidity does basil like?")
        self.assertTrue(self.a.view().has_history)
        self.a.clear()
        self.assertEqual(self.a.history, [])
        self.assertEqual((self.a.question, self.a.answer), ("", ""))
        self.h.ask("And what temperature?")
        self.assertEqual(self.h.questions[-1][3], [])

    def test_clear_while_thinking_drops_the_answer(self):
        self.h.ask("first?")
        self.a.submit("second?")
        self.a.clear()
        self.h.run()
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(self.a.history, [])
        self.assertEqual(self.a.answer, "")


class MockPhraseTests(unittest.TestCase):
    def test_phrases_cycle(self):
        h = Harness()
        heard = []
        for _ in range(len(MOCK_PHRASES) + 1):
            h.assistant.tap_mic()
            h.tick(LISTEN_FRAMES)
            heard.append(h.assistant.heard_phrase)
            h.assistant.cancel()
        self.assertEqual(heard, MOCK_PHRASES + MOCK_PHRASES[:1])

    def test_phrases_live_in_assistant(self):
        self.assertIs(assistant.MOCK_PHRASES, MOCK_PHRASES)
        self.assertGreaterEqual(len(MOCK_PHRASES), 3)

    def test_follow_up_comes_right_after_the_basil_question(self):
        basil = MOCK_PHRASES.index("What humidity does basil like?")
        self.assertEqual(MOCK_PHRASES[basil + 1], "And what temperature?")


if __name__ == "__main__":
    unittest.main()
