"""Plants page: one plant's full guide, browsed with the < > arrows.

Browsing only changes the plant being VIEWED here. The user's plant (the
one the Monitor page checks) changes only with the "Set as my plant" button.
"""
import tkinter as tk

from photos import load_photo
from plant_db import list_plants, get_plant
from theme import color, get_font, paint
from widgets import make_button, make_label
from zones import RowZone

PHOTO_BOX = 170
FACTS = [("temp", "TEMPERATURE"), ("hum", "HUMIDITY"), ("water", "WATERING"),
         ("soil", "SOIL"), ("ph", "SOIL pH")]


def fmt_range(low, high, unit="", digits=0):
    if low is None or high is None:
        return "–"
    return f"{low:.{digits}f}–{high:.{digits}f}{unit}"


class PlantsPage:
    def __init__(self, root, put, active_name, set_active):
        """active_name(): the user's plant's name or None.
        set_active(name): makes a plant the user's plant."""
        self.active_name = active_name
        self.set_active = set_active
        self.viewed_plant = None   # the plant shown here (None: none yet)
        self._build_card(root, put)
        self._build_browse_row(root, put)
        self.widgets = [self.plant_card, self.plants_picker]
        self.zones = [self.plants_picker]

    # -- building -------------------------------------------------------
    def _build_card(self, root, put):
        self.plant_card = tk.Frame(root, highlightthickness=1)
        paint(self.plant_card, bg="CARD", highlightbackground="BORDER")
        put(self.plant_card, show=False, row=2, column=0, columnspan=2,
            sticky="nsew", padx=35, pady=(4, 4))
        plant_inner = tk.Frame(self.plant_card)
        paint(plant_inner, bg="CARD")
        plant_inner.pack(expand=True)

        # Left column: the photo with the "Set as my plant" button under it
        # (the facts column is taller, so the button costs no height)
        photo_column = tk.Frame(plant_inner)
        paint(photo_column, bg="CARD")
        photo_column.pack(side="left", padx=(0, 22))
        self.plant_photo = tk.Canvas(photo_column, width=PHOTO_BOX, height=PHOTO_BOX,
                                     highlightthickness=0, bd=0)
        paint(self.plant_photo, bg="CARD")
        self.plant_photo.pack()
        self.set_button = make_button(photo_column, "Set as my plant", self._on_set,
                                      primary=True)
        self.set_button.pack(pady=(10, 0))

        info = tk.Frame(plant_inner)
        paint(info, bg="CARD")
        info.pack(side="left")
        self.plant_title = make_label(info, "", 20, "ACCENT", True, bg="CARD")
        self.plant_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.fact_values = {}
        for row_number, (key, heading) in enumerate(FACTS, start=1):
            make_label(info, heading, 9, "MUTED", True, bg="CARD").grid(
                row=row_number, column=0, sticky="w", padx=(0, 14), pady=2)
            self.fact_values[key] = make_label(info, "", 12, "TEXT", True, bg="CARD")
            self.fact_values[key].grid(row=row_number, column=1, sticky="w", pady=2)
        self.plant_notes = make_label(info, "", 11, "MUTED", bg="CARD")
        self.plant_notes.config(wraplength=380, justify="left")
        self.plant_notes.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _build_browse_row(self, root, put):
        self.plants_picker = RowZone(root, pad_top=4, pad_bottom=2)
        paint(self.plants_picker, bg="BG")
        put(self.plants_picker, show=False, row=3, column=0, columnspan=2,
            sticky="ew")

        self.plants_picker.add_widget(self._make_arrow("<", -1), padx=(0, 10))
        self.picker_name = tk.Label(self.plants_picker, text="Browse plants",
                                    width=14, font=get_font(14, True), pady=8,
                                    highlightthickness=1)
        paint(self.picker_name, bg="CARD", fg="TEXT", highlightbackground="BORDER")
        self.plants_picker.add_widget(self.picker_name)
        self.plants_picker.add_widget(self._make_arrow(">", 1), padx=(10, 0))

    def _make_arrow(self, text, step):
        """A big tappable arrow (a Label, since Mac Buttons ignore colors)."""
        arrow = tk.Label(self.plants_picker, text=text, font=get_font(18, True),
                         padx=22, pady=0, highlightthickness=1, cursor="hand2")
        paint(arrow, bg="CARD", fg="TEXT", highlightbackground="BORDER")
        arrow.bind("<Button-1>", lambda _event: self.step(step))
        return arrow

    # -- updating -------------------------------------------------------
    def draw_photo(self, name):
        """The plant's photo, or a drawn placeholder leaf if it has none yet."""
        canvas, s = self.plant_photo, PHOTO_BOX
        canvas.delete("all")
        image = load_photo(name, s) if name else None
        if image:
            canvas.image = image   # keep a reference so Tk doesn't discard it
            canvas.create_image(s / 2, s / 2, image=image)
            return
        canvas.create_rectangle(0, 0, s - 1, s - 1, fill=color("OK_BG"),
                                outline=color("BORDER"))
        canvas.create_polygon(s * .5, s * .78, s * .25, s * .5, s * .33, s * .2,
                              s * .62, s * .18, s * .75, s * .5, smooth=True,
                              fill=color("OK"), outline="")
        canvas.create_line(s * .5, s * .78, s * .52, s * .3,
                           fill=color("OK_BG"), width=2)
        canvas.create_text(s / 2, s * .9, text="No photo yet",
                           font=get_font(9), fill=color("MUTED"))

    def show(self):
        """The page is being opened: start on the user's plant, or the
        first plant if there isn't one."""
        names = list_plants()
        active = self.active_name()
        self.viewed_plant = active if active else (names[0] if names else None)
        self.refresh()

    def _on_set(self):
        if self.viewed_plant and self.viewed_plant != self.active_name():
            self.set_active(self.viewed_plant)   # the app then calls refresh()

    def _refresh_set_button(self):
        if self.viewed_plant == self.active_name():
            self.set_button.config(text="✔ Your plant", cursor="")
            paint(self.set_button, bg="CARD", fg="MUTED", highlightbackground="CARD")
        else:
            self.set_button.config(text="Set as my plant", cursor="hand2")
            paint(self.set_button, bg="ACCENT", fg="ON_ACCENT",
                  highlightbackground="ACCENT")

    def refresh(self):
        name = self.viewed_plant
        plant = get_plant(name) if name else None
        if plant is None:
            self.set_button.pack_forget()
            self.plant_title.config(text="No plant selected")
            for label in self.fact_values.values():
                label.config(text="–")
            self.plant_notes.config(text="Use the arrows below to browse the plants.")
            self.picker_name.config(text="Browse plants")
            self.draw_photo(None)
            return
        facts = self.fact_values
        facts["temp"].config(text=fmt_range(plant["min_temp"], plant["max_temp"], " °C"))
        facts["hum"].config(text=fmt_range(plant["min_hum"], plant["max_hum"], " % RH"))
        facts["water"].config(text=plant["water"] or "–")
        facts["soil"].config(text=plant["soil"] or "–")
        facts["ph"].config(text=fmt_range(plant["ph_min"], plant["ph_max"], "", 1))
        self.set_button.pack(pady=(10, 0))
        self._refresh_set_button()
        self.plant_title.config(text=plant["name"])
        self.plant_notes.config(text=plant["notes"] or "")
        self.picker_name.config(text=plant["name"])
        self.draw_photo(plant["name"])

    def step(self, step):
        """Previous / next plant (wraps around). Only changes the viewed plant."""
        names = list_plants()
        if not names:
            return
        if self.viewed_plant in names:
            index = (names.index(self.viewed_plant) + step) % len(names)
        else:
            index = 0 if step > 0 else len(names) - 1
        self.viewed_plant = names[index]
        self.refresh()
