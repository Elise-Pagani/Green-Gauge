"""WCAG contrast of every theme: text 4.5:1, control outlines 3:1.

Text that sits on the backdrop is checked against both gradient ends
(Light, Dark) or, for Nature, against the darkest the washed photo can be
(background.required_luminance). No display needed.
"""
import unittest

from background import hex_to_rgb, luminance, required_luminance
from theme import NATURE_TEXT_COLORS, THEMES

TEXT_CONTRAST = 4.5
CONTROL_CONTRAST = 3.0

# (background role, text roles drawn on it)
TEXT_PAIRS = [
    ("CARD", ("TEXT", "MUTED", "TEMP", "HUM", "ACCENT")),
    ("OK_BG", ("OK", "TEXT", "MUTED")),
    ("WARN_BG", ("WARN", "TEXT")),
    ("ACCENT", ("ON_ACCENT",)),
]
BACKDROP_TEXT = ("TEXT", "MUTED", "ACCENT", "OK", "WAIT")


def lum(color):
    return luminance(hex_to_rgb(color))


def ratio(lum_a, lum_b):
    light, dark = max(lum_a, lum_b), min(lum_a, lum_b)
    return (light + 0.05) / (dark + 0.05)


def backdrops(palette):
    """Luminance of the worst points of the backdrop, by name."""
    if "GRAD_TOP" in palette:
        return {end: lum(palette[end]) for end in ("GRAD_TOP", "GRAD_BOTTOM")}
    return {"washed photo": required_luminance(NATURE_TEXT_COLORS)}


class ThemeContrastTests(unittest.TestCase):
    def assertContrast(self, fg, bg_lum, minimum, label):
        value = ratio(lum(fg), bg_lum)
        self.assertGreaterEqual(value, minimum, f"{label}: {value:.2f}:1")

    def test_text_on_solid_backgrounds(self):
        for name, palette in THEMES.items():
            for bg, texts in TEXT_PAIRS:
                for text in texts:
                    with self.subTest(theme=name, pair=f"{text} on {bg}"):
                        self.assertContrast(palette[text], lum(palette[bg]),
                                            TEXT_CONTRAST, f"{name} {text} on {bg}")

    def test_text_on_the_backdrop(self):
        for name, palette in THEMES.items():
            for where, bg_lum in backdrops(palette).items():
                for text in BACKDROP_TEXT:
                    with self.subTest(theme=name, pair=f"{text} on {where}"):
                        self.assertContrast(palette[text], bg_lum,
                                            TEXT_CONTRAST, f"{name} {text} on {where}")

    def test_control_border_stands_out(self):
        for name, palette in THEMES.items():
            surroundings = {bg: lum(palette[bg]) for bg in ("CARD", "BG")}
            surroundings.update(backdrops(palette))
            for where, bg_lum in surroundings.items():
                with self.subTest(theme=name, against=where):
                    self.assertContrast(palette["CONTROL_BORDER"], bg_lum,
                                        CONTROL_CONTRAST, f"{name} border on {where}")

    def test_every_theme_has_every_role(self):
        roles = set(THEMES["light"])
        for name, palette in THEMES.items():
            # Nature's backdrop is a photo, so it has no gradient ends
            expected = roles - {"GRAD_TOP", "GRAD_BOTTOM"} if name == "nature" else roles
            self.assertEqual(set(palette), expected, name)


if __name__ == "__main__":
    unittest.main()
