"""Generate Booth Blaster BGM + SFX as procedural arcade WAVs."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "audio"
SR = 44100


def _env(n: int, attack: float, release: float) -> np.ndarray:
    a = max(1, int(attack * SR))
    r = max(1, int(release * SR))
    env = np.ones(n, dtype=np.float64)
    env[:a] = np.linspace(0.0, 1.0, a, endpoint=False)
    if r < n:
        env[-r:] = np.linspace(1.0, 0.0, r)
    return env


def _square(freq: float, n: int, duty: float = 0.5) -> np.ndarray:
    t = np.arange(n) / SR
    return np.where((t * freq) % 1.0 < duty, 1.0, -1.0).astype(np.float64)


def _triangle(freq: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    return (2.0 * np.abs(2.0 * ((t * freq) % 1.0) - 1.0) - 1.0).astype(np.float64)


def _saw(freq: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    return (2.0 * ((t * freq) % 1.0) - 1.0).astype(np.float64)


def _sine(freq: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    return np.sin(2.0 * np.pi * freq * t)


def _noise(n: int) -> np.ndarray:
    return np.random.default_rng(42).uniform(-1.0, 1.0, n)


def _tone(
    freq: float,
    dur: float,
    wave: str = "square",
    vol: float = 0.35,
    attack: float = 0.01,
    release: float = 0.05,
    duty: float = 0.5,
) -> np.ndarray:
    n = max(1, int(dur * SR))
    if wave == "triangle":
        sig = _triangle(freq, n)
    elif wave == "saw":
        sig = _saw(freq, n)
    elif wave == "noise":
        sig = _noise(n)
    else:
        sig = _square(freq, n, duty=duty)
    return sig * _env(n, attack, release) * vol


def _slide(f0: float, f1: float, dur: float, wave: str = "square", vol: float = 0.35) -> np.ndarray:
    n = max(1, int(dur * SR))
    freqs = np.linspace(f0, f1, n)
    phase = np.cumsum(freqs / SR)
    if wave == "triangle":
        sig = 2.0 * np.abs(2.0 * (phase % 1.0) - 1.0) - 1.0
    elif wave == "saw":
        sig = 2.0 * (phase % 1.0) - 1.0
    else:
        sig = np.where((phase % 1.0) < 0.5, 1.0, -1.0)
    return sig * _env(n, 0.005, 0.04) * vol


def _mix(*parts: np.ndarray, gap: float = 0.0) -> np.ndarray:
    chunks: list[np.ndarray] = []
    silence = np.zeros(max(0, int(gap * SR)), dtype=np.float64)
    for i, p in enumerate(parts):
        chunks.append(p)
        if i < len(parts) - 1 and silence.size:
            chunks.append(silence)
    return np.concatenate(chunks) if chunks else np.zeros(1)


def _overlay(*layers: np.ndarray) -> np.ndarray:
    n = max(len(x) for x in layers)
    out = np.zeros(n, dtype=np.float64)
    for layer in layers:
        out[: len(layer)] += layer
    peak = np.max(np.abs(out)) or 1.0
    if peak > 0.95:
        out *= 0.95 / peak
    return out


def write_wav(path: Path, mono: np.ndarray) -> None:
    mono = np.asarray(mono, dtype=np.float64)
    mono = np.clip(mono, -1.0, 1.0)
    pcm = (mono * 32767.0).astype(np.int16)
    stereo = np.column_stack([pcm, pcm]).reshape(-1)
    path.parent.mkdir(parents=True, exist_ok=True)
    import wave

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(stereo.tobytes())
    print("wrote", path.relative_to(ROOT), f"{len(mono)/SR:.2f}s")


def wav_to_ogg(wav_path: Path) -> None:
    """Encode WAV → OGG Vorbis for web (Safari/WASM). Requires ffmpeg on PATH."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("skip ogg (ffmpeg not found):", wav_path.name)
        return
    ogg_path = wav_path.with_suffix(".ogg")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(wav_path),
            "-c:a",
            "libvorbis",
            "-q:a",
            "7",
            str(ogg_path),
        ],
        check=True,
        capture_output=True,
    )
    print("wrote", ogg_path.relative_to(ROOT))


# --- note helpers ---
NOTE = {
    "C3": 130.81,
    "D3": 146.83,
    "E3": 164.81,
    "F3": 174.61,
    "G3": 196.00,
    "A3": 220.00,
    "B3": 246.94,
    "C4": 261.63,
    "D4": 293.66,
    "E4": 329.63,
    "F4": 349.23,
    "G4": 392.00,
    "A4": 440.00,
    "B4": 493.88,
    "C5": 523.25,
    "D5": 587.33,
    "E5": 659.25,
    "F5": 698.46,
    "G5": 783.99,
    "A5": 880.00,
}


