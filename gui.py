import queue
import threading
import tkinter as tk
from tkinter import font
from datetime import datetime

import background
from sensor import get_sensor, ON_PI
from plant_db import init_db, list_plants, get_plant, check_conditions
from commands import handle_command
from llm import ask
from zones import TextZone, RowZone
from photos import load_photo

# Real DHT22 on the Pi, simulated sensor on a PC/Mac
sensor = get_sensor()

# Make sure the plant database exists and is filled
init_db()

# ---------------------------------------------------------------- theme
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

# Current settings (changed from the Settings menu or the tabs)
current = {"theme": "light", "size": "Medium", "page": "monitor"}

NO_PLANT = "Select a plant..."
NUMBER_SIZE = 36   # the big temperature / humidity numbers

root = tk.Tk()
root.title("Climate Monitor")
root.geometry("800x480")   # the size the professor's original code used
if ON_PI:
    root.attributes("-fullscreen", True)
else:
    root.resizable(False, False)   # on a PC/Mac, keep it at the Pi's size


def color(role):
    return THEMES[current["theme"]][role]


# Every widget registers which color ROLE each option uses (e.g. fg="MUTED").
# Switching theme then just re-applies the roles with the new palette.
ROLES = {}


def paint(widget, **roles):
    ROLES.setdefault(widget, {}).update(roles)
    widget.config(**{opt: color(role) for opt, role in roles.items()})


def repaint_all():
    for widget, roles in ROLES.items():
        widget.config(**{opt: color(role) for opt, role in roles.items()})


# Fonts are shared objects, so resizing one resizes every widget using it.
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
            family="DejaVu Sans", size=px(size),
            weight="bold" if bold else "normal"
        )
    return FONTS[key]


def apply_scale():
    scale = SIZES[current["size"]]
    for (size, _bold), f in FONTS.items():
        # The big reading numbers never grow past their normal size, which
        # keeps the reading cards compact at every text size.
        s = min(scale, 1.0) if size == NUMBER_SIZE else scale
        f.configure(size=px(size, s))


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


paint(root, bg="BG")

# --------------------------------------------------------------- layout
# One grid, two columns. Rows (the same grid is shared by both pages):
#   0  header zone: title + date/time                       (both pages)
#   1  reading cards                                        (Monitor page)
#   2  plant-status card | assistant text                   (grows to fill)
#   3  plant picker      | typed question box
#   4  page tabs                                            (both pages)
#   5  sensor status line                                   (both pages)
# The zones are canvases (see zones.py): their text is drawn directly on the
# backdrop, so there are no boxes around it. Cards are solid on purpose.
root.columnconfigure((0, 1), weight=1, uniform="cols")
root.rowconfigure(2, weight=1)

# Tk quirk: when EVERY widget on a page spans both columns (as on the Assistant
# page), the grid stops re-arranging when a widget's size changes, so text-size
# changes and long answers don't take effect and a re-shown page can stay blank.
# One zero-size, invisible widget in each single column, present on every page,
# keeps the grid working. (Created first, so they sit under the cards.)
COLUMN_ANCHORS = []
for column in (0, 1):
    anchor = tk.Frame(root, width=0, height=0, highlightthickness=0, bd=0)
    anchor.grid(row=1, column=column)
    COLUMN_ANCHORS.append(anchor)

# Where each page widget goes on the grid. We remember the options ourselves
# so a hidden widget can be put back with exactly the same placement.
GRID = {}


def put(widget, show=True, **options):
    """Record where a widget goes, and (unless show=False) place it now.
    Widgets for a page that isn't showing at startup use show=False: Tk gets
    confused by widgets that are placed and then hidden before they were ever
    drawn (they wouldn't resize properly later), so they're only placed the
    first time their page is shown."""
    GRID[widget] = options
    if show:
        widget.grid(**options)

