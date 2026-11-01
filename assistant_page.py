"""Assistant page: the reply text, the typed question box and the mic."""
import tkinter as tk

from mic import MicButton
from theme import get_font, paint
from widgets import make_line, make_row_text, say
from zones import TextZone, RowZone


class AssistantPage:
    def __init__(self, root, put, on_submit, on_mic_tap):
        """on_submit(event): Return pressed in the box. on_mic_tap(event)."""
        self.zone = TextZone(root, pad_top=14, pad_bottom=4)
        paint(self.zone, bg="BG")
        put(self.zone, show=False, row=2, column=0, columnspan=2, sticky="nsew")
        make_line(self.zone, "ASSISTANT", 14, "ACCENT", True)
        make_line(self.zone, "Tap the mic or type, e.g. \"I'm planting basil\"",
                  10, "MUTED", gap=2, wraplength=700)
        self.reply_label = make_line(self.zone, "", 12, "TEXT", gap=14,
                                     wraplength=700)

        self.ask_row = RowZone(root, pad_top=4, pad_bottom=2)
        paint(self.ask_row, bg="BG")
        put(self.ask_row, show=False, row=3, column=0, columnspan=2, sticky="ew")
        make_row_text(self.ask_row, "ASK:", 11, "MUTED", True, padx=(0, 10))
        self.entry = tk.Entry(self.ask_row, font=get_font(12), width=34,
                              relief="flat", highlightthickness=1)
        paint(self.entry, bg="CARD", fg="TEXT", insertbackground="TEXT",
              highlightbackground="BORDER", highlightcolor="ACCENT")
        self.ask_row.add_widget(self.entry, extra_height=10)
        self.entry.bind("<Return>", on_submit)

        self.mic = MicButton(self.ask_row)
        self.ask_row.add_widget(self.mic.canvas, padx=(10, 0))
        self.mic.bind(on_mic_tap)

        self.widgets = [self.zone, self.ask_row]
        self.zones = [self.zone, self.ask_row]

    def show_reply(self, text, role):
        say(self.reply_label, text, role)

    def focus(self):
        self.entry.focus_set()
