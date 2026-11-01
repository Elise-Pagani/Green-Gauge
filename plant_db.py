"""Local plant database (SQLite, fully offline).

Stores the ideal temperature (°C) and relative humidity (%) range for
each plant, plus watering, soil and soil pH. The ranges below are general starting values for a
greenhouse and should be double-checked before anyone relies on them.
"""
import sqlite3
from pathlib import Path

import units

DB_PATH = Path(__file__).with_name("plants.db")

# name, min_temp, max_temp, min_hum, max_hum, notes, water, soil, ph_min, ph_max
# This list is the master copy: edit it and restart, and the database follows.
SEED_PLANTS = [
    ("Tomato",      18, 27, 50, 70, "Fruit set suffers above ~30 °C.", "2–3 times a week", "Sandy loam", 6.0, 6.5),
    ("Cucumber",    21, 27, 60, 80, "Likes it warm and humid.", "Every 2–3 days", "Loam", 6.0, 6.5),
    ("Bell Pepper", 21, 29, 50, 70, "Sensitive to cold nights.", "Every 2–3 days", "Sandy loam", 6.0, 6.8),
    ("Lettuce",     15, 21, 50, 70, "Bolts (goes to seed) in heat.", "2–3 times a week", "Loam", 6.2, 6.5),
    ("Spinach",     10, 21, 50, 60, "Prefers cool conditions.", "2–3 times a week", "Loam", 6.5, 7.0),
    ("Basil",       18, 29, 40, 60, "Damaged by cold; avoid very high humidity.", "Every 3–5 days", "Loam", 6.0, 7.0),
    ("Mint",        18, 24, 40, 60, "Tolerant, but keep it out of extreme heat.", "Every 3–4 days", "Loam", 6.0, 7.0),
    ("Strawberry",  15, 26, 60, 75, "Good airflow helps prevent mold.", "1–2 times a week", "Sandy loam", 5.8, 6.2),
    ("Orchid",      18, 29, 50, 70, "Based on common moth orchids (Phalaenopsis).", "Once a week", "Bark mix", 5.5, 6.5),
    ("Cactus",      18, 32, 10, 40, "Needs dry air; humidity is the main risk.", "Every 7–10 days", "Organic-grit mix", 6.0, 7.0),
]

COLUMNS = ["name", "min_temp", "max_temp", "min_hum", "max_hum", "notes",
           "water", "soil", "ph_min", "ph_max"]
# Columns added after the first version of the database (added to old files)
ADDED_COLUMNS = {"water": "TEXT", "soil": "TEXT", "ph_min": "REAL", "ph_max": "REAL"}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the table, upgrade an older database file, and load the seed."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plants (
                name     TEXT PRIMARY KEY COLLATE NOCASE,
                min_temp REAL NOT NULL,
                max_temp REAL NOT NULL,
                min_hum  REAL NOT NULL,
                max_hum  REAL NOT NULL,
                notes    TEXT,
                water    TEXT,
                soil     TEXT,
                ph_min   REAL,
                ph_max   REAL
            )
            """
        )
        # An older plants.db won't have the newer columns: add them
        have = {row["name"] for row in conn.execute("PRAGMA table_info(plants)")}
        for column, kind in ADDED_COLUMNS.items():
            if column not in have:
                conn.execute(f"ALTER TABLE plants ADD COLUMN {column} {kind}")
        # Insert new plants and refresh the seeded ones, so editing SEED_PLANTS
        # is enough. Plants that aren't in the seed list are left alone.
        updates = ", ".join(f"{c} = excluded.{c}" for c in COLUMNS[1:])
        conn.executemany(
            f"INSERT INTO plants ({', '.join(COLUMNS)}) "
            f"VALUES ({', '.join('?' * len(COLUMNS))}) "
            f"ON CONFLICT(name) DO UPDATE SET {updates}",
            SEED_PLANTS,
        )


def list_plants():
    """All plant names, alphabetical."""
    with _connect() as conn:
        rows = conn.execute("SELECT name FROM plants ORDER BY name").fetchall()
    return [r["name"] for r in rows]


def get_plant(name):
    """Return a plant as a dict, or None if it isn't in the database."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM plants WHERE name = ?", (name.strip(),)
        ).fetchone()
    return dict(row) if row else None


def check_conditions(plant, temperature, humidity):
    """Compare current readings to a plant's ideal ranges.

    Returns (ok, messages). `plant` is a dict from get_plant().
    """
    messages = []
    ideal_temp = units.temperature_range(plant["min_temp"], plant["max_temp"])
    ideal_hum = units.humidity_range(plant["min_hum"], plant["max_hum"])
    if temperature < plant["min_temp"]:
        messages.append(f"Too cold ({units.temperature(temperature)}, ideal {ideal_temp})")
    elif temperature > plant["max_temp"]:
        messages.append(f"Too hot ({units.temperature(temperature)}, ideal {ideal_temp})")

    if humidity < plant["min_hum"]:
        messages.append(f"Too dry ({units.humidity(humidity)}, ideal {ideal_hum})")
    elif humidity > plant["max_hum"]:
        messages.append(f"Too humid ({units.humidity(humidity)}, ideal {ideal_hum})")

    return (len(messages) == 0, messages)


if __name__ == "__main__":
    # Quick self-test: python3 plant_db.py
    init_db()
    print("Plants:", ", ".join(list_plants()))
    tomato = get_plant("tomato")
    print("Tomato:", tomato)
    print("Check 24 °C / 60%:", check_conditions(tomato, 24, 60))
    print("Check 33 °C / 85%:", check_conditions(tomato, 33, 85))