header = TextZone(root, pad_top=10, pad_bottom=2)
paint(header, bg="BG")
header.grid(row=0, column=0, columnspan=2, sticky="ew")
make_line(header, "CLIMATE MONITOR", 24, "ACCENT", True)
date_line = make_line(header, "", 11, "MUTED")

# ---- Monitor page: compact reading cards
temp_card = tk.Frame(root, highlightthickness=1)
paint(temp_card, bg="CARD", highlightbackground="BORDER")
put(temp_card, row=1, column=0, sticky="nsew", padx=(35, 8), pady=(4, 4), ipady=6)

hum_card = tk.Frame(root, highlightthickness=1)
paint(hum_card, bg="CARD", highlightbackground="BORDER")
put(hum_card, row=1, column=1, sticky="nsew", padx=(8, 35), pady=(4, 4), ipady=6)


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


temp_value = build_reading(temp_card, "TEMPERATURE", "TEMP", "°C")
hum_value = build_reading(hum_card, "HUMIDITY", "HUM", "% RH")

# ---- Monitor page: plant-status card (the main answer: are conditions ideal?)
status_card = tk.Frame(root, highlightthickness=1)
paint(status_card, bg="CARD", highlightbackground="BORDER")
put(status_card, row=2, column=0, columnspan=2, sticky="nsew",
    padx=35, pady=(4, 4))

status_inner = tk.Frame(status_card)
paint(status_inner, bg="CARD")
status_inner.pack(expand=True)

state_headline = make_label(status_inner, "", 24, "TEXT", True, bg="CARD")
state_plant = make_label(status_inner, "", 13, "MUTED", bg="CARD")
state_detail = make_label(status_inner, "", 13, "MUTED", bg="CARD")
state_detail.config(wraplength=680, justify="center")

# How the card looks in each state: card color, then text colors
STATUS_STYLES = {
    "neutral": dict(card="CARD", headline="TEXT", plant="MUTED", detail="MUTED"),
    "ok": dict(card="OK_BG", headline="OK", plant="TEXT", detail="MUTED"),
    "warn": dict(card="WARN_BG", headline="WARN", plant="TEXT", detail="TEXT"),
}


def set_status(kind, headline, plant_line="", detail=""):
    style = STATUS_STYLES[kind]
    paint(status_card, bg=style["card"])
    paint(status_inner, bg=style["card"])
    rows = ((state_headline, headline, style["headline"], (0, 0)),
            (state_plant, plant_line, style["plant"], (6, 0)),
            (state_detail, detail, style["detail"], (4, 0)))
    for index, (label, text, role, pady) in enumerate(rows):
        label.config(text=text)
        paint(label, fg=role, bg=style["card"])
        if text:
            label.grid(row=index, column=0, pady=pady)
        else:
            label.grid_remove()


# ---- Monitor page: plant picker
selected_plant = tk.StringVar(value=NO_PLANT)

picker = RowZone(root, pad_top=4, pad_bottom=2)
paint(picker, bg="BG")
put(picker, row=3, column=0, columnspan=2, sticky="ew")

menu_font = get_font(12)
make_row_text(picker, "PLANT:", 11, "MUTED", True, padx=(0, 10))
plant_menu = tk.OptionMenu(
    picker, selected_plant, NO_PLANT, *list_plants(),
    command=lambda _choice: refresh_plant_status()
)
plant_menu.config(font=menu_font, width=18, bd=0, relief="flat",
                  highlightthickness=1)
paint(plant_menu, bg="CARD", fg="TEXT",
      activebackground="CARD", activeforeground="TEXT",
      highlightbackground="BORDER", highlightcolor="ACCENT")
plant_menu["menu"].config(font=menu_font)
paint(plant_menu["menu"], bg="CARD", fg="TEXT",
      activebackground="ACCENT", activeforeground="ON_ACCENT")
picker.add_widget(plant_menu, extra_height=6)

