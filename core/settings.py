"""Persisted player preferences (audio, etc.)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.platform import writable_data_dir


@dataclass
class AudioSettings:
    muted: bool = False
    music_volume: float = 0.42
    sfx_volume: float = 0.55


def _path() -> Path:
    return writable_data_dir() / "audio_settings.json"


def load_audio_settings() -> AudioSettings:
    path = _path()
    if not path.is_file():
        return AudioSettings()
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
