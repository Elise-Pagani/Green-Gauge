# Green Gauge

**Climate Monitor** with **Sprout**, the plant assistant. An offline Raspberry Pi greenhouse
assistant (HCI class project), written in Python + Tkinter. It reads a DHT22
temperature/humidity sensor, compares the readings with a local plant database, warns when
conditions aren't ideal for your plant, and answers questions through a local LLM (Ollama).
Goal: work as offline as possible.

Run with `python3 gui.py`. Esc quits.

## Key features

- **Monitor tab**: live temperature and humidity cards and a status card for your plant
  (ideal = green with a check mark; not ideal = red with a warning and the reasons, e.g.
  "Too hot (33.0 °C, ideal 18–27 °C)"). Status always uses an icon and words, never color
  alone. `Change plant ›` (or `Choose a plant ›`) opens the Plants tab. When a warning is on,
  the Monitor tab button shows **⚠ Monitor**, so you see it from the other tabs too.
- **Plants tab**: browse plants with the `<` `>` buttons. Shows a photo, ideal temperature
  and humidity, watering, soil, soil pH and a care note. Browsing never changes your plant;
  **Set as my plant** does (it then reads **✔ Your plant**).
- **Assistant tab**: type a question and Sprout answers in two short sentences, using the plant
  database as its reference. It remembers your last 2 questions, so follow-ups like "And what
  temperature?" work; **Clear** forgets them (so does changing your plant). Saying "I'm
  growing basil" asks **Make Basil your plant? Yes / No**. Sprout never changes your plant on
  its own.
- **Mock voice input**: tap the mic for a "listening" animation, then "thinking", then the
  answer. It is a Wizard-of-Oz simulation, since the Pi has no microphone: it "hears" the next
  phrase in `MOCK_PHRASES` (in `assistant.py`) and runs it like typed text. The typed box is
  the real input. Tapping the mic again cancels.
- **Settings ▾** (top right): Theme (Light, Dark, Nature with a blurred photo background kept
  readable) and Text size (Small, Medium, Large). The layout is fixed at 800×480. Your choice
  is saved in `settings.json` next to `gui.py` (not in the repo) and restored at the next start.
- **Readable everywhere**: one five-step type scale (display, title, heading, body, caption), text
  contrast of at least 4.5:1 and control outlines of at least 3:1 in every theme, and touch
  targets at least 44 px tall.
- **Sensor fallback**: on the Pi the app uses the real DHT22; on any other machine it uses a
  simulated sensor (random readings that fail on purpose about 1 in 4 times: the temperature
  and the humidity each fail 12% of the time, independently). The footer says
  "● Simulated sensor" then.

## Files

| File | Purpose |
|---|---|
| `gui.py` | The app window: header, tabs, Settings menu, backdrop, timers, sensor loop |
| `monitor_page.py`, `plants_page.py`, `assistant_page.py` | The three tabs |
| `assistant.py` | Sprout's logic (no Tk): suggestions, history, mock voice (`MOCK_PHRASES`) |
| `commands.py` | Decides whether text is a plant selection or a question for Sprout |
| `llm.py` | Talks to Ollama (`MODEL` is set here) |
| `plant_db.py` | SQLite database. `SEED_PLANTS` is the master list: edit it and restart |
| `units.py` | How readings, ranges and warnings are written (`24.3 °C`, `18–27 °C`, `pH 6.0–6.5`) |
| `theme.py` | Colors of the three themes, the type scale and fonts |
| `widgets.py`, `zones.py` | Shared widget helpers; text drawn directly on the backdrop |
| `mic.py` | The drawn mic button and its animation |
| `settings.py` | Loads and saves `settings.json` |
| `sensor.py` | Real DHT22 on the Pi (GPIO4), simulated sensor elsewhere |
| `photos.py`, `background.py` | Plant photos; the Nature backdrop |
| `tests/` | Unit tests (`unittest`, no display or Ollama needed) |
| `photos/` | One square picture per plant, named after the plant: `basil.jpg`, `bell_pepper.jpg`. The current ones are about 430 px square JPEGs, shown at 170 px. Any of `.png .gif .jpg .jpeg .webp` works |
| `backgrounds/` | Optional photo for the Nature theme |

`plants.db` and `settings.json` are generated automatically and not stored in the repo.

## Tests

```bash
python3 -m unittest discover -s tests
```

## Setup on a new machine

```bash
pip install -r requirements.txt        # Pillow (Nature theme and photos)
```

Tkinter comes with Python (Fedora: `sudo dnf install python3-tkinter`; Pi/Debian:
`sudo apt install python3-tk`). Install Ollama and download the model once (needs wifi):

```bash
ollama pull llama3.2:3b
```

## Pi day checklist

