"""The app's entry point: python3 gui.py

Owns the window, the shared grid, the header, the page tabs, the footer,
page switching, the backdrop, the settings menu and the timers. The pages
themselves live in monitor_page.py, plants_page.py and assistant_page.py.
Importing this module doesn't open a window; main() does.
"""
import tkinter as tk
import traceback
from datetime import datetime

import background
import theme
from assistant import Assistant
from assistant_page import AssistantPage
from monitor_page import MonitorPage
from plant_db import init_db
from plants_page import PlantsPage
from sensor import get_sensor, ON_PI
from settings import load_settings, save_settings
from theme import THEMES, SIZES, NATURE_TEXT_COLORS, paint
from widgets import make_line, say
from zones import TextZone, RowZone

PAGE_TITLES = {"monitor": "Monitor", "plants": "Plants",
               "assistant": "Sprout"}
TAB_WIDTH = 10   # characters: room for "⚠ Monitor", so the badge never shifts the tabs

FRAME_MS = 50          # mic animation frame
ANSWER_POLL_MS = 200   # how often to look for a finished LLM answer
SENSOR_MS = 2500       # how often to read the sensor


class App:
    def __init__(self):
        self.sensor = get_sensor()   # real DHT22 on the Pi, simulated elsewhere
        self.page = "monitor"
        self.reading = None          # last good (temperature, humidity)
        self.grid_options = {}       # widget -> its grid() options
        self.backdrops = {}          # theme name -> PhotoImage, built once
        self.backdrop_label = None
        self.shown_view = None       # the assistant view last drawn on the Sprout page
        # The user's plant. Only the Plants page button and saying Yes to
        # Sprout's suggestion change it (set_active_plant).
        self.active_plant = None
        self.status_kind = "neutral"   # the Monitor status: neutral | ok | warn

        self.root = self._build_window()
        self._build_header()
        self.monitor = MonitorPage(self.root, self.put,
                                   lambda: self.show_page("plants"))
        self.assistant_page = AssistantPage(
            self.root, self.put, self.submit_command, self.on_mic_tap,
            on_yes=lambda: self.assistant.accept_suggestion(),
            on_no=lambda: self.assistant.decline_suggestion(),
            on_clear=lambda: self.assistant.clear(),
            window_width=self.screen_size()[0])
        self.plants = PlantsPage(self.root, self.put, lambda: self.active_plant,
                                 self.set_active_plant)
        self._build_tabs()
        self._build_footer()
        self.zones = [self.header, *self.monitor.zones, *self.assistant_page.zones,
                      *self.plants.zones, self.nav, self.footer]
        self.pages = {"monitor": self.monitor.widgets,
                      "plants": self.plants.widgets,
                      "assistant": self.assistant_page.widgets}
        self._show_first_backdrop()
        self._build_settings_menu()
        # Typed questions and the mock mic share this one assistant state
        self.assistant = Assistant(
            get_context=lambda: (self.active_plant, self.reading),
            on_plant=self.set_active_plant, on_change=self.render_assistant)

    # ----------------------------------------------------------- layout
    # One grid, two columns. Rows (the same grid is shared by all pages):
    #   0  header zone: title + date/time                       (all pages)
    #   1  reading cards                                        (Monitor page)
    #   2  status card | plant card | Sprout's question + answer (grows to fill)
    #   3  browse row | "Make Basil your plant?" row (only when it's needed)
    #   4  typed question box                                   (Sprout page)
    #   5  page tabs                                            (all pages)
    #   6  sensor status line                                   (all pages)
    # The zones are canvases (see zones.py): their text is drawn directly on
    # the backdrop, so there are no boxes around it. Cards are solid on purpose.
    def _build_window(self):
        root = tk.Tk()
        root.title("Green Gauge")
        root.geometry("800x480")   # the size the professor's original code used
        if ON_PI:
            root.attributes("-fullscreen", True)
        else:
            root.resizable(False, False)   # on a PC/Mac, keep it at the Pi's size
        paint(root, bg="BG")
        root.columnconfigure((0, 1), weight=1, uniform="cols")
        root.rowconfigure(2, weight=1)

        # Tk quirk: when EVERY widget on a page spans both columns (as on the
        # Assistant page), the grid stops re-arranging when a widget's size
        # changes, so text-size changes and long answers don't take effect and
        # a re-shown page can stay blank. One zero-size, invisible widget in
        # each single column, present on every page, keeps the grid working.
        # (Created first, so they sit under the cards.)
        self.column_anchors = []
        for column in (0, 1):
            anchor = tk.Frame(root, width=0, height=0, highlightthickness=0, bd=0)
            anchor.grid(row=1, column=column)
            self.column_anchors.append(anchor)
        return root

    def put(self, widget, show=True, **options):
        """Record where a widget goes, and (unless show=False) place it now.
        Widgets for a page that isn't showing at startup use show=False: Tk
        gets confused by widgets that are placed and then hidden before they
        were ever drawn (they wouldn't resize properly later), so they're only
        placed the first time their page is shown."""
        self.grid_options[widget] = options
        if show:
            widget.grid(**options)

    def _build_header(self):
        self.header = TextZone(self.root, pad_top=10, pad_bottom=2)
        paint(self.header, bg="BG")
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        make_line(self.header, "Green Gauge", 24, "ACCENT", True)
        self.date_line = make_line(self.header, "", 11, "MUTED")

    def _build_tabs(self):
        """Page tabs (always visible, easy to tap)."""
        self.nav = RowZone(self.root, pad_top=2, pad_bottom=2)
        paint(self.nav, bg="BG")
        self.nav.grid(row=5, column=0, columnspan=2, sticky="ew")
        self.tabs = {}
        for page_name, page_title in PAGE_TITLES.items():
            tab = tk.Label(self.nav, text=page_title, font=theme.get_font(12, True),
                           width=TAB_WIDTH, padx=16, pady=7, highlightthickness=1,
                           cursor="hand2")
            tab.bind("<Button-1>", lambda _event, name=page_name: self.show_page(name))
            self.tabs[page_name] = tab
            self.nav.add_widget(tab, padx=(6, 6))

    def _build_footer(self):
        """The sensor status line."""
        self.footer = TextZone(self.root, pad_top=2, pad_bottom=6)
        paint(self.footer, bg="BG")
        self.footer.grid(row=6, column=0, columnspan=2, sticky="ew")
        self.status = make_line(self.footer, "Connecting to sensor...", 10, "OK")

    # ------------------------------------------------------------ pages
    def nudge_zones(self):
        self.root.update_idletasks()
        for zone in self.zones:
            zone.refresh()

    def show_page(self, name):
        """Show one page's widgets and hide the others'."""
        for page, widgets in self.pages.items():
            for widget in widgets:
                if page == name:
                    widget.grid(**self.grid_options[widget])
                else:
                    widget.grid_forget()   # re-gridded later from grid_options
        self.page = name
        if name == "plants":
            self.plants.show()
        self.assistant_page.set_shown(name == "assistant")
        self.paint_tabs()
        self.nudge_zones()   # re-line-up the backdrop under each zone
        # On the Mac the boxes in the bottom row can show up late. Lining
        # everything up again a moment later gives it a nudge to draw them.
        for delay_ms in (20, 150):
            self.root.after(delay_ms, self.nudge_zones)
        if name == "assistant":
            self.assistant_page.focus()

    def paint_tabs(self):
        """Highlight the current page's tab. A warning on the Monitor page
        puts a ⚠ on its tab (and, unless it's the current tab, warning
        colors), so it's seen from the other pages too."""
        warn = self.status_kind == "warn"
        for tab_name, tab in self.tabs.items():
            title = PAGE_TITLES[tab_name]
            badge = warn and tab_name == "monitor"
            tab.config(text=f"⚠ {title}" if badge else title)
            if tab_name == self.page:
                paint(tab, bg="ACCENT", fg="ON_ACCENT", highlightbackground="ACCENT")
            elif badge:
                paint(tab, bg="WARN_BG", fg="WARN", highlightbackground="WARN")
            else:
                paint(tab, bg="CARD", fg="TEXT", highlightbackground="BORDER")

    def set_active_plant(self, name):
        """Make a plant the user's plant, everywhere. Only the Plants page
        button and the Yes on Sprout's suggestion call this."""
        self.active_plant = name
        self.refresh_plant_status()
        self.plants.refresh()
        self.assistant.plant_changed(name)   # earlier questions were about another plant

    # --------------------------------------------------------- backdrop
    # The picture behind everything: a gradient for Light and Dark, a blurred
    # photo for Nature. One big label shows it behind the cards, and the text
    # zones (see zones.py) show the same picture lined up with their position,
    # so text looks printed right on it.
    def screen_size(self):
        if ON_PI:
            return self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        return 800, 480

    def build_backdrop(self, name):
        width, height = self.screen_size()
        if name == "nature":
            data = background.build_background(
                width, height, text_colors=NATURE_TEXT_COLORS)
            return tk.PhotoImage(data=data)
        return theme.make_gradient(width, height, THEMES[name]["GRAD_TOP"],
                                   THEMES[name]["GRAD_BOTTOM"])

    def show_backdrop(self, name):
        """Put the theme's backdrop behind everything."""
        if name not in self.backdrops:
            # Built first: if it fails, nothing is half-changed
            self.backdrops[name] = self.build_backdrop(name)
        photo = self.backdrops[name]
        if self.backdrop_label is None:
            self.backdrop_label = tk.Label(self.root, bd=0)
        label = self.backdrop_label
        label.config(image=photo)
        label.place(x=0, y=0, relwidth=1, relheight=1)
        label.lower()   # behind every other widget...
        for anchor in self.column_anchors:
            anchor.lower()   # ...except the invisible column anchors: under it, hidden
        for zone in self.zones:
            zone.set_photo(photo)

    def _show_first_backdrop(self):
        """The saved theme's backdrop, or Light's if that one can't be built
        (e.g. a saved Nature theme on a machine without Pillow)."""
        name = theme.current_theme()
        if name == "nature" and not background.pillow_available():
            print("The Nature theme needs Pillow; using Light instead.")
            name = "light"
        try:
            self.show_backdrop(name)
        except Exception:
            traceback.print_exc()
            name = "light"
            self.show_backdrop(name)
        if name != theme.current_theme():
            theme.set_theme(name)
            theme.repaint_all()

    # ---------------------------------------------------- settings menu
    def _build_settings_menu(self):
        self.theme_var = tk.StringVar(value=theme.current_theme())
        self.size_var = tk.StringVar(value=theme.current_size())

        button = tk.Menubutton(self.root, text="Settings ▾",
                               font=theme.get_font(10, True), relief="flat", bd=0,
                               padx=12, pady=6, highlightthickness=1)
        paint(button, bg="CARD", fg="TEXT",
              activebackground="ACCENT", activeforeground="ON_ACCENT",
              highlightbackground="BORDER")

        menu = tk.Menu(button, tearoff=0, font=theme.get_font(11))
        paint(menu, bg="CARD", fg="TEXT",
              activebackground="ACCENT", activeforeground="ON_ACCENT",
              disabledforeground="MUTED", selectcolor="ACCENT")
        button["menu"] = menu

        menu.add_command(label="THEME", state="disabled")
        for name in THEMES:
            label = name.title()
            if name == "nature" and not background.pillow_available():
                menu.add_radiobutton(label="Nature (needs Pillow)",
                                     variable=self.theme_var, value=name,
                                     state="disabled")
                continue
            menu.add_radiobutton(label=label, variable=self.theme_var,
                                 value=name, command=self.on_theme_change)
        menu.add_separator()
        menu.add_command(label="TEXT SIZE", state="disabled")
        for size_name in SIZES:
            menu.add_radiobutton(label=size_name, variable=self.size_var,
                                 value=size_name, command=self.on_size_change)

        button.place(relx=1.0, x=-15, y=12, anchor="ne")

    def on_theme_change(self):
        name = self.theme_var.get()
        try:
            self.show_backdrop(name)
        except Exception as error:   # e.g. Pillow missing or a bad image file
            self.theme_var.set(theme.current_theme())
            self.assistant_page.show_reply(
                f"Couldn't load the {name.title()} background ({error}).", "WARN")
            return
        theme.set_theme(name)
        theme.repaint_all()
        self.draw_mic()
        self.plants.refresh()
        save_settings(theme.current_theme(), theme.current_size())

    def on_size_change(self):
        theme.set_size(self.size_var.get())
        theme.apply_scale()
        self.assistant_page.update_wrap()
        self.root.update_idletasks()
        for zone in self.zones:
            zone.relayout()
        self.root.update_idletasks()
        save_settings(theme.current_theme(), theme.current_size())

    # -------------------------------------------------------- assistant
    def submit_command(self, event=None):
        entry = self.assistant_page.entry
        if self.assistant.submit(entry.get()):
            entry.delete(0, "end")
        # otherwise the text stays in the box (busy, or nothing typed)

    def on_mic_tap(self, event=None):
        self.assistant.tap_mic()

    def render_assistant(self):
        """Draw the assistant's state: the mic, and (when they changed) the
        question, the answer and the suggestion row."""
        view = self.assistant.view()
        self.assistant_page.mic.draw(view.mode, view.frame)
        text_view = view._replace(mode="", frame=0)   # the mic redraws alone
        if text_view != self.shown_view:
            self.shown_view = text_view
            self.assistant_page.render(view)

    def draw_mic(self):
        view = self.assistant.view()
        self.assistant_page.mic.draw(view.mode, view.frame)

    def mic_tick(self):
        try:
            self.assistant.tick()
        except Exception:
            traceback.print_exc()
        finally:
            self.root.after(FRAME_MS, self.mic_tick)

    def check_for_answer(self):
        try:
            self.assistant.poll()
        except Exception:
            traceback.print_exc()
        finally:
            self.root.after(ANSWER_POLL_MS, self.check_for_answer)

    # ---------------------------------------------- readings and timers
    def refresh_plant_status(self):
        kind = self.monitor.refresh(self.active_plant, self.reading)
        if kind != self.status_kind:
            self.status_kind = kind
            self.paint_tabs()

    def update_datetime(self):
        now = datetime.now()
        text = f"{now:%A, %B} {now.day}  ·  {now.strftime('%I:%M %p').lstrip('0')}"
        line = self.date_line
        if text != line.zone.itemcget(line.item, "text"):
            line.config(text=text)
        self.root.after(5000, self.update_datetime)

    def update_display(self):
        try:
            temperature = self.sensor.temperature
            humidity = self.sensor.humidity

            if temperature is not None and humidity is not None:
                self.monitor.show_reading(temperature, humidity)
                if ON_PI:
                    say(self.status,
                        f"● SENSOR CONNECTED  ·  last check {clock_text()}", "OK")
                else:   # don't claim a real sensor when the readings are fake
                    say(self.status,
                        f"● Simulated sensor  ·  last check {clock_text()}", "WAIT")
                self.reading = (temperature, humidity)
                self.refresh_plant_status()

        except RuntimeError:
            # DHT22 readings can occasionally fail.
            waiting = ("Waiting for sensor reading..." if ON_PI
                       else "Simulated sensor  ·  waiting for reading…")
            say(self.status, f"{waiting}  ·  last check {clock_text()}", "WAIT")
        except Exception:
            # Anything unexpected: report it, keep the loop alive
            traceback.print_exc()
            say(self.status, f"Sensor error, retrying…  ·  last check {clock_text()}",
                "WARN")
        finally:
            self.root.after(SENSOR_MS, self.update_display)

    def close(self, event=None):
        try:
            self.sensor.exit()
        finally:
            self.root.destroy()

    def start(self):
        """Show the first page and start the timers."""
        self.root.bind("<Escape>", self.close)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.show_page("monitor")
        self.refresh_plant_status()
        self.update_datetime()
        self.update_display()
        self.check_for_answer()
        self.draw_mic()
        self.mic_tick()


def clock_text():
    return datetime.now().strftime("%I:%M:%S %p").lstrip("0")


def main():
    init_db()   # make sure the plant database exists and is filled
    # The saved text size and theme go in before any widget is built
    saved = load_settings()
    theme.set_size(saved["size"])
    theme.set_theme(saved["theme"])
    app = App()
    app.start()
    app.root.mainloop()


if __name__ == "__main__":
    main()
