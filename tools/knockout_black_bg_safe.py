"""Safe black-bg knockout: trim outer plate, keep dark clothing.

1) Seed non-plate content
2) Morphological CLOSE (equal dilate/erode) so black clothes fill without
   growing a black halo
3) Clear near-black only outside that protect mask
4) Edge-flood remaining plate from the border (cannot enter protect)
5) Strip thin black fringe crumbs touching clear
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
CURSOR = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")
PREVIEW = ROOT / "assets" / "reference" / "alpha_preview"

NAMES = [
    "player_dobby_bee.png",
    "player_dobby_cape.png",
    "player_dobby_cute.png",
    "player_dobby_dino.png",
    "player_dobby_hi_vis.png",
    "player_dobby_hoodie_green.png",
    "player_dobby_octopus.png",
    "player_dobby_pickle.png",
    "player_dobby_thriller.png",
    "enemy_boss_nana.png",
    "enemy_boss_parent_a.png",
    "enemy_boss_parent_b.png",
]


def process_to_square_black(im: Image.Image, size: int) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            if r < 20 and g < 20 and b < 20:
                px[x, y] = (0, 0, 0, 0)
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    pad = 24
    side = max(im.size) + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2), im)
    black = Image.new("RGBA", (side, side), (0, 0, 0, 255))
    black.paste(canvas, (0, 0), canvas)
    return black.resize((size, size), Image.Resampling.LANCZOS)


def _morph_close(mask_bool: np.ndarray, radius: int) -> np.ndarray:
    img = Image.fromarray((mask_bool.astype(np.uint8) * 255))
    for _ in range(radius):
        img = img.filter(ImageFilter.MaxFilter(3))
    for _ in range(radius):
        img = img.filter(ImageFilter.MinFilter(3))
    return np.asarray(img) > 127


def _morph_dilate(mask_bool: np.ndarray, radius: int) -> np.ndarray:
    img = Image.fromarray((mask_bool.astype(np.uint8) * 255))
    for _ in range(radius):
        img = img.filter(ImageFilter.MaxFilter(3))
    return np.asarray(img) > 127


def knockout_black_safe(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    arr = np.asarray(im).copy()
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)
    lu = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    sat = rgb.max(axis=2) - rgb.min(axis=2)

    plate = (lu <= 20) & (sat <= 24)
    seed = (lu > 22) | (sat > 28)
    # Pull in black outline / adjacent dark clothing (1–2px) before close.
    seed = seed | (plate & _morph_dilate(seed, 2))
    # Equal close: fill interior black clothes without net halo growth.
    protect = _morph_close(seed, 14)

    clear = plate & (~protect)

    # Edge-flood any leftover plate from the border; never enter protect.
    visited = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if plate[y, x] and not protect[y, x]:
                visited[y, x] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if plate[y, x] and not protect[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                if plate[ny, nx] and not protect[ny, nx]:
                    visited[ny, nx] = True
                    q.append((nx, ny))
    clear |= visited

    arr[clear, 3] = 0
    arr[clear, 0:3] = 0

    # Strip thin black fringe: plate-ish opaque pixels with many clear neighbors.
    alpha = arr[:, :, 3].copy()
    for _ in range(2):
        clear_n = np.zeros((h, w), dtype=np.uint8)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                rolled = np.roll(np.roll(alpha < 8, dy, 0), dx, 1)
                clear_n += rolled.astype(np.uint8)
        fringe = (alpha > 200) & plate & (clear_n >= 3) & (~protect)
        # Also allow fringe cleanup on protect border if clearly plate crumbs
        border_fringe = (alpha > 200) & plate & (clear_n >= 5)
        kill = fringe | border_fringe
        alpha[kill] = 0
        arr[kill, 0:3] = 0
    alpha = np.where(alpha < 40, 0, np.where(alpha > 210, 255, alpha)).astype(np.uint8)
    arr[:, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


def main() -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        src = CURSOR / name
        if not src.is_file():
            print("MISSING", name)
            continue
        size = 512 if name.startswith("player_") else 640
        base = process_to_square_black(Image.open(src), size)
        out = knockout_black_safe(base)
        out.save(SPRITES / name)
        prev = Image.new("RGBA", out.size, (255, 0, 255, 255))
        prev.paste(out, (0, 0), out)
        prev.convert("RGB").save(PREVIEW / f"preview_{name}")
        a = np.asarray(out)
        rgb = a[:, :, :3].astype(np.int16)
        lu = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
        sat = rgb.max(2) - rgb.min(2)
        alpha = a[:, :, 3]
        clear = alpha < 8
        near_clear = np.zeros_like(clear)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                near_clear |= np.roll(np.roll(clear, dy, 0), dx, 1)
        halo = (alpha > 200) & (lu <= 20) & (sat <= 25) & near_clear
        print(f"{name}: clear={clear.mean():.1%} black_edge_halo={int(halo.sum())}")


if __name__ == "__main__":
    main()
