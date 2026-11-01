"""Loading and saving settings.json (in a temp folder, never the real one)."""
import json
import tempfile
import unittest
from pathlib import Path

from settings import load_settings, save_settings, DEFAULTS


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "settings.json"

    def tearDown(self):
        self.folder.cleanup()

    def write(self, text):
        self.path.write_text(text, encoding="utf-8")

    def test_missing_file_gives_defaults(self):
        self.assertEqual(load_settings(self.path), DEFAULTS)
        self.assertEqual(DEFAULTS, {"theme": "light", "size": "Medium"})

    def test_corrupt_file_gives_defaults(self):
        for text in ("{not json", "", "[1, 2]", "null", '"dark"'):
            self.write(text)
            self.assertEqual(load_settings(self.path), DEFAULTS, text)

    def test_unknown_values_fall_back_per_key(self):
        self.write(json.dumps({"theme": "neon", "size": "Large"}))
        self.assertEqual(load_settings(self.path), {"theme": "light", "size": "Large"})
        self.write(json.dumps({"theme": "dark", "size": 3}))
        self.assertEqual(load_settings(self.path), {"theme": "dark", "size": "Medium"})
        self.write(json.dumps({"theme": "Dark"}))   # names are exact
        self.assertEqual(load_settings(self.path), DEFAULTS)

    def test_unreadable_path_gives_defaults(self):
        self.path.mkdir()   # a folder where the file should be
        self.assertEqual(load_settings(self.path), DEFAULTS)

    def test_round_trip(self):
        save_settings("nature", "Small", self.path)
        self.assertEqual(load_settings(self.path), {"theme": "nature", "size": "Small"})
        save_settings("dark", "Large", self.path)
        self.assertEqual(load_settings(self.path), {"theme": "dark", "size": "Large"})

    def test_save_leaves_no_temp_files(self):
        save_settings("dark", "Large", self.path)
        self.assertEqual([p.name for p in Path(self.folder.name).iterdir()],
                         ["settings.json"])

    def test_save_ignores_io_errors(self):
        missing = Path(self.folder.name) / "no-such-folder" / "settings.json"
        save_settings("dark", "Large", missing)   # must not raise
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
