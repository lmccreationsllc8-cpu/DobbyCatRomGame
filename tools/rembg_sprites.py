"""Cut sprites with rembg from cursor gens. Mild alpha harden only."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from rembg import remove

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
CURSOR = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")
PREVIEW = ROOT / "assets" / "reference" / "alpha_preview"
GOOD_DINO = CURSOR / (
    "c__Users_Dad_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_"
    "image-d89fc05b-d556-4aee-8e02-3cbb899fc06b.png"
)

NAMES = [
    ("player_dobby_bee.png", 512),
    ("player_dobby_cape.png", 512),
    ("player_dobby_cute.png", 512),
    ("player_dobby_dino.png", 512),
    ("player_dobby_hi_vis.png", 512),
    ("player_dobby_hoodie_green.png", 512),
    ("player_dobby_octopus.png", 512),
    ("player_dobby_pickle.png", 512),
    ("enemy_boss_nana.png", 640),
    ("enemy_boss_parent_a.png", 640),
    ("enemy_boss_parent_b.png", 640),
]


def center_square(im: Image.Image, size: int) -> Image.Image:
    im = im.convert("RGBA")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    pad = 16
    side = max(im.size) + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2), im)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def mild_harden(im: Image.Image) -> Image.Image:
    arr = np.asarray(im).copy()
    a = arr[:, :, 3]
    arr[:, :, 3] = np.where(a < 60, 0, np.where(a > 180, 255, a)).astype(np.uint8)
    # drop chroma green/magenta leftovers only
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mag = (arr[:, :, 3] > 8) & (r >= 190) & (b >= 190) & (g <= 120)
    gre = (arr[:, :, 3] > 8) & (g >= 200) & (g > r + 50) & (g > b + 50)
    arr[mag | gre, 3] = 0
    return Image.fromarray(arr, "RGBA")


def main() -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for name, size in NAMES:
        if name == "player_dobby_dino.png" and GOOD_DINO.is_file():
            src = GOOD_DINO
        else:
            src = CURSOR / name
        if not src.is_file():
            print("MISSING", name)
            continue
        cut = mild_harden(remove(Image.open(src).convert("RGBA")))
        out = center_square(cut, size)
        out.save(SPRITES / name)
        bg = Image.new("RGB", out.size, (180, 200, 220))
        bg.paste(out, mask=out.split()[-1])
        bg.save(PREVIEW / f"light_{name}")
        print("ok", name)


if __name__ == "__main__":
    main()