# ---- Assistant page (a simple placeholder for now; we'll design it properly
# once the plant database is expanded)
assistant_zone = TextZone(root, pad_top=14, pad_bottom=4)
paint(assistant_zone, bg="BG")
put(assistant_zone, show=False, row=2, column=0, columnspan=2, sticky="nsew")
make_line(assistant_zone, "ASSISTANT", 14, "ACCENT", True)
make_line(assistant_zone,
          "Tap the mic or type, e.g. \"I'm planting basil\"", 10, "MUTED", gap=2, wraplength=700)
reply_label = make_line(assistant_zone, "", 12, "TEXT", gap=14, wraplength=700)

ask_row = RowZone(root, pad_top=4, pad_bottom=2)
paint(ask_row, bg="BG")
put(ask_row, show=False, row=3, column=0, columnspan=2, sticky="ew")
make_row_text(ask_row, "ASK:", 11, "MUTED", True, padx=(0, 10))
command_entry = tk.Entry(ask_row, font=menu_font, width=34, relief="flat",
                         highlightthickness=1)
paint(command_entry, bg="CARD", fg="TEXT", insertbackground="TEXT",
      highlightbackground="BORDER", highlightcolor="ACCENT")
ask_row.add_widget(command_entry, extra_height=10)

# Mock voice button (drawn with plain canvas shapes, no emoji). There is no
# microphone on the Pi, so this only SIMULATES voice input; see "mock voice".
MIC_SIZE = 60
mic = tk.Canvas(ask_row, width=MIC_SIZE, height=MIC_SIZE, highlightthickness=0,
                bd=0, cursor="hand2")
paint(mic, bg="CARD")
ask_row.add_widget(mic, padx=(10, 0))

# ---- Plants page: one plant's full guide, browsed with the arrows
PHOTO_BOX = 170
plant_card = tk.Frame(root, highlightthickness=1)
paint(plant_card, bg="CARD", highlightbackground="BORDER")
put(plant_card, show=False, row=2, column=0, columnspan=2, sticky="nsew",
    padx=35, pady=(4, 4))
plant_inner = tk.Frame(plant_card)
paint(plant_inner, bg="CARD")
plant_inner.pack(expand=True)

plant_photo = tk.Canvas(plant_inner, width=PHOTO_BOX, height=PHOTO_BOX,
                        highlightthickness=0, bd=0)
paint(plant_photo, bg="CARD")
plant_photo.pack(side="left", padx=(0, 22))

plant_info = tk.Frame(plant_inner)
paint(plant_info, bg="CARD")
plant_info.pack(side="left")
plant_title = make_label(plant_info, "", 20, "ACCENT", True, bg="CARD")
plant_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
FACTS = [("temp", "TEMPERATURE"), ("hum", "HUMIDITY"), ("water", "WATERING"),
         ("soil", "SOIL"), ("ph", "SOIL pH")]
fact_values = {}
for row_number, (key, heading) in enumerate(FACTS, start=1):
    make_label(plant_info, heading, 9, "MUTED", True, bg="CARD").grid(
        row=row_number, column=0, sticky="w", padx=(0, 14), pady=2)
    fact_values[key] = make_label(plant_info, "", 12, "TEXT", True, bg="CARD")
    fact_values[key].grid(row=row_number, column=1, sticky="w", pady=2)
plant_notes = make_label(plant_info, "", 11, "MUTED", bg="CARD")
plant_notes.config(wraplength=380, justify="left")
plant_notes.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

plants_picker = RowZone(root, pad_top=4, pad_bottom=2)
paint(plants_picker, bg="BG")
put(plants_picker, show=False, row=3, column=0, columnspan=2, sticky="ew")


def make_arrow(text, step):
    """A big tappable arrow (a Label, since Mac Buttons ignore colors)."""
    arrow = tk.Label(plants_picker, text=text, font=get_font(18, True),
                     padx=22, pady=0, highlightthickness=1, cursor="hand2")
    paint(arrow, bg="CARD", fg="TEXT", highlightbackground="BORDER")
    arrow.bind("<Button-1>", lambda _event: step_plant(step))
    return arrow


