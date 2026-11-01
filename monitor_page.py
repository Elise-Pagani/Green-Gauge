"""Monitor page: the reading cards, the plant-status card and the plant picker."""
import tkinter as tk

from plant_db import list_plants, get_plant, check_conditions
from theme import NUMBER_SIZE, get_font, paint
from widgets import make_label, make_row_text
from zones import RowZone

NO_PLANT = "Select a plant..."

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
    def __init__(self, root, put, on_plant_chosen):
        """put: the app's grid helper. on_plant_chosen(): called after the
        user picks a plant in the dropdown."""
        self._build_readings(root, put)
        self._build_status(root, put)
        self._build_picker(root, put, on_plant_chosen)
        self.widgets = [self.temp_card, self.hum_card, self.status_card,
                        self.picker]
        self.zones = [self.picker]

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

    def _build_status(self, root, put):
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

    def _build_picker(self, root, put, on_plant_chosen):
        self.selected_plant = tk.StringVar(value=NO_PLANT)

        self.picker = RowZone(root, pad_top=4, pad_bottom=2)
        paint(self.picker, bg="BG")
        put(self.picker, row=3, column=0, columnspan=2, sticky="ew")

        menu_font = get_font(12)
        make_row_text(self.picker, "PLANT:", 11, "MUTED", True, padx=(0, 10))
        plant_menu = tk.OptionMenu(
            self.picker, self.selected_plant, NO_PLANT, *list_plants(),
            command=lambda _choice: on_plant_chosen()
        )
        plant_menu.config(font=menu_font, width=18, bd=0, relief="flat",
                          highlightthickness=1)
        paint(plant_menu, bg="CARD", fg="TEXT",
              activebackground="CARD", activeforeground="TEXT",
              highlightbackground="BORDER", highlightcolor="ACCENT")
        plant_menu["menu"].config(font=menu_font)
        paint(plant_menu["menu"], bg="CARD", fg="TEXT",
              activebackground="ACCENT", activeforeground="ON_ACCENT")
        self.picker.add_widget(plant_menu, extra_height=6)

    # -- the selected plant ---------------------------------------------
    def selected_name(self):
        """The selected plant's name, or None."""
        name = self.selected_plant.get()
        return None if name == NO_PLANT else name

    def select(self, name):
        self.selected_plant.set(name or NO_PLANT)

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

    def refresh(self, reading):
        """Re-check the selected plant against the latest reading
        ((temperature, humidity) or None)."""
        name = self.selected_name()
        plant = get_plant(name) if name else None

        if plant is None:
            self.set_status("neutral", "Pick a plant", "to check if conditions are ideal")
            return

        ideal = (f"{plant['name']}  ·  ideal {plant['min_temp']:.0f}-"
                 f"{plant['max_temp']:.0f} °C, {plant['min_hum']:.0f}-"
                 f"{plant['max_hum']:.0f}% RH")

        if reading is None:
            self.set_status("neutral", "Waiting for first reading...", ideal)
            return

        ok, messages = check_conditions(plant, *reading)
        if ok:
            self.set_status("ok", "✔ Conditions are ideal", ideal, plant["notes"] or "")
        else:
            self.set_status("warn", "⚠ Conditions need attention", ideal,
                            "\n".join(messages))
