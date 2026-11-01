"""Colors, text sizes and fonts shared by every page.

Every widget registers which color ROLE each option uses (e.g. fg="MUTED")
through paint(). Switching theme then just re-applies the roles with the new
palette (repaint_all). Fonts are shared objects, so resizing one resizes every
widget using it (apply_scale).

No Tk objects are created when this module is imported, so it can be used
(and tested) without a display.
"""
import tkinter as tk
from tkinter import font

# Every theme draws its text on a backdrop: a soft gradient (Light, Dark) or
# a blurred photo (Nature). Text colors were checked for WCAG AA contrast
# (4.5:1 or better) against the WORST point of the backdrop: along the whole
# gradient, or, for the photo, after lightening it just enough (see
# background.py). Cards stay solid so the numbers are always crisp.
# GRAD_TOP / GRAD_BOTTOM are the two ends of the gradient.
# OK_BG / WARN_BG tint the plant-status card (always paired with an icon and
# words, so color is never the only signal).
THEMES = {
    "light": dict(
        BG="#F1F8EF", CARD="#FFFFFF", BORDER="#C5D9C8",
        GRAD_TOP="#F8FCF6", GRAD_BOTTOM="#E9F4E7",
        TEXT="#1E3A2B", MUTED="#4F6B58",
        TEMP="#B8500A", HUM="#0B6E99",
        OK="#1B7541", WARN="#B3261E", WAIT="#8F5700",
        OK_BG="#E7F5EB", WARN_BG="#FCEBE9",
        ACCENT="#2A7549", ON_ACCENT="#FFFFFF",
    ),
    "dark": dict(
        BG="#12211A", CARD="#1B3026", BORDER="#2E4A3A",
        GRAD_TOP="#0D1913", GRAD_BOTTOM="#183024",
        TEXT="#E6F2E8", MUTED="#A9C2B0",
        TEMP="#F6A35B", HUM="#67C7E8",
        OK="#5FD08A", WARN="#FF8A80", WAIT="#F2B84B",
        OK_BG="#17402C", WARN_BG="#431F1F",
        ACCENT="#4CAF73", ON_ACCENT="#0E1A13",
    ),
    "nature": dict(
        BG="#F4FAF2", CARD="#FFFFFF", BORDER="#9DBFA6",
        TEXT="#0F2418", MUTED="#2D4636",
        TEMP="#B8500A", HUM="#0B6E99",
        OK="#0F5530", WARN="#8A1710", WAIT="#6B4000",
        OK_BG="#E8F5EC", WARN_BG="#FBE9E6",
        ACCENT="#14532F", ON_ACCENT="#FFFFFF",
    ),
}
# Colors of text that sits directly on the photo in the Nature theme
NATURE_TEXT_COLORS = [THEMES["nature"][role] for role in
                      ("TEXT", "MUTED", "ACCENT", "OK", "WARN", "WAIT")]
SIZES = {"Small": 0.85, "Medium": 1.0, "Large": 1.2}

NUMBER_SIZE = 36   # the big temperature / humidity numbers

# Current settings (changed from the Settings menu)
_theme = "light"
_size = "Medium"


def current_theme():
    return _theme


def current_size():
    return _size


def set_theme(name):
    """Switch palette. Call repaint_all() afterwards to recolor widgets."""
    global _theme
    if name not in THEMES:
        raise ValueError(f"unknown theme: {name}")
    _theme = name


def set_size(name):
    """Switch text size. Call apply_scale() afterwards to resize fonts."""
    global _size
    if name not in SIZES:
        raise ValueError(f"unknown text size: {name}")
    _size = name


def color(role):
    return THEMES[_theme][role]


ROLES = {}


def paint(widget, **roles):
    ROLES.setdefault(widget, {}).update(roles)
    widget.config(**{opt: color(role) for opt, role in roles.items()})


def repaint_all():
    for widget, roles in ROLES.items():
        widget.config(**{opt: color(role) for opt, role in roles.items()})


FONTS = {}


def px(size, scale=1.0):
    """Font size in PIXELS (negative = pixels in Tk).

    The window is a fixed 800x480 pixels, so fonts are sized in pixels too.
    Point sizes would change with each screen's DPI setting and make the
    layout fit on one computer but overflow on another. `size` is the
    familiar point size at 96 DPI; 4/3 converts it to pixels."""
    return -max(9, round(size * 4 / 3 * scale))


def get_font(size, bold=False):
    key = (size, bold)
    if key not in FONTS:
        FONTS[key] = font.Font(
            family="DejaVu Sans", size=px(size, _scale(size)),
            weight="bold" if bold else "normal"
        )
    return FONTS[key]


def _scale(size):
    scale = SIZES[_size]
    # The big reading numbers never grow past their normal size, which
    # keeps the reading cards compact at every text size.
    return min(scale, 1.0) if size == NUMBER_SIZE else scale


def apply_scale():
    for (size, _bold), f in FONTS.items():
        f.configure(size=px(size, _scale(size)))


def make_gradient(width, height, top, bottom):
    """A top-to-bottom gradient, built with plain Tk (no Pillow needed)."""
    image = tk.PhotoImage(width=width, height=height)
    top_rgb = [int(top[i:i + 2], 16) for i in (1, 3, 5)]
    bottom_rgb = [int(bottom[i:i + 2], 16) for i in (1, 3, 5)]
    for y in range(height):
        t = y / max(1, height - 1)
        r, g, b = (round(a + (c - a) * t) for a, c in zip(top_rgb, bottom_rgb))
        image.put(f"#{r:02x}{g:02x}{b:02x}", to=(0, y, width, y + 1))
    return image


def mix(a, b, t):
    """Blend hex color a toward hex color b (t from 0 to 1)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))