plants_picker.add_widget(make_arrow("<", -1), padx=(0, 10))
picker_name = tk.Label(plants_picker, text="Browse plants", width=14,
                       font=get_font(14, True), pady=8, highlightthickness=1)
paint(picker_name, bg="CARD", fg="TEXT", highlightbackground="BORDER")
plants_picker.add_widget(picker_name)
plants_picker.add_widget(make_arrow(">", 1), padx=(10, 0))


def fmt_range(low, high, unit="", digits=0):
    if low is None or high is None:
        return "–"
    return f"{low:.{digits}f}–{high:.{digits}f}{unit}"


def draw_plant_photo(name):
    """The plant's photo, or a drawn placeholder leaf if it has none yet."""
    canvas, s = plant_photo, PHOTO_BOX
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


def refresh_plant_page():
    name = selected_plant.get()
    plant = get_plant(name) if name != NO_PLANT else None
    if plant is None:
        plant_title.config(text="No plant selected")
        for label in fact_values.values():
            label.config(text="–")
        plant_notes.config(text="Use the arrows below to browse the plants.")
        picker_name.config(text="Browse plants")
        draw_plant_photo(None)
        return
    plant_title.config(text=plant["name"])
    fact_values["temp"].config(text=fmt_range(plant["min_temp"], plant["max_temp"], " °C"))
    fact_values["hum"].config(text=fmt_range(plant["min_hum"], plant["max_hum"], " % RH"))
    fact_values["water"].config(text=plant["water"] or "–")
    fact_values["soil"].config(text=plant["soil"] or "–")
    fact_values["ph"].config(text=fmt_range(plant["ph_min"], plant["ph_max"], "", 1))
    plant_notes.config(text=plant["notes"] or "")
    picker_name.config(text=plant["name"])
    draw_plant_photo(plant["name"])


def step_plant(step):
    """Previous / next plant (wraps around); shared with the Monitor page."""
    names = list_plants()
    current_name = selected_plant.get()
    if current_name in names:
        index = (names.index(current_name) + step) % len(names)
    else:
        index = 0 if step > 0 else len(names) - 1
    selected_plant.set(names[index])
    refresh_plant_status()
    refresh_plant_page()


# ---- Page tabs (always visible, easy to tap)
nav = RowZone(root, pad_top=2, pad_bottom=2)
paint(nav, bg="BG")
nav.grid(row=4, column=0, columnspan=2, sticky="ew")

PAGE_TITLES = {"monitor": "Monitor", "plants": "Plants",
               "assistant": "Assistant"}
tabs = {}
for page_name, page_title in PAGE_TITLES.items():
    tab = tk.Label(nav, text=page_title, font=get_font(12, True),
                   padx=26, pady=7, highlightthickness=1, cursor="hand2")
    tab.bind("<Button-1>", lambda _event, name=page_name: show_page(name))
    tabs[page_name] = tab
    nav.add_widget(tab, padx=(6, 6))

# ---- Sensor status line
footer = TextZone(root, pad_top=2, pad_bottom=6)
paint(footer, bg="BG")
footer.grid(row=5, column=0, columnspan=2, sticky="ew")
status = make_line(footer, "Connecting to sensor...", 10, "OK")

ZONES = [header, picker, assistant_zone, ask_row, plants_picker, nav, footer]

# ------------------------------------------------------------- pages
PAGES = {
    "monitor": [temp_card, hum_card, status_card, picker],
    "plants": [plant_card, plants_picker],
    "assistant": [assistant_zone, ask_row],
}


def nudge_zones():
    root.update_idletasks()
    for zone in ZONES:
        zone.refresh()


