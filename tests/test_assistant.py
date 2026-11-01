"""The assistant controller, with the LLM stubbed out (Ollama is never called).

Run from the project folder: python3 -m unittest discover -s tests
"""
import unittest
from unittest import mock

import assistant
from assistant import Assistant, MOCK_PHRASES, LISTEN_FRAMES, HEARD_FRAMES
from plant_db import init_db


def setUpModule():
    init_db()


class Harness:
    """An Assistant whose background work waits until run() is called."""

    def __init__(self):
        self.questions = []
        self.plants = []
        self.pending = []
        self.assistant = Assistant(
            get_context=lambda: ("Basil", (24.0, 60.0)),
            on_plant=self.plants.append,
            ask=self.fake_ask,
            run_in_background=self.pending.append,
        )

    def fake_ask(self, question, plant, reading):
        self.questions.append((question, plant, reading))
        return f"answer to {question}"

    def run(self):
        """Finish the background work and let the assistant pick it up."""
        while self.pending:
            self.pending.pop(0)()
        self.assistant.poll()

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
        self.h.run()
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(self.a.reply, "answer to What does basil like?")
        self.assertEqual(self.h.questions,
                         [("What does basil like?", "Basil", (24.0, 60.0))])

    def test_mic_goes_listening_heard_thinking_idle(self):
        self.a.tap_mic()
        self.assertEqual(self.a.mode, "listening")
        self.h.tick(LISTEN_FRAMES - 1)
        self.assertEqual(self.a.mode, "listening")
        self.h.tick(1)
        self.assertEqual(self.a.mode, "heard")
        self.assertIn(MOCK_PHRASES[0], self.a.reply)
        self.h.tick(HEARD_FRAMES)
        self.assertEqual(self.a.mode, "thinking")
        self.h.run()
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(self.a.reply, f"answer to {MOCK_PHRASES[0]}")

    def test_plant_statement_selects_without_llm(self):
        self.assertTrue(self.a.submit("I'm planting basil"))
        self.assertEqual(self.h.plants, ["Basil"])
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(self.h.pending, [])

    def test_tap_while_thinking_cancels(self):
        self.a.submit("What does basil like?")
        self.a.tap_mic()
        self.assertEqual(self.a.mode, "idle")

    def test_tap_while_listening_cancels(self):
        self.a.tap_mic()
        self.h.tick(5)
        self.a.tap_mic()
        self.assertEqual(self.a.mode, "idle")
        self.assertEqual(self.a.reply, "")

    def test_view_matches_state(self):
        self.a.tap_mic()
        self.h.tick(3)
        view = self.a.view()
        self.assertEqual((view.mode, view.frame), ("listening", 3))

    def test_on_change_is_called(self):
        changes = []
        a = Assistant(get_context=lambda: (None, None), on_plant=lambda name: None,
                      on_change=lambda: changes.append(1), ask=lambda *args: "",
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
        self.assertEqual(self.a.reply, "Sprout is still answering…")
        self.assertEqual(len(self.h.pending), 1)   # no second LLM call

    def test_submit_while_listening_is_refused(self):
        self.a.tap_mic()
        self.assertFalse(self.a.submit("What does basil like?"))
        self.assertEqual(self.a.mode, "listening")
        self.assertEqual(self.a.reply, "Sprout is still listening…")
        self.assertEqual(self.h.pending, [])

    def test_empty_submit_is_a_no_op(self):
        self.a.submit("What does basil like?")
        self.h.run()
        for text in ("", "   ", "\t\n"):
            self.assertFalse(self.a.submit(text))
        self.assertEqual(self.a.reply, "answer to What does basil like?")
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
        self.assertEqual(self.a.reply, "")

    def test_late_answer_does_not_replace_the_next_one(self):
        self.a.submit("first?")
        late = self.h.pending.pop()
        self.a.cancel()
        self.a.submit("second?")
        late()              # the canceled request finishes first
        self.a.poll()
        self.assertEqual(self.a.mode, "thinking")
        self.h.run()
        self.assertEqual(self.a.reply, "answer to second?")

    def test_failing_ask_still_answers(self):
        def broken(*args):
            raise OSError("boom")
        a = Assistant(get_context=lambda: (None, None), on_plant=lambda name: None,
                      ask=broken, run_in_background=lambda work: work())
        with mock.patch("traceback.print_exc"):   # keep the test output quiet
            a.submit("What does basil like?")
        a.poll()
        self.assertEqual(a.mode, "idle")
        self.assertEqual(a.reply_role, "TEXT")


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


if __name__ == "__main__":
    unittest.main()