def _seq(notes: list[tuple[str | None, float]], wave: str = "square", vol: float = 0.28) -> np.ndarray:
    parts = []
    for name, dur in notes:
        if name is None:
            parts.append(np.zeros(max(1, int(dur * SR))))
        else:
            parts.append(_tone(NOTE[name], dur, wave=wave, vol=vol, attack=0.008, release=min(0.08, dur * 0.4)))
    return _mix(*parts)


def make_sfx() -> None:
    write_wav(OUT / "shoot.wav", _slide(880, 1480, 0.07, "square", 0.28))
    write_wav(
        OUT / "enemy_shoot.wav",
        _overlay(_slide(420, 180, 0.11, "saw", 0.22), _tone(90, 0.11, "noise", 0.08, 0.001, 0.08)),
    )
    write_wav(
        OUT / "hit.wav",
        _overlay(_tone(620, 0.05, "square", 0.22), _tone(310, 0.07, "triangle", 0.18)),
    )
    write_wav(
        OUT / "enemy_die.wav",
        _mix(
            _slide(700, 180, 0.14, "square", 0.3),
            _tone(140, 0.08, "noise", 0.15, 0.001, 0.06),
            gap=0.0,
        ),
    )
    write_wav(
        OUT / "barrier_hit.wav",
        _overlay(_tone(180, 0.06, "noise", 0.22, 0.001, 0.05), _tone(240, 0.05, "square", 0.12)),
    )
    write_wav(
        OUT / "player_hurt.wav",
        _mix(_slide(360, 90, 0.22, "saw", 0.32), _tone(70, 0.18, "noise", 0.12, 0.001, 0.12)),
    )
    write_wav(
        OUT / "game_over.wav",
        _mix(
            _tone(NOTE["E4"], 0.22, "square", 0.28),
            _tone(NOTE["C4"], 0.22, "square", 0.28),
            _tone(NOTE["A3"], 0.28, "square", 0.28),
            _tone(NOTE["E3"], 0.55, "triangle", 0.3, release=0.25),
            gap=0.04,
        ),
    )
    write_wav(
        OUT / "wave_clear.wav",
        _mix(
            _tone(NOTE["C4"], 0.1, "triangle", 0.26),
            _tone(NOTE["E4"], 0.1, "triangle", 0.26),
            _tone(NOTE["G4"], 0.1, "triangle", 0.26),
            _tone(NOTE["C5"], 0.28, "square", 0.28, release=0.15),
            gap=0.02,
        ),
    )
    write_wav(
        OUT / "boss_incoming.wav",
        _mix(
            _tone(NOTE["G3"], 0.16, "saw", 0.3),
            _tone(NOTE["G3"], 0.16, "saw", 0.3),
            _tone(NOTE["D4"], 0.16, "saw", 0.32),
            _tone(NOTE["G4"], 0.4, "square", 0.34, release=0.2),
            gap=0.05,
        ),
    )
    write_wav(
        OUT / "boss_defeat.wav",
        _mix(
            _tone(NOTE["G4"], 0.1, "square", 0.26),
            _tone(NOTE["B4"], 0.1, "square", 0.26),
            _tone(NOTE["D5"], 0.1, "square", 0.28),
            _tone(NOTE["G5"], 0.35, "triangle", 0.3, release=0.2),
            gap=0.03,
        ),
    )
    write_wav(
        OUT / "ui_confirm.wav",
        _mix(_tone(NOTE["A4"], 0.06, "triangle", 0.24), _tone(NOTE["E5"], 0.1, "triangle", 0.26), gap=0.01),
    )
    write_wav(
        OUT / "ui_blip.wav",
        _tone(NOTE["C5"], 0.04, "triangle", 0.18, attack=0.002, release=0.03),
    )
    write_wav(
        OUT / "march.wav",
        _overlay(_tone(90, 0.05, "noise", 0.1, 0.001, 0.04), _tone(140, 0.04, "square", 0.08)),
    )
    # Rising bird-cry for phoenix title easter egg (short, does not loop).
    screech = _mix(
        _overlay(
            _slide(620, 1680, 0.2, "saw", 0.34),
            _slide(900, 2100, 0.16, "square", 0.2),
            _tone(1, 0.14, "noise", 0.1, 0.001, 0.1),
        ),
        _overlay(
            _slide(1100, 2200, 0.12, "saw", 0.28),
            _tone(1, 0.08, "noise", 0.07, 0.001, 0.06),
        ),
        gap=0.035,
    )
    phoenix_path = OUT / "phoenix_screech.wav"
    write_wav(phoenix_path, screech)
    wav_to_ogg(phoenix_path)

    # Short victory fanfare for campaign clear cutscene.
    fanfare = _mix(
        _tone(NOTE["C5"], 0.12, "square", 0.28),
        _tone(NOTE["E5"], 0.12, "square", 0.28),
        _tone(NOTE["G5"], 0.12, "square", 0.3),
        _tone(NOTE["C5"], 0.1, "triangle", 0.22),
        _tone(NOTE["E5"], 0.1, "triangle", 0.22),
        _tone(NOTE["G5"], 0.1, "triangle", 0.24),
        _tone(NOTE["C5"], 0.45, "square", 0.32, release=0.28),
        gap=0.03,
    )
    fanfare = _overlay(
        fanfare,
        _mix(
            _tone(NOTE["G4"], 0.55, "triangle", 0.12, release=0.3),
            _tone(NOTE["C5"], 0.55, "triangle", 0.1, release=0.3),
            gap=0.35,
        ),
    )
    fanfare_path = OUT / "victory_fanfare.wav"
    write_wav(fanfare_path, fanfare)
    wav_to_ogg(fanfare_path)


