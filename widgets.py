"""Small helpers that create themed text, shared by the page modules."""
import tkinter as tk

from theme import color, get_font, paint


def make_label(parent, text, size, fg, bold=False, bg="BG"):
    """A normal Label (used inside the solid cards)."""
    label = tk.Label(parent, text=text, font=get_font(size, bold))
    paint(label, fg=fg, bg=bg)
    return label


def make_line(zone, text, size, fg, bold=False, gap=0, wraplength=0,
              align="center"):
    """A line of text drawn straight onto a zone (no box around it)."""
    line = zone.add_line(text, get_font(size, bold), color(fg), gap=gap,
                         wraplength=wraplength, align=align)
    paint(line, fg=fg)
    return line


def make_row_text(zone, text, size, fg, bold=False, padx=(0, 0)):
    part = zone.add_text(text, get_font(size, bold), color(fg), padx=padx)
    paint(part, fg=fg)
    return part


def say(label, text, fg):
    """Set a label's text and color role together."""
    label.config(text=text)
    paint(label, fg=fg)


def make_button(parent, text, command, size=11, primary=False):
    """A tappable Label (Mac Buttons ignore colors). primary: filled with
    the accent color, for the main choice."""
    button = tk.Label(parent, text=text, font=get_font(size, True), padx=14,
                      pady=5, highlightthickness=1, cursor="hand2")
    if primary:
        paint(button, bg="ACCENT", fg="ON_ACCENT", highlightbackground="ACCENT")
    else:
        paint(button, bg="CARD", fg="TEXT", highlightbackground="BORDER")
    button.bind("<Button-1>", lambda _event: command())
    return button
