# Greenhouse Assistant

An offline Raspberry Pi greenhouse assistant (HCI class project), written in Python + Tkinter.
It reads a DHT22 temperature/humidity sensor, compares the readings with a local plant
database, warns when conditions aren't ideal for the selected plant, and answers questions
through a local LLM (Ollama). Goal: work as offline as possible.

Run with `python3 gui.py`. Esc quits.

## Key features

- **Monitor page**: live temperature and humidity cards, plant picker, and a status card
  (ideal = green with a check mark; not ideal = red with a warning and the reasons).
  Status always uses an icon and words, never color alone.
- **Plants page**: browse plants with the `<` `>` buttons. Shows a photo, ideal temperature
  and humidity, watering, soil, soil pH and a care note. The selected plant is shared with the
  Monitor page.
- **Assistant page**: type a question (or say "I'm planting basil" to select a plant) and the
  local LLM answers in two short sentences, using the plant database as its reference.
- **Mock voice input**: tap the mic for a "listening" animation, then "thinking", then the
  answer. It is a Wizard-of-Oz simulation, since the Pi has no microphone: it "hears" the next
  phrase in `MOCK_PHRASES` (in `gui.py`) and runs it like typed text. The typed box is the real input.
- **Themes and text sizes**: Light, Dark and Nature (blurred photo background kept readable);
  Small, Medium, Large text. Layout is fixed at 800x480. Settings are not saved between runs.
- **Sensor fallback**: on the Pi the app uses the real DHT22; on any other machine it uses a
  simulated sensor (random readings that fail about 1 in 8 reads, on purpose).

## Files

| File | Purpose |
|---|---|
| `gui.py` | The app: themes, pages, settings, mock mic, sensor loop |
| `sensor.py` | Real DHT22 on the Pi (GPIO4), simulated sensor elsewhere |
| `plant_db.py` | SQLite database. `SEED_PLANTS` is the master list: edit it and restart |
| `commands.py` | Decides whether text is a question (LLM) or a plant selection |
| `llm.py` | Talks to Ollama (`MODEL` is set here) |
| `photos.py` | Loads plant photos from `photos/` |
| `background.py`, `zones.py` | Nature backdrop and text drawn directly on it |
| `photos/` | One square picture per plant, e.g. `basil.png`, `bell_pepper.png` (340x340 px) |
| `backgrounds/` | Optional photo for the Nature theme |

`plants.db` is generated automatically and not stored in the repo.

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
   must print `True`. If it prints `False` the app silently shows fake readings, and the
   status line still says "SENSOR CONNECTED".
6. **Wiring**: DHT22 data pin on GPIO4 (physical pin 7). A different pin means editing
   `adafruit_dht.DHT22(board.D4, ...)` in `sensor.py`.
7. **Ollama**: install it on the Pi (`curl -fsSL https://ollama.com/install.sh | sh`), then
   `ollama pull llama3.2:3b`. If answers are too slow, change `MODEL` in `llm.py` to
   `llama3.2:1b` (or `qwen2.5:1.5b`) and pull that model instead. The first answer is slow
   while the model loads.
8. **Run**: `python3 gui.py` (it goes fullscreen on the Pi). Check:
   - readings change and match the real room (breathe on the sensor to test)
   - the status card follows the selected plant
   - touchscreen: tabs, `<` `>` buttons, mic and the ASK box are easy to tap (not yet verified)
   - an on-screen keyboard is available if there is no physical one
   - all three themes and text sizes fit the screen

## Photo sources

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
