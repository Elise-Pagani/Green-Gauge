"""Sprout's state, shared by typed questions and the mock mic.

No Tk here: the GUI calls submit() / tap_mic() / tick() / poll() and draws
whatever view() says. One state for both inputs means a question can't be
asked while another one is being answered, and canceling really cancels.

Modes:  idle -> listening -> heard -> thinking -> idle   (mock mic)
        idle -> thinking -> idle                         (typed question)

The LLM runs in a worker thread that only puts its result on a queue;
poll() picks answers up on the GUI's thread. Every request gets a new ID and
cancel() moves the ID on, so a late answer from a canceled request is thrown
away when it arrives. (The HTTP call itself can't be stopped.)

Sprout never changes the user's plant by itself. When the text chooses a
plant, or a question mentions a plant other than the user's, Sprout only
SUGGESTS it; accept_suggestion() (the Yes button) makes it the user's plant.

Follow-up questions: the last HISTORY_PAIRS (question, answer) pairs are
sent with each new question. Only real answers are kept (not errors, not
canceled requests), and the history is forgotten when the user's plant
changes or the user taps Clear.
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
    "And what temperature?",   # a follow-up: Sprout remembers it was basil
    "I'm planting tomatoes",
    "Is it too hot for lettuce?",
]
LISTEN_FRAMES = 44   # about 2.2 seconds at 50 ms per frame
HEARD_FRAMES = 16    # about 0.8 seconds
HISTORY_PAIRS = 2    # how many earlier questions Sprout remembers

BUSY_REPLIES = {
    "listening": "Sprout is still listening…",
    "heard": "Sprout is still listening…",
    "thinking": "Sprout is still answering…",
}

# What the GUI shows:
#   mode, frame   the mic's mode and animation frame
#   question      the latest question ("" for none)
#   answer        Sprout's answer to it ("" for none yet)
#   note          a short status line shown instead of the answer while it
#                 isn't "" (e.g. "Sprout is thinking…")
#   suggestion    a plant waiting for the user's Yes / No, or None
#   switched_to   the plant the user just said Yes to, or None
#   has_history   True when there is something for Clear to forget
View = namedtuple("View", "mode frame question answer note suggestion "
                          "switched_to has_history")

# What the worker thread hands back
Answer = namedtuple("Answer", "request_id question plant ok text")


def _start_thread(work):
    threading.Thread(target=work, daemon=True).start()


class Assistant:
    def __init__(self, get_context, on_plant, on_change=None, ask=None,
                 run_in_background=_start_thread):
        """get_context(): (the user's plant name or None, reading or None).
        on_plant(name): the user said Yes to making name their plant.
        on_change(): the view changed and should be redrawn.
        ask(question, plant, reading, history): the LLM call, returning
            (ok, text) (default: llm.ask).
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
        self.question, self.answer, self.note = "", "", ""
        self.suggestion = None
        self.switched_to = None
        self.history = []        # (question, answer) pairs, oldest first
        self.history_epoch = 0   # moves on whenever the history is forgotten
        self.next_phrase = 0
        self.heard_phrase = ""

    def view(self):
        return View(self.mode, self.frame, self.question, self.answer,
                    self.note, self.suggestion, self.switched_to,
                    bool(self.history))

    # -- input ----------------------------------------------------------
    def submit(self, text):
        """Typed text. Returns True if it was taken (the box can be cleared)."""
        if not text.strip():
            return False
        if self.mode != "idle":
            self._set(note=BUSY_REPLIES[self.mode])
            return False
        self._process(text.strip())
        return True

    def tap_mic(self):
        """Start listening, or cancel whatever is going on."""
        if self.mode == "idle":
            self._start_exchange("")
            self._set("listening", note="Listening…")
        else:
            self.cancel()

    def cancel(self):
        self.request_id += 1   # a late answer to the old request is dropped
        self._set("idle", note="")

    # -- the plant suggestion -------------------------------------------
    def accept_suggestion(self):
        """Yes: the suggested plant becomes the user's plant."""
        name = self.suggestion
        if name is None:
            return
        self.suggestion, self.switched_to = None, name
        self._on_plant(name)   # the app then calls plant_changed()
        self._on_change()

    def decline_suggestion(self):
        """No: just forget the suggestion."""
        self.suggestion = None
        self._on_change()

    def plant_changed(self, name):
        """The user's plant changed (any way): earlier questions were about
        another plant, so forget them."""
        self.forget_history()
        if self.suggestion == name:   # nothing left to suggest
            self.suggestion = None
        self._on_change()

    # -- history --------------------------------------------------------
    def forget_history(self):
        self.history = []
        self.history_epoch += 1   # an answer on its way isn't kept either

    def clear(self):
        """The Clear button: stop, forget the history and empty the page."""
        self.forget_history()
        self.cancel()
        self._start_exchange("")
        self._on_change()

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
            self.question = phrase   # shown as the question straight away
            self._set("heard", note="")
        elif self.mode == "heard" and self.frame >= HEARD_FRAMES:
            self._process(self.heard_phrase)
        else:
            self._on_change()

    def poll(self):
        """Pick up finished answers (the GUI calls this regularly)."""
        while True:
            try:
                result, epoch = self._answers.get_nowait()
            except queue.Empty:
                return
            if result.request_id == self.request_id and self.mode == "thinking":
                self._finish(result, epoch)

    # -- inside ---------------------------------------------------------
    def _start_exchange(self, question):
        """A new question replaces the last one and any pending suggestion."""
        self.question, self.answer, self.note = question, "", ""
        self.suggestion = self.switched_to = None

    def _process(self, text):
        """Typed text and (mock) voice both end up here."""
        self._start_exchange(text)
        command = handle_command(text)
        if command.kind == "select":
            active, _reading = self._get_context()
            if command.plant == active:
                self._set("idle", note=f"Sprout is already watching {active}.")
            else:
                self.suggestion = command.plant
                self._set("idle")
        else:
            self._ask_in_background(text, command.plant)

    def _ask_in_background(self, text, plant_mentioned):
        self.request_id += 1
        request_id, epoch = self.request_id, self.history_epoch
        active, reading = self._get_context()
        history = list(self.history)

        def work():
            try:
                ok, answer = self._ask(text, active, reading, history)
            except Exception:   # llm.ask shouldn't raise, but never hang
                traceback.print_exc()
                ok, answer = False, "Something went wrong. Please try again."
            result = Answer(request_id, text, plant_mentioned, ok, answer)
            self._answers.put((result, epoch))

        self._set("thinking", note="Sprout is thinking…")
        self._run_in_background(work)

    def _finish(self, result, epoch):
        if result.ok and epoch == self.history_epoch:
            self.history = (self.history + [(result.question, result.text)])[
                -HISTORY_PAIRS:]
        active, _reading = self._get_context()
        if result.ok and result.plant not in (None, active):
            self.suggestion = result.plant
        self.answer = result.text
        self._set("idle", note="")

    def _set(self, mode=None, note=None):
        if mode is not None and mode != self.mode:
            self.mode, self.frame = mode, 0
        if note is not None:
            self.note = note
        self._on_change()
