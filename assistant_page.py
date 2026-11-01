"""Sprout page: the question and answer, the plant suggestion row, the typed
question box and the mic."""
import tkinter as tk

from mic import MicButton
from theme import get_font, paint
from widgets import make_button, make_line, make_row_text, say, text_width
from zones import TextZone, RowZone

WRAP_CHARACTERS = 60    # answers wrap at about this many characters
SIDE_MARGIN = 70        # ...but never closer than this to the window's sides


class AssistantPage:
    def __init__(self, root, put, on_submit, on_mic_tap, on_yes, on_no,
                 on_clear, window_width):
        """on_submit(event): Return pressed in the box. on_mic_tap(event).
        on_yes(), on_no(): the answer to "Make Basil your plant?".
        on_clear(): the Clear button. window_width: in pixels."""
        self.window_width = window_width
        self.shown = False       # is this page on screen?
        self.has_row = False     # does the suggestion row have something?
        self._build_text(root, put)
        self._build_suggestion_row(root, put, on_yes, on_no, on_clear)
        self._build_ask_row(root, put, on_submit, on_mic_tap)
        # The suggestion row isn't listed: it's shown only when it has
        # something in it (see _place_row)
        self.widgets = [self.zone, self.ask_row]
        self.zones = [self.zone, self.row, self.ask_row]
        self.update_wrap()

    # -- building -------------------------------------------------------
    def _build_text(self, root, put):
        self.zone = TextZone(root, pad_top=14, pad_bottom=4)
        paint(self.zone, bg="BG")
        put(self.zone, show=False, row=2, column=0, columnspan=2, sticky="nsew")
        self.hint = make_line(
            self.zone, "Tap the mic or ask Sprout, e.g. \"I'm planting basil\"",
            "caption", "MUTED", wraplength=700)
        self.question_label = make_line(self.zone, "", "body", "MUTED",
                                        gap=10, align="left")
        self.reply_label = make_line(self.zone, "", "body", "TEXT", gap=6,
                                     align="left")

    def _build_suggestion_row(self, root, put, on_yes, on_no, on_clear):
        """"Make Basil your plant? [Yes] [No]", or what came of it, or the
        follow-up hint and Clear."""
        self.row = RowZone(root, pad_top=4, pad_bottom=2)
        paint(self.row, bg="BG")
        self.row_grid = dict(row=3, column=0, columnspan=2, sticky="ew")
        self.row_text = make_row_text(self.row, "", "body", "TEXT",
                                      padx=(0, 12))
        self.yes = make_button(self.row, "Yes", on_yes, primary=True)
        self.row.add_widget(self.yes, padx=(0, 8))
        self.no = make_button(self.row, "No", on_no)
        self.row.add_widget(self.no)
        self.memory_hint = make_row_text(
            self.row, "Sprout remembers your last 2 questions", "caption", "MUTED",
            padx=(0, 12))
        self.clear = make_button(self.row, "Clear", on_clear)
        self.row.add_widget(self.clear)

    def _build_ask_row(self, root, put, on_submit, on_mic_tap):
        self.ask_row = RowZone(root, pad_top=4, pad_bottom=2)
        paint(self.ask_row, bg="BG")
        put(self.ask_row, show=False, row=4, column=0, columnspan=2, sticky="ew")
        make_row_text(self.ask_row, "Ask Sprout:", "body", "MUTED", padx=(0, 10))
        self.entry = tk.Entry(self.ask_row, font=get_font("body"), width=34,
                              relief="flat", highlightthickness=1)
        paint(self.entry, bg="CARD", fg="TEXT", insertbackground="TEXT",
              highlightbackground="CONTROL_BORDER", highlightcolor="ACCENT")
        self.ask_row.add_widget(self.entry, extra_height=10)
        self.entry.bind("<Return>", on_submit)

        self.mic = MicButton(self.ask_row)
        self.ask_row.add_widget(self.mic.canvas, padx=(10, 0))
        self.mic.bind(on_mic_tap)

    # -- updating -------------------------------------------------------
    def update_wrap(self):
        """Wrap the question and answer at about WRAP_CHARACTERS characters
        of the current answer font (call again after a text-size change)."""
        width = min(text_width(WRAP_CHARACTERS), self.window_width - SIDE_MARGIN)
        for label in (self.question_label, self.reply_label):
            label.config(wraplength=width)

    def render(self, view):
        """Draw the question, the answer and the suggestion row from the
        assistant's view (see assistant.View)."""
        say(self.question_label, f"You: {view.question}" if view.question else "",
            "MUTED")
        if view.note:
            say(self.reply_label, view.note, "MUTED")
        else:
            say(self.reply_label, f"Sprout: {view.answer}" if view.answer else "",
                "TEXT")

        if view.suggestion:
            self._fill_row(f"Make {view.suggestion} your plant?", "TEXT",
                           buttons=True)
        elif view.switched_to:
            self._fill_row(f"Okay, Sprout is now watching {view.switched_to}.",
                           "TEXT")
        elif view.has_history:
            self._fill_row("", "TEXT", memory=True)
        else:
            self.has_row = False
        self._place_row()

    def show_reply(self, text, role):
        """Show a message in the answer's place (e.g. a theme that failed)."""
        say(self.reply_label, text, role)

    def _fill_row(self, text, role, buttons=False, memory=False):
        say(self.row_text, text, role)
        self.row.show_part(self.row_text, bool(text))
        for part in (self.yes, self.no):
            self.row.show_part(part, buttons)
        for part in (self.memory_hint, self.clear):
            self.row.show_part(part, memory)
        self.has_row = True

    def _place_row(self):
        if self.shown and self.has_row:
            self.row.grid(**self.row_grid)
        else:
            self.row.grid_remove()

    def set_shown(self, shown):
        """The app shows or hides this page."""
        self.shown = shown
        self._place_row()

    def focus(self):
        self.entry.focus_set()