def _loop_crossfade(mono: np.ndarray, fade_s: float = 0.12) -> np.ndarray:
    """Blend loop endpoints so pygame -1 loops do not click on mobile."""
    n = len(mono)
    fade_n = min(n // 4, max(1, int(fade_s * SR)))
    if fade_n < 8:
        return mono
    out = mono.copy()
    blend = np.linspace(0.0, 1.0, fade_n)
    start = out[:fade_n].copy()
    end = out[-fade_n:].copy()
    out[:fade_n] = start * blend + end * (1.0 - blend)
    out[-fade_n:] = end * (1.0 - blend) + start * blend
    # Soft zero endpoints after blend to kill residual clicks.
    tip = min(fade_n // 3, int(0.02 * SR))
    if tip > 1:
        out[:tip] *= np.linspace(0.0, 1.0, tip)
        out[-tip:] *= np.linspace(1.0, 0.0, tip)
    return out


def _drum_kick(dur: float = 0.12) -> np.ndarray:
    return _slide(120, 40, dur, "triangle", 0.45)


def _drum_hat(dur: float = 0.04) -> np.ndarray:
    return _tone(1, dur, "noise", 0.1, 0.001, 0.03)


def _place(total: int, hits: list[tuple[int, np.ndarray]]) -> np.ndarray:
    out = np.zeros(total, dtype=np.float64)
    for start, clip in hits:
        end = min(total, start + len(clip))
        out[start:end] += clip[: end - start]
    peak = np.max(np.abs(out)) or 1.0
    if peak > 0.95:
        out *= 0.95 / peak
    return out


def _soft_piano(freq: float, duration: float = 4.5) -> np.ndarray:
    """A mellow, quickly struck tone with a long piano-like decay."""
    n = int(duration * SR)
    t = np.arange(n) / SR
    tone = (
        np.sin(2 * np.pi * freq * t) * np.exp(-t * 1.05)
        + 0.32 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t * 1.9)
        + 0.12 * np.sin(2 * np.pi * freq * 3.01 * t) * np.exp(-t * 2.8)
    )
    attack = min(n, int(0.018 * SR))
    tone[:attack] *= np.linspace(0.0, 1.0, attack)
    return tone * 0.13


def _ambient_bed(duration: float, root: float, seed: int, active: bool = False) -> np.ndarray:
    """Peaceful, spacious ambience with an original sparse piano motif."""
    n = int(duration * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)

    # A very quiet warm pad; most of the track is intentionally open space.
    drift = 0.8 + 0.14 * np.sin(2 * np.pi * t / 17.0) + 0.06 * np.sin(2 * np.pi * t / 11.0)
    bed = (
        _sine(root, n) * 0.038
        + _sine(root * 1.5, n) * 0.018
        + _sine(root * 2.0, n) * 0.009
    ) * drift

    # Barely audible room tone keeps silence from feeling digitally empty.
    control_step = max(1, int(SR * 0.5))
    control_x = np.arange(0, n + control_step, control_step)
    control_y = rng.uniform(-1.0, 1.0, len(control_x))
    room_tone = np.interp(np.arange(n), control_x, control_y) * 0.01
    bed += room_tone

    # Original pentatonic phrases separated by generous pauses.
    note_times = (4.0, 9.5, 15.0, 23.5, 30.0, 38.5, 46.0, 54.0)
    title_notes = (329.63, 392.0, 493.88, 440.0, 293.66, 392.0, 329.63, 246.94)
    game_notes = (293.66, 440.0, 392.0, 329.63, 493.88, 392.0, 293.66, 329.63)
    notes = game_notes if active else title_notes
    for start_s, freq in zip(note_times, notes):
        start = int(start_s * SR)
        piano = _soft_piano(freq)
        length = min(len(piano), n - start)
        if length <= 0:
            continue
        bed[start : start + length] += piano[:length]

    # Crossfade the endpoints so pygame's looping transition stays unobtrusive.
    fade_n = int(3.0 * SR)
    blend = np.linspace(0.0, 1.0, fade_n)
    start_copy = bed[:fade_n].copy()
    end_copy = bed[-fade_n:].copy()
    bed[:fade_n] = start_copy * blend + end_copy * (1.0 - blend)
    bed[-fade_n:] = end_copy * (1.0 - blend) + start_copy * blend
    return np.clip(bed, -0.8, 0.8)


def make_music_title() -> None:
    write_wav(OUT / "music_title.wav", _ambient_bed(20.0, 55.0, seed=17))


def make_music_game() -> None:
    # Urgent 150 BPM chase loop — tense but leaves room for gameplay SFX.
    beat = 0.4
    ostinato = _seq(
        [
            ("E3", beat / 2),
            ("B3", beat / 2),
            ("G3", beat / 2),
            ("B3", beat / 2),
            ("E4", beat / 2),
            ("B3", beat / 2),
            ("D4", beat / 2),
            ("B3", beat / 2),
            ("C4", beat / 2),
            ("G3", beat / 2),
            ("A3", beat / 2),
            ("C4", beat / 2),
            ("B3", beat / 2),
            ("A3", beat / 2),
            ("G3", beat / 2),
            ("D4", beat / 2),
        ]
        * 4,
        wave="triangle",
        vol=0.13,
    )
    bass = _seq(
        [("E3", beat * 4), ("C3", beat * 4), ("G3", beat * 4), ("D3", beat * 4)] * 2,
        wave="square",
        vol=0.11,
    )
    n = max(len(ostinato), len(bass))
    step = int(beat * SR)
    kicks = [(i * step, _drum_kick(0.09) * 0.55) for i in range(n // step) if i % 2 == 0]
    hats = [
        (i * step + step // 2, _drum_hat(0.025) * 0.42)
        for i in range(n // step)
    ]
    drums = _place(n, kicks + hats)
    warning = _seq(
        [("E4", beat), (None, beat * 3), ("G4", beat), (None, beat * 3)] * 4,
        wave="saw",
        vol=0.045,
    )
    bed = _overlay(ostinato[:n], bass[:n], drums, warning[:n])
    write_wav(OUT / "music_game.wav", _loop_crossfade(bed, fade_s=0.14))


def make_music_boss() -> None:
    # 200 BPM boss loop: heavier pulse, tighter rhythm, more dissonance.
    beat = 0.3
    lead = _seq(
        [
            ("E3", beat),
            ("B3", beat),
            ("F3", beat),
            ("C4", beat),
            ("E3", beat),
            ("E4", beat),
            ("B3", beat),
            ("G3", beat),
            ("D4", beat),
            ("F3", beat),
            ("C4", beat),
            ("E3", beat),
            ("A3", beat),
            ("B3", beat),
            ("G3", beat),
            ("F3", beat),
        ]
        * 2,
        wave="saw",
        vol=0.19,
    )
    bass = _seq(
        [("E3", beat * 2), ("F3", beat * 2), ("D3", beat * 2), ("E3", beat * 2)] * 4,
        wave="square",
        vol=0.16,
    )
    n = max(len(lead), len(bass))
    pulse = _seq([("E4", beat / 2), (None, beat / 2)] * 32, wave="square", vol=0.07)
    step = int(beat * SR)
    kicks = [(i * step, _drum_kick(0.1) * 0.9) for i in range(n // step)]
    hats = [
        (i * step + step // 2, _drum_hat(0.035) * 0.65)
        for i in range(n // step)
    ]
    drums = _place(n, kicks + hats)
    sub = _sine(55.0, n) * (0.06 + 0.025 * np.sin(2 * np.pi * np.arange(n) / SR / beat))
    bed = _overlay(lead[:n], bass[:n], pulse[:n], drums, sub)
    write_wav(OUT / "music_boss.wav", _loop_crossfade(bed, fade_s=0.12))


def encode_music_oggs() -> None:
    """Re-encode BGM (and any missing SFX) OGGs at the configured quality."""
    for name in ("music_title.wav", "music_game.wav", "music_boss.wav", "victory_fanfare.wav"):
        path = OUT / name
        if path.is_file():
            wav_to_ogg(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_sfx()
    make_music_title()
    make_music_game()
    make_music_boss()
    encode_music_oggs()
    print("audio ready in", OUT)


if __name__ == "__main__":
    main()
