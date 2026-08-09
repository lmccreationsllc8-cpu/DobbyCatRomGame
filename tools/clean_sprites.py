"""Knock out generated studio plates and export crisp RGBA sprites.

Uses edge-connected plate / magenta chroma — never blanket-deletes luma>=230 whites.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
SRC_DIR = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")

# Import shared safe alpha helpers
sys.path.insert(0, str(ROOT / "tools"))
from sprite_alpha import luma, process_sprite  # noqa: E402


def clean_bg(im: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    px = im.load()
    w, h = im.size
    for x in range(w):
        bright_col = 0
        for y in range(0, h, 6):
            r, g, b = px[x, y]
            if luma(r, g, b) > 215 and (max(r, g, b) - min(r, g, b)) < 40:
                bright_col += 1
        if bright_col > h // 50:
            for y in range(h):
                left = px[max(0, x - 3), y]
                right = px[min(w - 1, x + 3), y]
                px[x, y] = tuple((left[i] * 2 + right[i] * 2) // 4 for i in range(3))

    soft = im.filter(ImageFilter.MedianFilter(size=3))
    return Image.blend(im, soft, 0.25)


def process_path(path: Path) -> None:
    im = Image.open(path)
    if path.name.startswith("bg_"):
        out = clean_bg(im)
        out = out.resize((540, 960), Image.Resampling.LANCZOS)
        out.save(path, optimize=True)
        print(f"bg cleaned {path.name} -> {out.size} {out.mode}")
        return

    # Boss identity lock: skip destructive re-clean of Scooter Dog
    if path.name == "enemy_boss.png":
        print(f"skip boss identity lock {path.name}")
        return

    size = 128 if path.name.startswith("paw_") else 256
    canvas = process_sprite(im, size=size)
    canvas.save(path, optimize=True)
    alpha = canvas.split()[-1]
    clear = sum(1 for v in alpha.getdata() if v == 0)
    print(f"sprite {path.name} -> {canvas.size} RGBA clear={clear}/{size * size}")


def main() -> int:
    preferred = (
        "bg_booth.png",
        "player_dobby.png",
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
        # enemy_boss intentionally omitted from master overwrite (identity lock)
        "barrier_crate.png",
        "barrier_crate_d1.png",
        "barrier_crate_d2.png",
        "fx_phoenix.png",
        "paw_bolt.png",
        "paw_enemy.png",
        "bolt.png",
    )
    for name in preferred:
        src = SRC_DIR / name
        # Prefer *_gen.png masters when present (glowstick/mecha/pillow)
        alt = SRC_DIR / name.replace(".png", "_gen.png")
        pick = alt if alt.is_file() else src
        if pick.is_file() and name != "enemy_boss.png":
            (SPRITES / name).write_bytes(pick.read_bytes())

    names = sorted(SPRITES.glob("*.png"))
    if not names:
        print("No sprites found", file=sys.stderr)
        return 1
    for path in names:
        process_path(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
