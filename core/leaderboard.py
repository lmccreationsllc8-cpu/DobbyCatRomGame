"""Local high-score leaderboard (JSON on disk or browser localStorage).

DBY is always first place at the hard-coded perfect campaign score.
Only human scores are persisted.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from config import MAX_ENTRIES
from core import storage

DBY_NAME = "DBY"
# Hard-coded vanity top score — always first on the board.
DBY_SCORE = 99999
DBY_WAVE = 4
RESERVED_NAMES = frozenset({DBY_NAME})
_STORE_NAME = "leaderboard.json"


@dataclass
class ScoreEntry:
    name: str
    score: int
    wave: int


def _parse_entries(raw: Any) -> list[ScoreEntry]:
    entries: list[ScoreEntry] = []
    if not isinstance(raw, list):
        return entries
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            name = str(item.get("name", "???")).upper()[:3]
            score = int(item.get("score", 0))
            wave = int(item.get("wave", 1))
        except (TypeError, ValueError):
            continue
        if name in RESERVED_NAMES:
            continue
        entries.append(ScoreEntry(name=name, score=score, wave=max(1, wave)))
    entries.sort(key=lambda e: (-e.score, -e.wave))
    return entries


def _load_real_scores() -> list[ScoreEntry]:
    text = storage.read_text(_STORE_NAME)
    if not text:
        return []
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError:
        return []
    return _parse_entries(raw)


def _with_dby(real: list[ScoreEntry]) -> list[ScoreEntry]:
    dby = ScoreEntry(name=DBY_NAME, score=DBY_SCORE, wave=DBY_WAVE)
    return [dby] + real[: max(0, MAX_ENTRIES - 1)]


def load_scores() -> list[ScoreEntry]:
    return _with_dby(_load_real_scores())


def save_scores(entries: list[ScoreEntry]) -> None:
    """Persist human scores only (DBY is synthetic)."""
    real = [e for e in entries if e.name not in RESERVED_NAMES]
    real.sort(key=lambda e: (-e.score, -e.wave))
    real = real[: max(0, MAX_ENTRIES - 1)]
    payload = [asdict(e) for e in real]
    storage.write_text(_STORE_NAME, json.dumps(payload, indent=2))


def qualifies(score: int) -> bool:
    if score <= 0:
        return False
    real = _load_real_scores()
    slots = max(0, MAX_ENTRIES - 1)
    if len(real) < slots:
        return True
    return score > real[-1].score


def submit(name: str, score: int, wave: int) -> list[ScoreEntry]:
    clean = "".join(ch for ch in name.upper() if ch.isalnum())[:3].ljust(3, "X")
    if clean in RESERVED_NAMES:
        clean = "DOB"
    real = _load_real_scores()
    real.append(ScoreEntry(name=clean, score=int(score), wave=int(wave)))
    real.sort(key=lambda e: (-e.score, -e.wave))
    real = real[: max(0, MAX_ENTRIES - 1)]
    save_scores(real)
    return _with_dby(real)


def is_high_score(score: int, entries: list[ScoreEntry] | None = None) -> bool:
    """True if this beats every human score (DBY still stays #1 on the board)."""
    real = _load_real_scores()
    if score <= 0:
        return False
    if not real:
        return True
    return score >= real[0].score
