"""Rebuild sprite alpha: fill holes, peel thick black borders, keep dark clothes."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
CURSOR = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")
PREVIEW = ROOT / "assets" / "reference" / "alpha_preview"
GOOD_DINO = CURSOR / "c__Users_Dad_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_image-d89fc05b-d556-4aee-8e02-3cbb899fc06b.png"

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


def _lu_sat(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lu = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    return lu, sat


def square_on_black(im: Image.Image, size: int) -> Image.Image:
    im = im.convert("RGBA")
    arr = np.asarray(im).copy()
    lu, sat = _lu_sat(arr[:, :, :3].astype(np.int16))
    # temp-clear near-black for bbox only
    tmp = arr.copy()
    tmp[(lu <= 18) & (sat <= 22), 3] = 0
    bbox = Image.fromarray(tmp, "RGBA").getbbox()
    if bbox:
        im = im.crop(bbox)
    pad = 20
    side = max(im.size) + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2), im.convert("RGBA"))
    black = Image.new("RGBA", (side, side), (0, 0, 0, 255))
    black.paste(canvas, (0, 0), canvas)
    return black.resize((size, size), Image.Resampling.LANCZOS)


def key_light_plate(im: Image.Image, size: int) -> Image.Image:
    """For light-bg reference cuts (good dino)."""
    im = im.convert("RGBA")
    arr = np.asarray(im).copy()
    rgb = arr[:, :, :3].astype(np.int16)
    lu, sat = _lu_sat(rgb)
    # light plate + near-white holes
    plate = ((lu >= 235) & (sat <= 40)) | ((rgb[:, :, 0] > 245) & (rgb[:, :, 1] > 245) & (rgb[:, :, 2] > 245))
    arr[plate, 3] = 0
    arr[plate, 0:3] = 0
    out = Image.fromarray(arr, "RGBA")
    bbox = out.getbbox()
    if bbox:
        out = out.crop(bbox)
    pad = 20
    side = max(out.size) + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(out, ((side - out.size[0]) // 2, (side - out.size[1]) // 2), out)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def fill_interior_holes(arr: np.ndarray, original: np.ndarray) -> np.ndarray:
    """Restore transparent islands that were real content (not bg plate).

    Hair curl gaps that were originally black plate stay transparent.
    Eaten costume fills (originally colored) get restored.
    """
    h, w = arr.shape[:2]
    orgb = original[:, :, :3].astype(np.int16)
    olu, osat = _lu_sat(orgb)
    was_content = (olu > 26) | (osat > 30)
    clear = arr[:, :, 3] < 8
    seen = np.zeros((h, w), dtype=bool)
    for y in range(h):
        for x in range(w):
            if not clear[y, x] or seen[y, x]:
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            seen[y, x] = True
            comp: list[tuple[int, int]] = []
            touches = False
            content_hits = 0
            while q:
                cx, cy = q.popleft()
                comp.append((cx, cy))
                if was_content[cy, cx]:
                    content_hits += 1
                if cx in (0, w - 1) or cy in (0, h - 1):
                    touches = True
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h and clear[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((nx, ny))
            # Restore colored costume hits, or larger islands (black clothes),
            # but skip tiny enclosed plate speckles (hair curl gaps).
            if not touches and (content_hits >= max(1, len(comp) // 5) or len(comp) >= 48):
                for cx, cy in comp:
                    arr[cy, cx] = original[cy, cx]
    return arr


def edge_flood_plate(arr: np.ndarray, lu_max: float = 14.0, sat_max: float = 18.0) -> np.ndarray:
    """Clear near-black plate connected to the image edge (strict)."""
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)
    lu, sat = _lu_sat(rgb)
    plate = (arr[:, :, 3] >= 8) & (lu <= lu_max) & (sat <= sat_max)
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
            if 0 <= nx < w and 0 <= ny < h and plate[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                q.append((nx, ny))
    arr[visited, 3] = 0
    arr[visited, 0:3] = 0
    return arr


def peel_black_border(arr: np.ndarray, passes: int = 3) -> np.ndarray:
    """Remove thick outer black outline while keeping interior dark clothing.

    Peels near-black edge pixels that touch transparency. Stops when a pixel
    has strong non-black content neighbors (fur/cloth color).
    """
    for _ in range(passes):
        rgb = arr[:, :, :3].astype(np.int16)
        lu, sat = _lu_sat(rgb)
        alpha = arr[:, :, 3]
        clear = alpha < 8
        opaque = alpha > 200
        clear_n = np.zeros(alpha.shape, dtype=np.uint8)
        content_n = np.zeros(alpha.shape, dtype=np.uint8)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                a2 = np.roll(np.roll(alpha, dy, 0), dx, 1)
                lu2 = np.roll(np.roll(lu, dy, 0), dx, 1)
                sat2 = np.roll(np.roll(sat, dy, 0), dx, 1)
                clear_n += (a2 < 8).astype(np.uint8)
                content_n += ((a2 > 200) & ((lu2 > 35) | (sat2 > 35))).astype(np.uint8)
        # Peel pure-ish black fringe; keep if surrounded by real content colors
        peel = opaque & (lu <= 28) & (sat <= 28) & (clear_n >= 2) & (content_n <= 1)
        arr[peel, 3] = 0
        arr[peel, 0:3] = 0
    return arr


def strip_magenta(arr: np.ndarray) -> np.ndarray:
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    mag = (a > 8) & (r >= 180) & (b >= 180) & (g <= 140) & ((r.astype(int) + b.astype(int) - 2 * g.astype(int)) > 160)
    arr[mag, 3] = 0
    arr[mag, 0:3] = 0
    return arr


def harden(arr: np.ndarray) -> np.ndarray:
    a = arr[:, :, 3]
    arr[:, :, 3] = np.where(a < 40, 0, np.where(a > 210, 255, a)).astype(np.uint8)
    return arr


def _morph_dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    img = Image.fromarray((mask.astype(np.uint8) * 255))
    for _ in range(radius):
        img = img.filter(ImageFilter.MaxFilter(3))
    return np.asarray(img) > 127


def edge_flood_plate_protected(
    arr: np.ndarray,
    protect: np.ndarray,
    lu_max: float = 12.0,
    sat_max: float = 16.0,
) -> np.ndarray:
    """Edge-flood near-black plate, never entering protect mask."""
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)
    lu, sat = _lu_sat(rgb)
    plate = (arr[:, :, 3] >= 8) & (lu <= lu_max) & (sat <= sat_max) & (~protect)
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
            if 0 <= nx < w and 0 <= ny < h and plate[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                q.append((nx, ny))
    arr[visited, 3] = 0
    arr[visited, 0:3] = 0
    return arr


def process_black_source(
    im: Image.Image,
    size: int,
    peel_passes: int = 3,
    protect_grow: int = 0,
) -> Image.Image:
    base = square_on_black(im, size)
    original = np.asarray(base).copy()
    arr = original.copy()
    rgb = arr[:, :, :3].astype(np.int16)
    lu, sat = _lu_sat(rgb)
    seed = (lu > 28) | (sat > 32)
    protect = _morph_dilate(seed, protect_grow) if protect_grow > 0 else np.zeros(lu.shape, dtype=bool)

    if protect_grow > 0:
        arr = edge_flood_plate_protected(arr, protect, lu_max=14, sat_max=18)
    else:
        arr = edge_flood_plate(arr, lu_max=12, sat_max=16)

    arr = fill_interior_holes(arr, original)
    # Peel ignores protect — it only removes outer black fringe touching clear.
    arr = peel_black_border(arr, passes=peel_passes)
    arr = fill_interior_holes(arr, original)
    arr = peel_black_border(arr, passes=2)
    # Clear any remaining near-black that is outside the dilated content core
    # (leftover halo ring protected from flood but still plate).
    if protect_grow > 0:
        rgb = arr[:, :, :3].astype(np.int16)
        lu, sat = _lu_sat(rgb)
        core = _morph_dilate((lu > 28) | (sat > 32), max(1, protect_grow // 2))
        halo = (arr[:, :, 3] > 200) & (lu <= 22) & (sat <= 22) & (~core)
        arr[halo, 3] = 0
        arr[halo, 0:3] = 0
    arr = fill_interior_holes(arr, original)
    arr = strip_magenta(arr)
    arr = harden(arr)
    return Image.fromarray(arr, "RGBA")


def stats(path: Path) -> str:
    a = np.asarray(Image.open(path).convert("RGBA"))
    rgb = a[:, :, :3].astype(np.int16)
    lu, sat = _lu_sat(rgb)
    alpha = a[:, :, 3]
    clear = alpha < 8
    opaque = alpha > 200
    clear_n = np.zeros(alpha.shape, dtype=np.uint8)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            clear_n += np.roll(np.roll(clear, dy, 0), dx, 1).astype(np.uint8)
    border = opaque & (lu <= 25) & (sat <= 30) & (clear_n >= 3)
    # hole px
    h, w = clear.shape
    seen = np.zeros_like(clear)
    holes = 0
    for y in range(h):
        for x in range(w):
            if not clear[y, x] or seen[y, x]:
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            seen[y, x] = True
            border_touch = False
            size = 0
            while q:
                cx, cy = q.popleft()
                size += 1
                if cx in (0, w - 1) or cy in (0, h - 1):
                    border_touch = True
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h and clear[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((nx, ny))
            if not border_touch and size > 5:
                holes += size
    return f"clear={clear.mean():.1%} black_border={int(border.sum())} holes={holes}"


def save_light_preview(name: str) -> None:
    im = Image.open(SPRITES / name).convert("RGBA")
    bg = Image.new("RGB", im.size, (180, 200, 220))
    bg.paste(im, mask=im.split()[-1])
    PREVIEW.mkdir(parents=True, exist_ok=True)
    bg.save(PREVIEW / f"light_{name}")


def main() -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)

    # Dino from user's good light-bg cut
    if GOOD_DINO.is_file():
        arr = np.asarray(key_light_plate(Image.open(GOOD_DINO), 512)).copy()
        # Fill white micro-holes by dilating opaque neighbors into clear islands
        for _ in range(5):
            clear = arr[:, :, 3] < 8
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    src = np.roll(np.roll(arr, dy, 0), dx, 1)
                    take = clear & (src[:, :, 3] > 200)
                    arr[take] = src[take]
        arr = edge_flood_plate(arr, lu_max=10, sat_max=14)
        arr = peel_black_border(arr, passes=2)
        arr = harden(arr)
        Image.fromarray(arr, "RGBA").save(SPRITES / "player_dobby_dino.png")
        print("player_dobby_dino.png", stats(SPRITES / "player_dobby_dino.png"))
        save_light_preview("player_dobby_dino.png")

    for name in PLAYERS:
        if name == "player_dobby_dino.png":
            continue
        src = CURSOR / name
        if not src.is_file():
            print("MISSING", name)
            continue
        out = process_black_source(Image.open(src), 512, peel_passes=4, protect_grow=5)
        out.save(SPRITES / name)
        print(name, stats(SPRITES / name))
        save_light_preview(name)

    for name in BOSSES:
        src = CURSOR / name
        if not src.is_file():
            print("MISSING", name)
            continue
        out = process_black_source(Image.open(src), 640, peel_passes=6, protect_grow=14)
        out.save(SPRITES / name)
        print(name, stats(SPRITES / name))
        save_light_preview(name)


if __name__ == "__main__":
    main()
