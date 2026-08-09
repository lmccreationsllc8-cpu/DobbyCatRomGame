"""Lightweight pygame audio helper for Booth Blaster."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pygame

import config
from core.platform import is_android, is_web
from core.settings import AudioSettings, load_audio_settings, save_audio_settings

_initialized = False
_sounds: dict[str, pygame.mixer.Sound] = {}
_music_current: Optional[str] = None
_pending_music: Optional[tuple[str, bool]] = None
_music_fade_remaining = 0.0
_settings = AudioSettings()

_MUSIC_FADE_MS = 350

SFX_FILES = {
    "shoot": "shoot.wav",
    "enemy_shoot": "enemy_shoot.wav",
    "hit": "hit.wav",
    "enemy_die": "enemy_die.wav",
    "barrier_hit": "barrier_hit.wav",
    "player_hurt": "player_hurt.wav",
    "game_over": "game_over.wav",
    "wave_clear": "wave_clear.wav",
    "boss_incoming": "boss_incoming.wav",
    "boss_defeat": "boss_defeat.wav",
    "ui_confirm": "ui_confirm.wav",
    "ui_blip": "ui_blip.wav",
    "march": "march.wav",
    "phoenix_screech": "phoenix_screech.wav",
    "victory_fanfare": "victory_fanfare.wav",
}

MUSIC_FILES = {
    "title": "music_title.wav",
    "game": "music_game.wav",
    "boss": "music_boss.wav",
}


def _resolve_audio_file(filename: str) -> Optional[Path]:
    """Prefer OGG on web (Safari/WASM); fall back to the configured name."""
    audio_dir: Path = config.AUDIO_DIR
    stem = Path(filename).stem
    candidates: list[Path]
    if is_web():
        candidates = [audio_dir / f"{stem}.ogg", audio_dir / filename]
    else:
        candidates = [audio_dir / filename, audio_dir / f"{stem}.ogg"]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _ensure_mixer() -> bool:
    """Open the mixer with platform-appropriate buffer/rate.

    ``pygame.init()`` often opens the mixer with a tiny default buffer first.
    On web that causes underrun crackle, so we always re-init there.
    """
    from core.platform import mixer_buffer, mixer_frequency

    freq = mixer_frequency()
    buf = mixer_buffer()
    want_web_or_mobile = is_web() or is_android()
    try:
        current = pygame.mixer.get_init()
        if current is not None:
            cur_freq, _fmt, _ch = current
            # Buffer size is not reported by get_init(); force a clean open on
            # web/Android so we never keep pygame's default 512-sample buffer.
            if want_web_or_mobile or cur_freq != freq:
                pygame.mixer.quit()
                current = None
        if current is None:
            pygame.mixer.init(frequency=freq, size=-16, channels=2, buffer=buf)
        # Fewer concurrent voices on WASM avoids saturating the audio graph.
        pygame.mixer.set_num_channels(8 if is_web() else 16)
        return True
    except pygame.error:
        return False


def _load_sound(key: str) -> Optional[pygame.mixer.Sound]:
    """Load one SFX by key; cache on success."""
    if key in _sounds:
        return _sounds[key]
    filename = SFX_FILES.get(key)
    if not filename:
        return None
    path = _resolve_audio_file(filename)
    if path is None:
        return None
    try:
        sound = pygame.mixer.Sound(str(path))
    except pygame.error:
        return None
    _sounds[key] = sound
    try:
        head = _output_headroom()
        sfx_v = 0.0 if _settings.muted else _settings.sfx_volume * head
        sound.set_volume(sfx_v)
    except pygame.error:
        pass
    return sound


def init() -> None:
    """Initialize mixer and load available assets. Safe to call multiple times."""
    global _initialized, _settings
    if _initialized:
        return
    _settings = load_audio_settings()
    if not _ensure_mixer():
        _initialized = True
        return

    # Desktop/Android: preload. Web: lazy-load on first play — decoding every
    # OGG up front stalls the single-threaded WASM loop for seconds.
    if not is_web():
        for key in SFX_FILES:
            _load_sound(key)
    _initialized = True
    _apply_volumes()


def get_settings() -> AudioSettings:
    return AudioSettings(
        muted=_settings.muted,
        music_volume=_settings.music_volume,
        sfx_volume=_settings.sfx_volume,
    )


def is_muted() -> bool:
    return _settings.muted


def _output_headroom() -> float:
    """Leave mix headroom on web — WASM clip/distortion is harsher than desktop."""
    return 0.72 if is_web() else 1.0


def _apply_volumes() -> None:
    head = _output_headroom()
    music_v = 0.0 if _settings.muted else _settings.music_volume * head
    sfx_v = 0.0 if _settings.muted else _settings.sfx_volume * head
    try:
        pygame.mixer.music.set_volume(music_v)
    except pygame.error:
        pass
    for sound in _sounds.values():
        try:
            sound.set_volume(sfx_v)
        except pygame.error:
            pass


def _persist() -> None:
    save_audio_settings(_settings)
    _apply_volumes()


def set_muted(muted: bool) -> None:
    global _music_current
    _settings.muted = bool(muted)
    _persist()
    if _settings.muted:
        try:
            pygame.mixer.music.set_volume(0.0)
            pygame.mixer.music.pause()
        except pygame.error:
            pass
    else:
        # Resume or restart last track if paused/stopped.
        try:
            pygame.mixer.music.set_volume(_settings.music_volume * _output_headroom())
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.unpause()
            elif _music_current:
                name = _music_current
                _music_current = None
                play_music(name)
            else:
                pygame.mixer.music.unpause()
        except pygame.error:
            pass


def toggle_mute() -> bool:
    set_muted(not _settings.muted)
    return _settings.muted


def set_music_volume(volume: float) -> None:
    _settings.music_volume = round(max(0.0, min(1.0, float(volume))), 2)
    _persist()


def set_sfx_volume(volume: float) -> None:
    _settings.sfx_volume = round(max(0.0, min(1.0, float(volume))), 2)
    _persist()


def nudge_music_volume(delta: float) -> float:
    set_music_volume(_settings.music_volume + delta)
    return _settings.music_volume


def nudge_sfx_volume(delta: float) -> float:
    set_sfx_volume(_settings.sfx_volume + delta)
    return _settings.sfx_volume


def play(name: str, volume: Optional[float] = None) -> None:
    if _settings.muted or not _initialized:
        return
    sound = _load_sound(name)
    if sound is None:
        return
    try:
        channel = sound.play()
        if channel is not None and volume is not None:
            base = _settings.sfx_volume * _output_headroom()
            channel.set_volume(max(0.0, min(1.0, base * volume)))
    except pygame.error:
        pass


def _start_music(name: str, loop: bool) -> None:
    """Load and play a music key immediately."""
    global _music_current
    filename = MUSIC_FILES.get(name)
    if not filename:
        return
    path = _resolve_audio_file(filename)
    if path is None:
        return
    try:
        pygame.mixer.music.load(str(path))
        music_v = 0.0 if _settings.muted else _settings.music_volume * _output_headroom()
        pygame.mixer.music.set_volume(music_v)
        pygame.mixer.music.play(-1 if loop else 0)
        _music_current = name
        if _settings.muted:
            pygame.mixer.music.pause()
    except pygame.error:
        pass


def play_music(name: str, loop: bool = True) -> None:
    """Start looping background music by key (title/game/boss)."""
    global _music_current, _pending_music, _music_fade_remaining
    if not _initialized:
        return
    if name not in MUSIC_FILES:
        return
    if _music_current == name and _pending_music is None and pygame.mixer.music.get_busy():
        _apply_volumes()
        return
    # Soft-cut on mobile/web to avoid crackle from hard load() swaps.
    soft = is_web() or is_android()
    busy = False
    try:
        busy = bool(pygame.mixer.music.get_busy())
    except pygame.error:
        busy = False
    if soft and busy and _music_current and _music_current != name:
        try:
            pygame.mixer.music.fadeout(_MUSIC_FADE_MS)
        except pygame.error:
            pass
        _pending_music = (name, loop)
        _music_fade_remaining = _MUSIC_FADE_MS / 1000.0
        _music_current = name
        return
    _pending_music = None
    _music_fade_remaining = 0.0
    _start_music(name, loop)


def tick(dt: float) -> None:
    """Advance deferred music swaps after a mobile/web fade-out."""
    global _pending_music, _music_fade_remaining
    if _pending_music is None:
        return
    _music_fade_remaining -= max(0.0, dt)
    busy = False
    try:
        busy = bool(pygame.mixer.music.get_busy())
    except pygame.error:
        busy = False
    if _music_fade_remaining > 0.0 and busy:
        return
    name, loop = _pending_music
    _pending_music = None
    _music_fade_remaining = 0.0
    _start_music(name, loop)


def stop_music(fade_ms: int = 400) -> None:
    global _music_current, _pending_music, _music_fade_remaining
    if not _initialized:
        return
    _pending_music = None
    _music_fade_remaining = 0.0
    try:
        if fade_ms > 0:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()
    except pygame.error:
        pass
    _music_current = None


def shutdown() -> None:
    global _initialized, _music_current, _pending_music, _music_fade_remaining
    if not _initialized:
        return
    try:
        pygame.mixer.music.stop()
        pygame.mixer.quit()
    except pygame.error:
        pass
    _sounds.clear()
    _music_current = None
    _pending_music = None
    _music_fade_remaining = 0.0
    _initialized = False
