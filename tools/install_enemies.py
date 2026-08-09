"""Install enemy roster sprites with safe transparency knockout.

Edge-connected plate / magenta chroma — preserves interior white/cream fills.
Does not overwrite enemy_boss.png (Scooter Dog identity lock).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")
SPRITES = ROOT / "assets" / "sprites"

sys.path.insert(0, str(ROOT / "tools"))
from sprite_alpha import process_sprite  # noqa: E402

NAMES = (
    "enemy_box.png",
    "enemy_ziptie.png",
    "enemy_teen.png",
    "enemy_adult.png",
    "enemy_linecutter.png",
    "enemy_selfie.png",
    "enemy_glowstick.png",
    "enemy_maid_pink.png",
    "enemy_maid_cyan.png",
    "enemy_maid_lime.png",
    "enemy_mecha.png",
    "enemy_pillow.png",
    # enemy_boss.png — identity lock; install via restore_boss_whites / manual only
)

EXTRA = (
    "paw_bolt.png",
    "paw_enemy.png",
    "player_dobby.png",
)


def resolve_src(name: str) -> Path | None:
    stem = name.replace(".png", "")
    for candidate in (
        SRC / f"{stem}_gen_magenta2.png",
        SRC / f"{stem}_gen_magenta.png",
        SRC / f"{stem}_gen.png",
        SRC / name,
    ):
        if candidate.is_file():
            return candidate
    return None


def install(name: str) -> None:
    if name == "enemy_boss.png":
        print("skip boss identity lock", name)
        return
    src = resolve_src(name)
    if src is None:
        print("missing", name)
        return
    size = 128 if name.startswith("paw_") else 256
    out = process_sprite(Image.open(src), size=size)
    out.save(SPRITES / name)
    a = list(out.getchannel("A").getdata())
    print(
        f"ok {name} from {src.name} clear={sum(1 for v in a if v == 0)} "
        f"opaque={sum(1 for v in a if v == 255)}"
    )


def main() -> None:
    for name in NAMES + EXTRA:
        install(name)


if __name__ == "__main__":
    main()