def show_page(name):
    """Show one page's widgets and hide the other's."""
    for page, widgets in PAGES.items():
        for widget in widgets:
            if page == name:
                widget.grid(**GRID[widget])
            else:
                widget.grid_forget()   # re-gridded later using GRID[widget]
    current["page"] = name
    if name == "plants":
        refresh_plant_page()
    for tab_name, tab in tabs.items():
        if tab_name == name:
            paint(tab, bg="ACCENT", fg="ON_ACCENT", highlightbackground="ACCENT")
        else:
            paint(tab, bg="CARD", fg="TEXT", highlightbackground="BORDER")
    root.update_idletasks()
    for zone in ZONES:
        zone.refresh()   # re-line-up the backdrop under each zone
    # On the Mac the boxes in the bottom row can show up late. Lining
    # everything up again a moment later gives it a nudge to draw them.
    for delay_ms in (20, 150):
        root.after(delay_ms, nudge_zones)
    if name == "assistant":
        command_entry.focus_set()


# ------------------------------------------------------------- backdrop
# The picture behind everything: a gradient for Light and Dark, a blurred
# photo for Nature. One big label shows it behind the cards, and the text
# zones (see zones.py) show the same picture lined up with their position,
# so text looks printed right on it.
backdrops = {}              # theme name -> PhotoImage, built the first time
backdrop_label = {"widget": None}


def screen_size():
    if ON_PI:
        return root.winfo_screenwidth(), root.winfo_screenheight()
    return 800, 480


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


def build_backdrop(theme):
    width, height = screen_size()
    if theme == "nature":
        data = background.build_background(
            width, height, text_colors=NATURE_TEXT_COLORS)
        return tk.PhotoImage(data=data)
    return make_gradient(width, height,
                         THEMES[theme]["GRAD_TOP"], THEMES[theme]["GRAD_BOTTOM"])


def show_backdrop(theme):
    """Put the theme's backdrop behind everything."""
    if theme not in backdrops:
        backdrops[theme] = build_backdrop(theme)   # built first: if it fails,
    photo = backdrops[theme]                       # nothing is half-changed
    if backdrop_label["widget"] is None:
        backdrop_label["widget"] = tk.Label(root, bd=0)
    label = backdrop_label["widget"]
    label.config(image=photo)
    label.place(x=0, y=0, relwidth=1, relheight=1)
    label.lower()   # behind every other widget...
    for anchor in COLUMN_ANCHORS:
        anchor.lower()   # ...except the invisible column anchors: under it, hidden
    for zone in ZONES:
        zone.set_photo(photo)


show_backdrop(current["theme"])

# ------------------------------------------------------- settings menu
theme_var = tk.StringVar(value=current["theme"])
size_var = tk.StringVar(value=current["size"])


def on_theme_change():
    name = theme_var.get()
    try:
        show_backdrop(name)
    except Exception as error:   # e.g. Pillow missing or a bad image file
        theme_var.set(current["theme"])
        say(reply_label, f"Couldn't load the {name.title()} background ({error}).", "WARN")
        return
    current["theme"] = name
    repaint_all()
    draw_mic()
    refresh_plant_page()


def on_size_change():
    current["size"] = size_var.get()
    apply_scale()
    root.update_idletasks()
    for zone in ZONES:
        zone.relayout()
    root.update_idletasks()


settings_btn = tk.Menubutton(root, text="Settings ▾", font=get_font(10, True),
                             relief="flat", bd=0, padx=12, pady=6,
                             highlightthickness=1)
paint(settings_btn, bg="CARD", fg="TEXT",
      activebackground="ACCENT", activeforeground="ON_ACCENT",
      highlightbackground="BORDER")

settings_menu = tk.Menu(settings_btn, tearoff=0, font=get_font(11))
paint(settings_menu, bg="CARD", fg="TEXT",
      activebackground="ACCENT", activeforeground="ON_ACCENT",
      disabledforeground="MUTED", selectcolor="ACCENT")
settings_btn["menu"] = settings_menu

settings_menu.add_command(label="THEME", state="disabled")
settings_menu.add_radiobutton(label="Light", variable=theme_var,
                              value="light", command=on_theme_change)
