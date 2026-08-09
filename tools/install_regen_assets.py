"""Install regenerated bg + player with safe edge/magenta knockout."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")
SPRITES = ROOT / "assets" / "sprites"

sys.path.insert(0, str(ROOT / "tools"))
from sprite_alpha import process_sprite  # noqa: E402


def main() -> None:
    bg_src = SRC / "bg_booth.png"
    pl_src = SRC / "player_dobby.png"
    bg_dst = SPRITES / "bg_booth.png"
    pl_dst = SPRITES / "player_dobby.png"

    if bg_src.is_file():
        bg = Image.open(bg_src).convert("RGB").resize((540, 960), Image.Resampling.LANCZOS)
        bg.save(bg_dst, optimize=True)
        print("bg installed", bg.size)

    if pl_src.is_file():
        canvas = process_sprite(Image.open(pl_src), size=256)
        canvas.save(pl_dst)
        a = list(canvas.getchannel("A").getdata())
        print(
            f"player installed {canvas.size} clear={sum(1 for v in a if v == 0)} "
            f"opaque={sum(1 for v in a if v == 255)}"
        )


if __name__ == "__main__":
    main()
