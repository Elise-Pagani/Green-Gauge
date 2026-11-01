"""Monitor page: the reading cards and the plant-status card."""
import tkinter as tk

from plant_db import get_plant, check_conditions
from theme import NUMBER_SIZE, paint
from widgets import make_button, make_label

# How the status card looks in each state: card color, then text colors
STATUS_STYLES = {
    "neutral": dict(card="CARD", headline="TEXT", plant="MUTED", detail="MUTED"),
    "ok": dict(card="OK_BG", headline="OK", plant="TEXT", detail="MUTED"),
    "warn": dict(card="WARN_BG", headline="WARN", plant="TEXT", detail="TEXT"),
}


def build_reading(card, title, color_role, unit):
    """One compact reading card: small title, big number and unit."""
    inner = tk.Frame(card)
    paint(inner, bg="CARD")
    inner.pack(expand=True)   # expand without fill = centered in the card
    make_label(inner, title, 11, "MUTED", True, bg="CARD").pack(pady=(0, 2))
    row = tk.Frame(inner)
    paint(row, bg="CARD")
    row.pack()
    value = make_label(row, "--.-", NUMBER_SIZE, color_role, True, bg="CARD")
    value.pack(side="left")
    make_label(row, unit, 14, color_role, bg="CARD").pack(
        side="left", anchor="s", padx=(6, 0), pady=(0, 8))
    return value


class MonitorPage:
    def __init__(self, root, put, on_change_plant):
        """put: the app's grid helper. on_change_plant(): the "Change plant"
        button was tapped (the app opens the Plants page)."""
        self._build_readings(root, put)
        self._build_status(root, put, on_change_plant)
        self.widgets = [self.temp_card, self.hum_card, self.status_card]
        self.zones = []

    # -- building -------------------------------------------------------
    def _build_readings(self, root, put):
        self.temp_card = tk.Frame(root, highlightthickness=1)
        paint(self.temp_card, bg="CARD", highlightbackground="BORDER")
        put(self.temp_card, row=1, column=0, sticky="nsew", padx=(35, 8),
            pady=(4, 4), ipady=6)

        self.hum_card = tk.Frame(root, highlightthickness=1)
        paint(self.hum_card, bg="CARD", highlightbackground="BORDER")
        put(self.hum_card, row=1, column=1, sticky="nsew", padx=(8, 35),
            pady=(4, 4), ipady=6)

        self.temp_value = build_reading(self.temp_card, "TEMPERATURE", "TEMP", "°C")
        self.hum_value = build_reading(self.hum_card, "HUMIDITY", "HUM", "% RH")

    def _build_status(self, root, put, on_change_plant):
        # The main answer on this page: are conditions ideal?
        self.status_card = tk.Frame(root, highlightthickness=1)
        paint(self.status_card, bg="CARD", highlightbackground="BORDER")
        put(self.status_card, row=2, column=0, columnspan=2, sticky="nsew",
            padx=35, pady=(4, 4))

        self.status_inner = tk.Frame(self.status_card)
        paint(self.status_inner, bg="CARD")
        self.status_inner.pack(expand=True)

        inner = self.status_inner
        self.state_headline = make_label(inner, "", 24, "TEXT", True, bg="CARD")
        self.state_plant = make_label(inner, "", 13, "MUTED", bg="CARD")
        self.state_detail = make_label(inner, "", 13, "MUTED", bg="CARD")
        self.state_detail.config(wraplength=680, justify="center")
        # Plant selection is one tap away, on the Plants page. The button
        # stays CARD-colored on the tinted ok / warn cards.
        self.change_plant = make_button(inner, "Change plant ›", on_change_plant)
        self.change_plant.grid(row=3, column=0, pady=(10, 0))

    # -- updating -------------------------------------------------------
    def show_reading(self, temperature, humidity):
        self.temp_value.config(text=f"{temperature:.1f}")
        self.hum_value.config(text=f"{humidity:.1f}")

    def set_status(self, kind, headline, plant_line="", detail=""):
        style = STATUS_STYLES[kind]
        paint(self.status_card, bg=style["card"])
        paint(self.status_inner, bg=style["card"])
        rows = ((self.state_headline, headline, style["headline"], (0, 0)),
                (self.state_plant, plant_line, style["plant"], (6, 0)),
                (self.state_detail, detail, style["detail"], (4, 0)))
        for index, (label, text, role, pady) in enumerate(rows):
            label.config(text=text)
            paint(label, fg=role, bg=style["card"])
            if text:
                label.grid(row=index, column=0, pady=pady)
            else:
                label.grid_remove()

    def refresh(self, plant_name, reading):
        """Re-check the user's plant (a name or None) against the latest
        reading ((temperature, humidity) or None). Returns the status:
        "neutral", "ok" or "warn"."""
        plant = get_plant(plant_name) if plant_name else None
        self.change_plant.config(
            text="Change plant ›" if plant else "Choose a plant ›")

        if plant is None:
            self.set_status("neutral", "Pick a plant", "to check if conditions are ideal")
            return "neutral"

        ideal = (f"{plant['name']}  ·  ideal {plant['min_temp']:.0f}-"
                 f"{plant['max_temp']:.0f} °C, {plant['min_hum']:.0f}-"
                 f"{plant['max_hum']:.0f}% RH")

        if reading is None:
            self.set_status("neutral", "Waiting for first reading...", ideal)
            return "neutral"

        ok, messages = check_conditions(plant, *reading)
        if ok:
            self.set_status("ok", "✔ Conditions are ideal", ideal, plant["notes"] or "")
            return "ok"
        self.set_status("warn", "⚠ Conditions need attention", ideal,
                        "\n".join(messages))
        return "warn"
