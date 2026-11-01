"""Saves the theme and text size between runs, in settings.json next to gui.py.

Loading never fails: a missing, unreadable or corrupt file, or an unknown
value, just means the default for that setting. Saving quietly gives up on
I/O errors (a read-only SD card shouldn't stop the app).
"""
import json
import os
import tempfile
from pathlib import Path

from theme import THEMES, SIZES

SETTINGS_PATH = Path(__file__).with_name("settings.json")
DEFAULTS = {"theme": "light", "size": "Medium"}
ALLOWED = {"theme": THEMES, "size": SIZES}


def load_settings(path=SETTINGS_PATH):
    """{"theme": ..., "size": ...}, falling back to Light / Medium per key."""
    try:
        with open(path, encoding="utf-8") as file:
            saved = json.load(file)
    except (OSError, ValueError):
        saved = {}
    if not isinstance(saved, dict):
        saved = {}
    settings = {}
    for key, default in DEFAULTS.items():
        value = saved.get(key)
        settings[key] = value if isinstance(value, str) and value in ALLOWED[key] else default
    return settings


def save_settings(theme, size, path=SETTINGS_PATH):
    """Write atomically: a temp file in the same folder, then a rename."""
    path = Path(path)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".settings-", suffix=".tmp",
                                         delete=False) as file:
            temp_name = file.name
            json.dump({"theme": theme, "size": size}, file)
        os.replace(temp_name, path)
    except OSError:
        if temp_name:
            try:
                os.remove(temp_name)
            except OSError:
                pass
