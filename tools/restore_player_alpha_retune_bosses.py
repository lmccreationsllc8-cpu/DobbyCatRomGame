"""Restore player sprite alpha to the good content-mask pass; retune bosses only."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
CURSOR = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")
PREVIEW = ROOT / "assets" / "reference" / "alpha_preview"

PLAYERS = [
    "player_dobby_bee.png",
    "player_dobby_cape.png",
    "player_dobby_cute.png",
    "player_dobby_dino.png",
    "player_dobby_hi_vis.png",
    "player_dobby_hoodie_green.png",
    "player_dobby_octopus.png",
    "player_dobby_pickle.png",
]

BOSSES = [
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


def _morph(mask: np.ndarray, dilate: int, erode: int) -> np.ndarray:
    img = Image.fromarray((mask.astype(np.uint8) * 255))
    for _ in range(dilate):
        img = img.filter(ImageFilter.MaxFilter(3))
    for _ in range(erode):
        img = img.filter(ImageFilter.MinFilter(3))
    return np.asarray(img) > 127


def knockout_player_good(im: Image.Image) -> Image.Image:
    """Last good player pass: content mask dilate18/erode10, clear plate outside."""
    im = im.convert("RGBA")
    arr = np.asarray(im).copy()
    rgb = arr[:, :, :3].astype(np.int16)
    lu = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    content = (lu > 22) | (sat > 28)
    protect = _morph(content, dilate=18, erode=10)
    plate = (lu <= 18) & (sat <= 22)
    clear = plate & (~protect)
    arr[clear, 3] = 0
    arr[clear, 0:3] = 0
    alpha = arr[:, :, 3]
    alpha = np.where(alpha < 32, 0, np.where(alpha > 220, 255, alpha)).astype(np.uint8)
    arr[:, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


def knockout_boss_retune(im: Image.Image) -> Image.Image:
    """Boss trim: grow protect into black clothes from content, limited distance.

    Morphological close was filling arm/leg negative space. Instead, grow a
    limited band from non-plate content into adjacent plate (keeps shirts/boots),
    then edge-flood-clear remaining plate (opens crotch/arm gaps + outer bg).
    """
    im = im.convert("RGBA")
    arr = np.asarray(im).copy()
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)
    lu = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    sat = rgb.max(axis=2) - rgb.min(axis=2)

    plate = (lu <= 20) & (sat <= 24)
    content = (lu > 22) | (sat > 28)

    # Distance-limited grow into plate from content (covers black clothes/outline).
    protect = content.copy()
    frontier = list(zip(*np.where(content)))
    # store as (y,x)
    q: deque[tuple[int, int, int]] = deque((int(y), int(x), 0) for y, x in frontier)
    seen = content.copy()
    max_grow = 14
    while q:
        y, x, d = q.popleft()
        if d >= max_grow:
            continue
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and plate[ny, nx]:
                seen[ny, nx] = True
                protect[ny, nx] = True
                q.append((ny, nx, d + 1))

    # Edge-flood plate outside protect — clears bg + negative spaces.
    visited = np.zeros((h, w), dtype=bool)
    fq: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if plate[y, x] and not protect[y, x]:
                visited[y, x] = True
                fq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if plate[y, x] and not protect[y, x] and not visited[y, x]:
                visited[y, x] = True
                fq.append((x, y))
    while fq:
        x, y = fq.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                if plate[ny, nx] and not protect[ny, nx]:
                    visited[ny, nx] = True
                    fq.append((nx, ny))

    clear = visited | (plate & (~protect))
    arr[clear, 3] = 0
    arr[clear, 0:3] = 0

    # Thin outer black fringe cleanup (do not require ~protect — outline crumbs).
    alpha = arr[:, :, 3].copy()
    for _ in range(2):
        clear_n = np.zeros((h, w), dtype=np.uint8)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                clear_n += np.roll(np.roll(alpha < 8, dy, 0), dx, 1).astype(np.uint8)
        kill = (alpha > 200) & plate & (clear_n >= 4)
        # Keep pixels that still look interior (many opaque neighbors).
        opaque_n = np.zeros((h, w), dtype=np.uint8)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                opaque_n += np.roll(np.roll(alpha > 200, dy, 0), dx, 1).astype(np.uint8)
        kill &= opaque_n <= 5
        alpha[kill] = 0
        arr[kill, 0:3] = 0
    alpha = np.where(alpha < 40, 0, np.where(alpha > 210, 255, alpha)).astype(np.uint8)
    arr[:, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


def _preview(name: str, im: Image.Image) -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    prev = Image.new("RGBA", im.size, (255, 0, 255, 255))
    prev.paste(im, (0, 0), im)
    prev.convert("RGB").save(PREVIEW / f"preview_{name}")


def _stats(name: str, im: Image.Image) -> None:
    a = np.asarray(im)
    rgb = a[:, :, :3].astype(np.int16)
    lu = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    sat = rgb.max(2) - rgb.min(2)
    alpha = a[:, :, 3]
    clear = alpha < 8
    near = np.zeros_like(clear)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            near |= np.roll(np.roll(clear, dy, 0), dx, 1)
    halo = (alpha > 200) & (lu <= 20) & (sat <= 25) & near
    print(f"{name}: clear={clear.mean():.1%} black_edge_halo={int(halo.sum())}")


def main() -> None:
    print("=== restore players (good content-mask) ===")
    for name in PLAYERS:
        src = CURSOR / name
        if not src.is_file():
            print("MISSING", name)
            continue
        out = knockout_player_good(process_to_square_black(Image.open(src), 512))
        out.save(SPRITES / name)
        _preview(name, out)
        _stats(name, out)

    print("=== retune bosses only ===")
    for name in BOSSES:
        src = CURSOR / name
        if not src.is_file():
            print("MISSING", name)
            continue
        out = knockout_boss_retune(process_to_square_black(Image.open(src), 640))
        out.save(SPRITES / name)
        _preview(name, out)
        _stats(name, out)


if __name__ == "__main__":
    main()