settings_menu.add_radiobutton(label="Dark", variable=theme_var,
                              value="dark", command=on_theme_change)
if background.pillow_available():
    settings_menu.add_radiobutton(label="Nature", variable=theme_var,
                                  value="nature", command=on_theme_change)
else:
    settings_menu.add_radiobutton(label="Nature (needs Pillow)",
                                  variable=theme_var, value="nature",
                                  state="disabled")
settings_menu.add_separator()
settings_menu.add_command(label="TEXT SIZE", state="disabled")
for size_name in SIZES:
    settings_menu.add_radiobutton(label=size_name, variable=size_var,
                                  value=size_name, command=on_size_change)

settings_btn.place(relx=1.0, x=-15, y=12, anchor="ne")

# ------------------------------------------------------ asking the LLM
# The LLM can take several seconds, so it runs in a background thread and
# hands its answer back through this queue (keeps the window responsive).
answers = queue.Queue()
llm_busy = {"value": False}

# Most recent good sensor reading: (temperature, humidity) or None
state = {"reading": None}


def ask_llm_in_background(text):
    plant = selected_plant.get()
    plant = None if plant == NO_PLANT else plant
    reading = state["reading"]

    def worker():
        answers.put(ask(text, plant, reading))

    llm_busy["value"] = True
    say(reply_label, "Thinking...", "MUTED")
    threading.Thread(target=worker, daemon=True).start()


def check_for_answer():
    try:
        answer = answers.get_nowait()
        say(reply_label, answer, "TEXT")
        llm_busy["value"] = False
    except queue.Empty:
        pass
    root.after(200, check_for_answer)


def process_text(text):
    """Typed text and (mock) voice both end up here."""
    plant_name, reply, ask_llm = handle_command(text)
    if plant_name is not None:
        selected_plant.set(plant_name)
        refresh_plant_status()
    if ask_llm:
        ask_llm_in_background(text)
    else:
        say(reply_label, reply, "MUTED")


def submit_command(event=None):
    if llm_busy["value"]:
        return  # still answering the last question

    process_text(command_entry.get())
    command_entry.delete(0, "end")


command_entry.bind("<Return>", submit_command)

# ------------------------------------------------------------ mock voice
# There is no microphone, so this is a Wizard-of-Oz style simulation: tapping
# the mic plays a "listening" animation, "hears" the next sample phrase below,
# then runs it exactly like typed text (real LLM answer). Edit the phrases to
# whatever you want to demo. Tap again while it is active to cancel.
MOCK_PHRASES = [
    "What humidity does basil like?",
    "I'm planting tomatoes",
    "Is it too hot for lettuce?",
]
FRAME_MS = 50
LISTEN_FRAMES = 44   # about 2.2 seconds
HEARD_FRAMES = 16    # about 0.8 seconds
mic_state = {"mode": "idle", "frame": 0, "next": 0, "phrase": ""}


