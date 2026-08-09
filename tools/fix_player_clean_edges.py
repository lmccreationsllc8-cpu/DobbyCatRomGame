"""Restore player costume sprites to clean soft edges (no thick black halo).

- dino: install from user-attached good cut (light-bg knockout)
- others: re-key cursor black-bg gens with short distance-grow protect
  (NOT dilate18/erode10 which left ugly black plate borders)
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
CURSOR = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")
PREVIEW = ROOT / "assets" / "reference" / "alpha_preview"
GOOD_DINO = CURSOR / (
    "c__Users_Dad_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_"
    "image-d89fc05b-d556-4aee-8e02-3cbb899fc06b.png"
)

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
    black_edge = (alpha > 200) & near & (lu <= 25) & (sat <= 30)
    print(f"{name}: clear={clear.mean():.1%} black_edge={int(black_edge.sum())}")


def _preview(name: str, im: Image.Image) -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    prev = Image.new("RGBA", im.size, (255, 0, 255, 255))
    prev.paste(im, (0, 0), im)
    prev.convert("RGB").save(PREVIEW / f"preview_{name}")


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


def knockout_light_plate(im: Image.Image) -> Image.Image:
    """Edge-flood remove light studio plate (for attached good dino)."""
    im = im.convert("RGBA")
    arr = np.asarray(im).copy()
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)
    lu = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    sat = rgb.max(2) - rgb.min(2)
    plate = (lu >= 235) & (sat <= 18)

    visited = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if plate[y, x]:
                visited[y, x] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if plate[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx] and plate[ny, nx]:
                visited[ny, nx] = True
                q.append((nx, ny))
    arr[visited, 3] = 0
    arr[visited, 0:3] = 0
    # light fringe
    alpha = arr[:, :, 3].copy()
    for _ in range(2):
        clear_n = np.zeros((h, w), dtype=np.uint8)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                clear_n += np.roll(np.roll(alpha < 8, dy, 0), dx, 1).astype(np.uint8)
        kill = (alpha > 200) & (lu >= 230) & (sat <= 20) & (clear_n >= 3)
        alpha[kill] = 0
        arr[kill, 0:3] = 0
    arr[:, :, 3] = np.where(alpha < 40, 0, np.where(alpha > 210, 255, alpha)).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def process_black_square(im: Image.Image, size: int) -> Image.Image:
    """Center raw gen on opaque black square (pre-knockout)."""
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
    pad = 16
    side = max(im.size) + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2), im)
    black = Image.new("RGBA", (side, side), (0, 0, 0, 255))
    black.paste(canvas, (0, 0), canvas)
    return black.resize((size, size), Image.Resampling.LANCZOS)


def knockout_black_clean(im: Image.Image, max_grow: int = 5) -> Image.Image:
    """Clean black-bg knockout: short grow into costume blacks, no fat halo.

    Matches soft dithered edges like player_dobby_ugly — not dilate18 protect.
    """
    im = im.convert("RGBA")
    arr = np.asarray(im).copy()
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)
    lu = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    sat = rgb.max(2) - rgb.min(2)

    # Slightly stricter plate so dark brown fur outline is not treated as bg.
    plate = (lu <= 16) & (sat <= 20)
    content = (lu > 20) | (sat > 26)

    protect = content.copy()
    seen = content.copy()
    q: deque[tuple[int, int, int]] = deque(
        (int(y), int(x), 0) for y, x in zip(*np.where(content))
    )
    while q:
        y, x, d = q.popleft()
        if d >= max_grow:
            continue
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and plate[ny, nx]:
                seen[ny, nx] = True
                protect[ny, nx] = True
                q.append((ny, nx, d + 1))

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

    # Peel outer black crumbs; keep denser costume blacks.
    alpha = arr[:, :, 3].copy()
    for _ in range(3):
        clear_n = np.zeros((h, w), dtype=np.uint8)
        opaque_n = np.zeros((h, w), dtype=np.uint8)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                clear_n += np.roll(np.roll(alpha < 8, dy, 0), dx, 1).astype(np.uint8)
                opaque_n += np.roll(np.roll(alpha > 200, dy, 0), dx, 1).astype(np.uint8)
        kill = (alpha > 200) & plate & (clear_n >= 3) & (opaque_n <= 5)
        alpha[kill] = 0
        arr[kill, 0:3] = 0
    arr[:, :, 3] = np.where(alpha < 40, 0, np.where(alpha > 210, 255, alpha)).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def main() -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)

    # Dino from attached good cut
    if not GOOD_DINO.is_file():
        raise SystemExit(f"missing good dino ref: {GOOD_DINO}")
    dino = center_square(knockout_light_plate(Image.open(GOOD_DINO)), 512)
    dino.save(SPRITES / "player_dobby_dino.png")
    _preview("player_dobby_dino.png", dino)
    _stats("player_dobby_dino.png (from attached good cut)", dino)

    # Others from cursor gens with clean short-grow knockout
    for name in PLAYERS:
        if name == "player_dobby_dino.png":
            continue
        src = CURSOR / name
        if not src.is_file():
            print("MISSING", name)
            continue
        # bee has more black stripes — slightly longer grow
        grow = 7 if "bee" in name or "octopus" in name else 5
        out = knockout_black_clean(process_black_square(Image.open(src), 512), max_grow=grow)
        out.save(SPRITES / name)
        _preview(name, out)
        _stats(f"{name} (short-grow key)", out)

    # Reference comparison
    ugly = Image.open(SPRITES / "player_dobby_ugly.png").convert("RGBA")
    _stats("player_dobby_ugly.png (style target)", ugly)


if __name__ == "__main__":
    main()
