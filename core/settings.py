"""Persisted player preferences (audio, etc.)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from core import storage

_STORE_NAME = "audio_settings.json"


@dataclass
class AudioSettings:
    muted: bool = False
    music_volume: float = 0.42
    sfx_volume: float = 0.55


def load_audio_settings() -> AudioSettings:
    text = storage.read_text(_STORE_NAME)
    if not text:
        return AudioSettings()
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError:
        return AudioSettings()
    if not isinstance(raw, dict):
        return AudioSettings()
    try:
        music = float(raw.get("music_volume", 0.42))
        sfx = float(raw.get("sfx_volume", 0.55))
        muted = bool(raw.get("muted", False))
    except (TypeError, ValueError):
        return AudioSettings()
    return AudioSettings(
        muted=muted,
        music_volume=max(0.0, min(1.0, music)),
        sfx_volume=max(0.0, min(1.0, sfx)),
    )


def save_audio_settings(settings: AudioSettings) -> None:
    storage.write_text(_STORE_NAME, json.dumps(asdict(settings), indent=2))
