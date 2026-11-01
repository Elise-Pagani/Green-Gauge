"""Small helpers that create themed text, shared by the page modules."""
import tkinter as tk

from theme import color, get_font, paint


def make_label(parent, text, size, fg, bold=False, bg="BG"):
    """A normal Label (used inside the solid cards)."""
    label = tk.Label(parent, text=text, font=get_font(size, bold))
    paint(label, fg=fg, bg=bg)
    return label


def make_line(zone, text, size, fg, bold=False, gap=0, wraplength=0):
    """A line of text drawn straight onto a zone (no box around it)."""
    line = zone.add_line(text, get_font(size, bold), color(fg), gap=gap,
                         wraplength=wraplength)
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
