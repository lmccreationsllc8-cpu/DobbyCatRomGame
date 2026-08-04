"""Generate Booth Blaster BGM + SFX as procedural arcade WAVs."""

from __future__ import annotations

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


def make_music_title() -> None:
    # Soft looping booth lobby vibe — ~8s
    beat = 0.28
    melody = _seq(
        [
            ("E4", beat),
            ("G4", beat),
            ("A4", beat),
            ("B4", beat),
            ("A4", beat),
            ("G4", beat),
            ("E4", beat),
            (None, beat * 0.5),
            ("D4", beat),
            ("E4", beat),
            ("G4", beat),
            ("A4", beat * 1.5),
            ("G4", beat),
            ("E4", beat),
            ("D4", beat),
            ("E4", beat * 2),
        ],
        wave="triangle",
        vol=0.22,
    )
    bass = _seq(
        [
            ("E3", beat * 2),
            ("A3", beat * 2),
            ("G3", beat * 2),
            ("B3", beat * 2),
            ("E3", beat * 2),
            ("A3", beat * 2),
            ("D3", beat * 2),
            ("E3", beat * 2),
        ],
        wave="square",
        vol=0.14,
    )
    n = max(len(melody), len(bass))
    pads = np.zeros(n)
    for i, f in enumerate([NOTE["E3"], NOTE["B3"], NOTE["E4"]]):
        tone = _tone(f, n / SR, "triangle", 0.04 + 0.01 * i, 0.2, 0.4)
        pads[: len(tone)] += tone[:n]
    write_wav(OUT / "music_title.wav", _overlay(melody, bass[:n], pads))


def make_music_game() -> None:
    # Upbeat invader march — ~8 bars looping
    beat = 0.22
    lead = _seq(
        [
            ("C4", beat),
            ("E4", beat),
            ("G4", beat),
            ("C5", beat),
            ("B4", beat),
            ("G4", beat),
            ("E4", beat),
            ("C4", beat),
            ("D4", beat),
            ("F4", beat),
            ("A4", beat),
            ("D5", beat),
            ("C5", beat),
            ("A4", beat),
            ("F4", beat),
            ("D4", beat),
            ("E4", beat),
            ("G4", beat),
            ("B4", beat),
            ("E5", beat),
            ("D5", beat),
            ("B4", beat),
            ("G4", beat),
            ("E4", beat),
            ("F4", beat),
            ("A4", beat),
            ("C5", beat),
            ("F5", beat * 0.75),
            ("E5", beat * 0.75),
            ("C5", beat),
            ("A4", beat),
            ("G4", beat * 1.5),
        ],
        wave="square",
        vol=0.2,
    )
    bass = _seq(
        [
            ("C3", beat * 2),
            ("C3", beat * 2),
            ("D3", beat * 2),
            ("D3", beat * 2),
            ("E3", beat * 2),
            ("E3", beat * 2),
            ("F3", beat * 2),
            ("G3", beat * 2),
        ]
        * 2,
        wave="triangle",
        vol=0.16,
    )
    n = max(len(lead), len(bass))
    hat_hits: list[tuple[int, np.ndarray]] = []
    kick_hits: list[tuple[int, np.ndarray]] = []
    step = int(beat * SR)
    for i in range(n // step):
        if i % 2 == 0:
            kick_hits.append((i * step, _drum_kick(0.1)))
        hat_hits.append((i * step + step // 2, _drum_hat(0.035)))
    drums = _place(n, kick_hits + hat_hits)
    arp = _seq(
        [("G4", beat / 2), ("C5", beat / 2), ("E5", beat / 2), ("G5", beat / 2)] * 16,
        wave="triangle",
        vol=0.07,
    )
    write_wav(OUT / "music_game.wav", _overlay(lead[:n], bass[:n], drums, arp[:n]))


def make_music_boss() -> None:
    beat = 0.2
    lead = _seq(
        [
            ("E3", beat),
            ("E3", beat),
            ("B3", beat),
            ("E4", beat),
            ("D4", beat),
            ("B3", beat),
            ("A3", beat),
            ("G3", beat),
            ("E3", beat),
            ("E3", beat),
            ("A3", beat),
            ("B3", beat),
            ("C4", beat),
            ("B3", beat),
            ("A3", beat),
            ("G3", beat),
        ]
        * 2,
        wave="saw",
        vol=0.22,
    )
    bass = _seq(
        [("E3", beat * 2), ("B3", beat * 2), ("A3", beat * 2), ("G3", beat * 2)] * 4,
        wave="square",
        vol=0.18,
    )
    n = max(len(lead), len(bass))
    pulse = _seq([("E4", beat / 2), (None, beat / 2)] * 32, wave="square", vol=0.08)
    write_wav(OUT / "music_boss.wav", _overlay(lead[:n], bass[:n], pulse[:n]))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_sfx()
    make_music_title()
    make_music_game()
    make_music_boss()
    print("audio ready in", OUT)


if __name__ == "__main__":
    main()
