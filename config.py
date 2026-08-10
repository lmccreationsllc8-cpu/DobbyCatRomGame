"""Shared runtime settings for DobbyCatRomGame."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS_DIR = ROOT / "assets"
SPRITES_DIR = ASSETS_DIR / "sprites"
AUDIO_DIR = ASSETS_DIR / "audio"
FONTS_DIR = ASSETS_DIR / "fonts"

# Portrait stage matching RCARS mock canvas.
# Web/WASM: half-res canvas (CSS upscales). Full 1080x1920 fullscreen blits
# cost ~25ms/frame in pygbag and make the tab feel frozen.
SCALE = 0.5 if sys.platform == "emscripten" else 1.0
WIDTH = int(1080 * SCALE)
HEIGHT = int(1920 * SCALE)
FPS = 60
# Bumped in web deploys so cached pygbag archives are easy to spot in logs.
BUILD_ID = "7b7edde-scale"

LEADERBOARD_PATH = ROOT / "data" / "leaderboard.json"
MAX_ENTRIES = 10
TITLE = "Booth Blaster"
IDLE_QUIT_SECONDS = 90.0
EXIT_COMBO_HOLD_SECONDS = 1.25

FULLSCREEN = os.environ.get("DOBBY_GAME_FULLSCREEN", "").strip() in {"1", "true", "TRUE", "yes", "YES"}
SMOKE_SECONDS = float(os.environ.get("DOBBY_GAME_SMOKE_SECONDS", "0") or "0")


def parse_pad_button_set(raw: str, default: frozenset[int]) -> frozenset[int]:
    """Parse comma-separated button indices; empty / invalid falls back to default."""
    text = (raw or "").strip()
    if not text:
        return default
    out: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            continue
    return frozenset(out) if out else default


# Union maps cover DragonRise 0079 SNES clones + DualShock / DualSense remaps.
# Booth pad (LaserMonkeyKiosk2): fire face 0-3, Select=8, Start=9; D-pad on axes 0/1.
# Override on the Pi if a clone differs, e.g. DOBBY_PAD_FIRE=2,3
_DEFAULT_PAD_FIRE = frozenset({0, 1, 2, 3})
_DEFAULT_PAD_SELECT = frozenset({6, 8, 10})
_DEFAULT_PAD_START = frozenset({7, 9, 6})

PAD_FIRE_BUTTONS = parse_pad_button_set(os.environ.get("DOBBY_PAD_FIRE", ""), _DEFAULT_PAD_FIRE)
PAD_SELECT_BUTTONS = parse_pad_button_set(os.environ.get("DOBBY_PAD_SELECT", ""), _DEFAULT_PAD_SELECT)
PAD_START_BUTTONS = parse_pad_button_set(os.environ.get("DOBBY_PAD_START", ""), _DEFAULT_PAD_START)