def mix(a, b, t):
    """Blend hex color a toward hex color b (t from 0 to 1)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))


def draw_mic():
    mic.delete("all")
    mic.create_rectangle(0, 0, MIC_SIZE - 1, MIC_SIZE - 1,
                         outline=color("BORDER"))
    c = MIC_SIZE / 2
    mode, f = mic_state["mode"], mic_state["frame"]
    if mode == "listening":
        for k in range(3):   # three rings expanding outward and fading
            p = (f / 16 + k / 3) % 1
            r = 19 + p * 10
            mic.create_oval(c - r, c - r, c + r, c + r, width=2,
                            outline=mix(color("ACCENT"), color("CARD"), p))
    elif mode == "thinking":   # a spinning arc
        mic.create_arc(c - 25, c - 25, c + 25, c + 25, start=-f * 12,
                       extent=100, style="arc", width=3,
                       outline=color("ACCENT"))
    mic.create_oval(c - 19, c - 19, c + 19, c + 19,
                    fill=color("ACCENT"), outline=color("ACCENT"))
    ink = color("ON_ACCENT")
    mic.create_line(c, c - 9, c, c + 1, width=8, capstyle="round", fill=ink)
    mic.create_arc(c - 9, c - 11, c + 9, c + 7, start=180, extent=180,
                   style="arc", width=2, outline=ink)
    mic.create_line(c, c + 7, c, c + 11, width=2, fill=ink)
    mic.create_line(c - 5, c + 11, c + 5, c + 11, width=2, fill=ink)


def mic_set(mode):
    mic_state["mode"] = mode
    mic_state["frame"] = 0
    draw_mic()


def on_mic_tap(event=None):
    if mic_state["mode"] != "idle":      # tap again = cancel
        mic_set("idle")
        say(reply_label, "", "MUTED")
    elif not llm_busy["value"]:
        say(reply_label, "Listening...", "MUTED")
        mic_set("listening")


def mic_tick():
    mode = mic_state["mode"]
    if mode != "idle":
        mic_state["frame"] += 1
        f = mic_state["frame"]
        if mode == "listening" and f >= LISTEN_FRAMES:
            phrase = MOCK_PHRASES[mic_state["next"] % len(MOCK_PHRASES)]
            mic_state["next"] += 1
            mic_state["phrase"] = phrase
            say(reply_label, f'Heard: "{phrase}"', "TEXT")
            mic_set("heard")
        elif mode == "heard" and f >= HEARD_FRAMES:
            mic_set("thinking")
            process_text(mic_state["phrase"])
        elif mode == "thinking" and not llm_busy["value"]:
            mic_set("idle")
        else:
            draw_mic()
    root.after(FRAME_MS, mic_tick)


mic.bind("<Button-1>", on_mic_tap)

# ------------------------------------------------- readings and warnings
def refresh_plant_status():
    name = selected_plant.get()
    plant = get_plant(name) if name != NO_PLANT else None

    if plant is None:
        set_status("neutral", "Pick a plant", "to check if conditions are ideal")
        return

    ideal = (f"{plant['name']}  ·  ideal {plant['min_temp']:.0f}-"
             f"{plant['max_temp']:.0f} °C, {plant['min_hum']:.0f}-"
             f"{plant['max_hum']:.0f}% RH")

    if state["reading"] is None:
        set_status("neutral", "Waiting for first reading...", ideal)
        return

    ok, messages = check_conditions(plant, *state["reading"])
    if ok:
        set_status("ok", "✔ Conditions are ideal", ideal, plant["notes"] or "")
    else:
        set_status("warn", "⚠ Conditions need attention", ideal,
                   "\n".join(messages))


def clock_text():
    return datetime.now().strftime("%I:%M:%S %p").lstrip("0")


def update_datetime():
    now = datetime.now()
    text = f"{now:%A, %B} {now.day}  ·  {now.strftime('%I:%M %p').lstrip('0')}"
    if text != date_line.zone.itemcget(date_line.item, "text"):
        date_line.config(text=text)
    root.after(5000, update_datetime)


def update_display():
    try:
        temperature = sensor.temperature
        humidity = sensor.humidity

        if temperature is not None and humidity is not None:
            temp_value.config(text=f"{temperature:.1f}")
            hum_value.config(text=f"{humidity:.1f}")
            say(status, f"● SENSOR CONNECTED  ·  last check {clock_text()}", "OK")
            state["reading"] = (temperature, humidity)
            refresh_plant_status()

    except RuntimeError:
        # DHT22 readings can occasionally fail.
        say(status, f"Waiting for sensor reading...  ·  last check {clock_text()}",
            "WAIT")

    root.after(2500, update_display)


def close_app(event=None):
    try:
        sensor.exit()
    finally:
        root.destroy()


root.bind("<Escape>", close_app)
root.protocol("WM_DELETE_WINDOW", close_app)

show_page("monitor")
refresh_plant_status()
update_datetime()
update_display()
check_for_answer()
draw_mic()
mic_tick()
root.mainloop()
