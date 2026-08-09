"""Focused release checks using only the Python standard-library test runner."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from core import settings, storage


ROOT = Path(__file__).resolve().parents[1]
AUDIO_DIR = ROOT / "assets" / "audio"
SPRITES_DIR = ROOT / "assets" / "sprites"


def _assigned_literal(path: Path, name: str) -> object:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not assigned in {path}")


class StorageTests(unittest.TestCase):
    def test_desktop_storage_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            with (
                mock.patch.object(storage, "is_web", return_value=False),
                mock.patch.object(storage, "writable_data_dir", return_value=data_dir),
            ):
                self.assertIsNone(storage.read_text("sample.txt"))
                self.assertFalse(storage.exists("sample.txt"))

                storage.write_text("sample.txt", "Dobby ✓")

                self.assertEqual(storage.read_text("sample.txt"), "Dobby ✓")
                self.assertTrue(storage.exists("sample.txt"))
                self.assertEqual(storage.path_for("sample.txt"), data_dir / "sample.txt")

    def test_web_storage_uses_namespaced_local_storage(self) -> None:
        values: dict[str, str] = {}

        class FakeLocalStorage:
            def getItem(self, key: str) -> str | None:
                return values.get(key)

            def setItem(self, key: str, value: str) -> None:
                values[key] = value

        browser_platform = types.SimpleNamespace(
            window=types.SimpleNamespace(localStorage=FakeLocalStorage())
        )
        with (
            mock.patch.object(storage, "is_web", return_value=True),
            mock.patch.dict(sys.modules, {"platform": browser_platform}),
        ):
            self.assertIsNone(storage.read_text("sample.txt"))
            storage.write_text("sample.txt", "browser value")
            self.assertEqual(values, {"dobbycat:sample.txt": "browser value"})
            self.assertEqual(storage.read_text("sample.txt"), "browser value")
            self.assertTrue(storage.exists("sample.txt"))


class AudioSettingsTests(unittest.TestCase):
    def test_missing_or_invalid_settings_use_defaults(self) -> None:
        default = settings.AudioSettings()
        for text in (None, "", "{broken", "[]", '{"music_volume": "loud"}'):
            with self.subTest(text=text), mock.patch.object(
                settings.storage, "read_text", return_value=text
            ):
                self.assertEqual(settings.load_audio_settings(), default)

    def test_loaded_volumes_are_clamped(self) -> None:
        payload = json.dumps(
            {"muted": True, "music_volume": 1.7, "sfx_volume": -0.25}
        )
        with mock.patch.object(settings.storage, "read_text", return_value=payload):
            loaded = settings.load_audio_settings()

        self.assertTrue(loaded.muted)
        self.assertEqual(loaded.music_volume, 1.0)
        self.assertEqual(loaded.sfx_volume, 0.0)

    def test_save_uses_expected_storage_key_and_json(self) -> None:
        value = settings.AudioSettings(muted=True, music_volume=0.3, sfx_volume=0.8)
        with mock.patch.object(settings.storage, "write_text") as write_text:
            settings.save_audio_settings(value)

        name, payload = write_text.call_args.args
        self.assertEqual(name, "audio_settings.json")
        self.assertEqual(json.loads(payload), vars(value))


class RuntimeMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audio_source = ROOT / "core" / "audio.py"
        cls.game_source = ROOT / "games" / "booth_blaster.py"
        cls.music_files = _assigned_literal(cls.audio_source, "MUSIC_FILES")
        cls.sfx_files = _assigned_literal(cls.audio_source, "SFX_FILES")

    def test_music_keys_and_scene_calls_match(self) -> None:
        self.assertEqual(
            self.music_files,
            {
                "title": "music_title.wav",
                "game": "music_game.wav",
                "boss": "music_boss.wav",
            },
        )
        game_tree = ast.parse(
            self.game_source.read_text(encoding="utf-8"),
            filename=str(self.game_source),
        )
        scene_music_keys = {
            call.args[0].value
            for call in ast.walk(game_tree)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "play_music"
            and call.args
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        }
        self.assertEqual(scene_music_keys, set(self.music_files))

    def test_required_audio_formats_and_web_staging(self) -> None:
        filenames = {*self.music_files.values(), *self.sfx_files.values()}
        missing = [
            name
            for name in sorted(filenames)
            for suffix in (".wav", ".ogg")
            if not (AUDIO_DIR / f"{Path(name).stem}{suffix}").is_file()
        ]
        self.assertEqual(missing, [])

        workflow = (ROOT / ".github" / "workflows" / "deploy-pages.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("cp assets/audio/*.ogg web_src/assets/audio/", workflow)

    def test_referenced_runtime_sprites_exist(self) -> None:
        game_tree = ast.parse(
            self.game_source.read_text(encoding="utf-8"),
            filename=str(self.game_source),
        )
        sprite_names = {
            node.value
            for node in ast.walk(game_tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and len(node.value) > len(".png")
            and node.value.endswith(".png")
            and "/" not in node.value
            and "\\" not in node.value
        }
        self.assertGreater(len(sprite_names), 10)
        missing = sorted(name for name in sprite_names if not (SPRITES_DIR / name).is_file())
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