1. **Pi model**: `cat /proc/device-tree/model` (Pi 4 or 5 not yet confirmed).
2. **Screen resolution**:
   `python3 -c "import tkinter as tk; r=tk.Tk(); print(r.winfo_screenwidth(), r.winfo_screenheight())"`
   The app is built for 800x480 and the professor said to keep the resolution as is.
3. **Copy the project** to the Pi (`git clone` or copy the folder) and install Tkinter and
   Pillow. On newer Pi OS, `pip` may refuse system-wide installs; use
   `sudo apt install python3-pil` or a virtual environment.
4. **Sensor libraries**: `pip install -r requirements-pi.txt` (the Adafruit DHT library; this
   file hasn't been tested on a real Pi). The professor's code also uses `board`.
5. **Confirm the real sensor is used**: `python3 -c "import sensor; print(sensor.ON_PI)"`
   must print `True`. The footer then says "● Sensor connected". If it says
   "● Simulated sensor", the readings are fake.
6. **Wiring**: DHT22 data pin on GPIO4 (physical pin 7). A different pin means editing
   `adafruit_dht.DHT22(board.D4, ...)` in `sensor.py`.
7. **Ollama**: install it on the Pi (`curl -fsSL https://ollama.com/install.sh | sh`), then
   `ollama pull llama3.2:3b`. If answers are too slow, change `MODEL` in `llm.py` to
   `llama3.2:1b` (or `qwen2.5:1.5b`) and pull that model instead. The first answer is slow
   while the model loads.
8. **Run**: `python3 gui.py` (it goes fullscreen on the Pi). Check:
   - readings change and match the real room (breathe on the sensor to test)
   - the status card follows your plant
   - touchscreen: tabs, Settings, `<` `>` buttons, mic and the Ask box are easy to tap
     (all are at least 44 px tall; not yet tried with a finger)
   - an on-screen keyboard is available if there is no physical one
   - all three themes and text sizes fit the screen. At Large, check that the date line
     doesn't touch the Settings button on a long date such as "Wednesday, September 30"
     (checked with a stand-in font, not DejaVu Sans)

## Photo sources

All plant photos are from [Pixabay](https://pixabay.com) and used under the
[Pixabay Content License](https://pixabay.com/service/license-summary/), which allows free use
and modification.

| Plant | Photographer (Pixabay username) | Link |
|---|---|---|
| Tomato | [Ralphs_Fotos](https://pixabay.com/users/ralphs_fotos-1767157/) | [https://pixabay.com/photos/...](https://pixabay.com/photos/tomatoes-panicle-tomato-4434850/) |
| Cucumber | [artellliii72](https://pixabay.com/users/artellliii72-15900295/) | [https://pixabay.com/photos/...](https://pixabay.com/photos/cucumbers-vegetable-garden-7322966/) |
| Bell Pepper | [senjakelabu29](https://pixabay.com/users/senjakelabu29-9800347/) | [https://pixabay.com/photos/...](https://pixabay.com/photos/chili-paprika-fruit-plant-food-5985294/) |
| Lettuce | [Zotx](https://pixabay.com/users/zotx-14174246/) | [https://pixabay.com/photos/...](https://pixabay.com/photos/salad-field-agriculture-vegetables-4755777/) |
| Spinach | [maikewilstermann](https://pixabay.com/users/maikewilstermann-5018575/) | [https://pixabay.com/photos/...](https://pixabay.com/photos/spinach-vegetable-patch-garden-4062500/) |
| Basil | [\_Alicja\_](https://pixabay.com/users/_alicja_-5975425/) | [https://pixabay.com/photos/...](https://pixabay.com/photos/basil-total-spice-plant-herbs-2759337/) |
| Mint | [Squirrel_photos](https://pixabay.com/users/squirrel_photos-7862139/) | [https://pixabay.com/photos/...](https://pixabay.com/photos/mint-plant-healing-herbs-leaves-6544690/) |
| Strawberry | [Kathas_Fotos](https://pixabay.com/users/kathas_fotos-11174123/) | [https://pixabay.com/photos/...](https://pixabay.com/photos/strawberries-strawberry-patch-7323943/) |
| Orchid | [trungkhang](https://pixabay.com/users/trungkhang-29069499/) | [https://pixabay.com/photos/...](https://pixabay.com/photos/orchid-flowers-plant-phalaenopsis-7511812/) |
| Cactus | [ignartonosbg](https://pixabay.com/users/ignartonosbg-21428489/) | [https://pixabay.com/photos/...](https://pixabay.com/photos/cactus-flora-flower-plant-nature-7856967/) |

## Background photo

The Nature theme's background (`backgrounds/pexels-gianluca-buonaiuto-4849527-29731003.jpg`) is
"Sunlit Green Leaves in Forest Canopy", photo by Gianluca Buonaiuto on Pexels:
<https://www.pexels.com/photo/29731003/>, used under the
[Pexels License](https://www.pexels.com/license/).
