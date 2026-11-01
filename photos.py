"""Optional plant photos for the Plants page.

Put one picture per plant in a folder called "photos" next to gui.py, named
after the plant in lowercase with underscores: basil.jpg, bell_pepper.png ...
(.png, .gif, .jpg, .jpeg, .webp). Without Pillow only .png and .gif work.
A plant with no photo just shows a drawn placeholder leaf.
"""
import base64
import io
import tkinter as tk
from pathlib import Path

PHOTO_DIR = Path(__file__).with_name("photos")
TYPES = (".png", ".gif", ".jpg", ".jpeg", ".webp")
_cache = {}


def find_photo(name):
    stem = name.lower().replace(" ", "_")
    for ext in TYPES:
        path = PHOTO_DIR / (stem + ext)
        if path.exists():
            return path
    return None


def load_photo(name, box):
    """A Tk image of the plant's photo, shrunk to fit box x box, or None."""
    key = (name, box)
    if key in _cache:
        return _cache[key]
    image = None
    path = find_photo(name)
    if path:
        try:
            from PIL import Image
            picture = Image.open(path).convert("RGB")
            picture.thumbnail((box, box))
            buffer = io.BytesIO()
            picture.save(buffer, format="PNG")
            image = tk.PhotoImage(data=base64.b64encode(buffer.getvalue()))
        except ImportError:
            if path.suffix.lower() in (".png", ".gif"):
                image = tk.PhotoImage(file=str(path))
                factor = max(1, -(-max(image.width(), image.height()) // box))
                if factor > 1:
                    image = image.subsample(factor)
        except Exception:
            image = None   # a broken file just means "no photo"
    _cache[key] = image
    return image
