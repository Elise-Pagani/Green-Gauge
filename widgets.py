"""Small helpers that create themed text, shared by the page modules."""
import tkinter as tk

from theme import color, get_font, paint


# The touch targets (tabs, arrows, buttons) are at least this tall at Medium.
# Labels here have no border (bd=0), so the padding alone sets their size.
TOUCH_PX = 44
BUTTON_PADY = 12   # padding that makes a body-text button TOUCH_PX tall

# Text used to measure a font's average character width
SAMPLE = "Basil likes 18–29 °C and 40–60% humidity; keep it out of the cold."


def text_width(characters, role="body", bold=None):
    """About how many pixels `characters` characters take in a font role,
    for wrap widths that follow the text size."""
    font = get_font(role, bold)
    return int(font.measure(SAMPLE) / len(SAMPLE) * characters)


def make_label(parent, text, role, fg, bold=None, bg="BG"):
    """A normal Label (used inside the solid cards)."""
    label = tk.Label(parent, text=text, font=get_font(role, bold), bd=0)
    paint(label, fg=fg, bg=bg)
    return label


def make_line(zone, text, role, fg, bold=None, gap=0, wraplength=0,
              align="center"):
    """A line of text drawn straight onto a zone (no box around it)."""
    line = zone.add_line(text, get_font(role, bold), color(fg), gap=gap,
                         wraplength=wraplength, align=align)
    paint(line, fg=fg)
    return line


def make_row_text(zone, text, role, fg, bold=None, padx=(0, 0)):
    part = zone.add_text(text, get_font(role, bold), color(fg), padx=padx)
    paint(part, fg=fg)
    return part


def say(label, text, fg):
    """Set a label's text and color role together."""
    label.config(text=text)
    paint(label, fg=fg)


def make_button(parent, text, command, primary=False):
    """A tappable Label (Mac Buttons ignore colors), TOUCH_PX tall.
    primary: filled with the accent color, for the main choice."""
    button = tk.Label(parent, text=text, font=get_font("body"), bd=0, padx=16,
                      pady=BUTTON_PADY, highlightthickness=1, cursor="hand2")
    if primary:
        paint(button, bg="ACCENT", fg="ON_ACCENT", highlightbackground="ACCENT")
    else:
        paint(button, bg="CARD", fg="TEXT", highlightbackground="CONTROL_BORDER")
    button.bind("<Button-1>", lambda _event: command())
    return button
