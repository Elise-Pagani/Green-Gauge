"""The assistant's state, shared by typed questions and the mock mic.

No Tk here: the GUI calls submit() / tap_mic() / tick() / poll() and draws
whatever view() says. One state for both inputs means a question can't be
asked while another one is being answered, and canceling really cancels.

Modes:  idle -> listening -> heard -> thinking -> idle   (mock mic)
        idle -> thinking -> idle                         (typed question)

The LLM runs in a worker thread that only puts (request_id, answer) on a
queue; poll() picks answers up on the GUI's thread. Every request gets a new
ID and cancel() moves the ID on, so a late answer from a canceled request is
thrown away when it arrives. (The HTTP call itself can't be stopped.)
"""
import queue
import threading
import traceback
from collections import namedtuple

from commands import handle_command

# There is no microphone, so voice input is a Wizard-of-Oz simulation:
# tapping the mic plays a "listening" animation, "hears" the next sample
# phrase below, then runs it exactly like typed text (real LLM answer). Edit
# the phrases to whatever you want to demo. Tap again while it is active to
# cancel.
MOCK_PHRASES = [
    "What humidity does basil like?",
    "I'm planting tomatoes",
    "Is it too hot for lettuce?",
]
LISTEN_FRAMES = 44   # about 2.2 seconds at 50 ms per frame
HEARD_FRAMES = 16    # about 0.8 seconds

BUSY_REPLIES = {
    "listening": "Sprout is still listening…",
    "heard": "Sprout is still listening…",
    "thinking": "Sprout is still answering…",
}

# What the GUI shows: the mic's mode and animation frame, and the reply line
# (its text and color role)
View = namedtuple("View", "mode frame reply reply_role")


def _start_thread(work):
    threading.Thread(target=work, daemon=True).start()


class Assistant:
    def __init__(self, get_context, on_plant, on_change=None, ask=None,
                 run_in_background=_start_thread):
        """get_context(): (selected plant name or None, reading or None).
        on_plant(name): the text selected a plant.
        on_change(): the view changed and should be redrawn.
        ask(question, plant, reading): the LLM call (default: llm.ask).
        run_in_background(work): runs work() off the GUI thread."""
        if ask is None:
            from llm import ask
        self._ask = ask
        self._get_context = get_context
        self._on_plant = on_plant
        self._on_change = on_change or (lambda: None)
        self._run_in_background = run_in_background
        self._answers = queue.Queue()
        self.request_id = 0
        self.mode = "idle"
        self.frame = 0
        self.reply, self.reply_role = "", "MUTED"
        self.next_phrase = 0
        self.heard_phrase = ""

    def view(self):
        return View(self.mode, self.frame, self.reply, self.reply_role)

    # -- input ----------------------------------------------------------
    def submit(self, text):
        """Typed text. Returns True if it was taken (the box can be cleared)."""
        if not text.strip():
            return False
        if self.mode != "idle":
            self._set(reply=BUSY_REPLIES[self.mode], role="MUTED")
            return False
        self._process(text)
        return True

    def tap_mic(self):
        """Start listening, or cancel whatever is going on."""
        if self.mode == "idle":
            self._set("listening", "Listening...", "MUTED")
        else:
            self.cancel()

    def cancel(self):
        self.request_id += 1   # a late answer to the old request is dropped
        self._set("idle", "", "MUTED")

    # -- timers ---------------------------------------------------------
    def tick(self):
        """One animation frame (the GUI calls this every 50 ms)."""
        if self.mode == "idle":
            return
        self.frame += 1
        if self.mode == "listening" and self.frame >= LISTEN_FRAMES:
            phrase = MOCK_PHRASES[self.next_phrase % len(MOCK_PHRASES)]
            self.next_phrase += 1
            self.heard_phrase = phrase
            self._set("heard", f'Heard: "{phrase}"', "TEXT")
        elif self.mode == "heard" and self.frame >= HEARD_FRAMES:
            self._process(self.heard_phrase)
        else:
            self._on_change()

    def poll(self):
        """Pick up finished answers (the GUI calls this regularly)."""
        while True:
            try:
                request_id, answer = self._answers.get_nowait()
            except queue.Empty:
                return
            if request_id == self.request_id and self.mode == "thinking":
                self._set("idle", answer, "TEXT")

    # -- inside ---------------------------------------------------------
    def _process(self, text):
        """Typed text and (mock) voice both end up here."""
        plant_name, reply, ask_llm = handle_command(text)
        if plant_name is not None:
            self._on_plant(plant_name)
        if ask_llm:
            self._ask_in_background(text)
        else:
            self._set("idle", reply, "MUTED")

    def _ask_in_background(self, text):
        self.request_id += 1
        request_id = self.request_id
        plant, reading = self._get_context()

        def work():
            try:
                answer = self._ask(text, plant, reading)
            except Exception:   # llm.ask shouldn't raise, but never hang
                traceback.print_exc()
                answer = "Something went wrong. Please try again."
            self._answers.put((request_id, answer))

        self._set("thinking", "Thinking...", "MUTED")
        self._run_in_background(work)

    def _set(self, mode=None, reply=None, role=None):
        if mode is not None and mode != self.mode:
            self.mode, self.frame = mode, 0
        if reply is not None:
            self.reply, self.reply_role = reply, role
        self._on_change()
