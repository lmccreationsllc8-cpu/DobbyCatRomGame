"""Knock out generated studio plates and export crisp RGBA sprites."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
SRC_DIR = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")


def _luma(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def _dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _corner_bg(im: Image.Image) -> tuple[int, int, int]:
    px = im.convert("RGB")
    w, h = px.size
    samples: list[tuple[int, int, int]] = []
    for x, y in (
        (2, 2),
        (w - 3, 2),
        (2, h - 3),
        (w - 3, h - 3),
        (w // 2, 2),
        (2, h // 2),
        (w - 3, h // 2),
        (w // 2, h - 3),
    ):
        samples.append(px.getpixel((x, y)))
    # Quantize a bit so near-matches group
    buckets = Counter((r // 8 * 8, g // 8 * 8, b // 8 * 8) for r, g, b in samples)
    return buckets.most_common(1)[0][0]


def knockout(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    bg = _corner_bg(im)
    px = im.load()
    w, h = im.size
    # Threshold: looser for near-white/near-black plates, tighter for colored plates
    base_thr = 48 if (_luma(*bg) < 40 or _luma(*bg) > 220) else 36

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            luma = _luma(r, g, b)
            # Always kill classic white/light-gray studio plates
            sat = max(r, g, b) - min(r, g, b)
            if luma >= 230 and sat <= 30:
                px[x, y] = (0, 0, 0, 0)
                continue
            # Kill near-black empty plate (common in regen)
            if luma <= 18 and _dist((r, g, b), bg) < 40:
                px[x, y] = (0, 0, 0, 0)
                continue
            if _dist((r, g, b), bg) <= base_thr:
                px[x, y] = (0, 0, 0, 0)

    # Edge fringe: translucent/light pixels touching clear become clear
    src = im.copy()
    sp = src.load()
    px = im.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a == 0:
                continue
            near_clear = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and sp[nx, ny][3] == 0:
                        near_clear = True
                        break
                if near_clear:
                    break
            if not near_clear:
                continue
            if _luma(r, g, b) >= 200 and (max(r, g, b) - min(r, g, b)) < 40:
                px[x, y] = (0, 0, 0, 0)
            elif _luma(r, g, b) <= 25 and _dist((r, g, b), bg) < 50:
                px[x, y] = (0, 0, 0, 0)
    return im


def autocrop(im: Image.Image, pad: int = 8) -> Image.Image:
    bbox = im.split()[-1].getbbox()
    if not bbox:
        return im
    l, t, r, b = bbox
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(im.width, r + pad)
    b = min(im.height, b + pad)
    return im.crop((l, t, r, b))


def clean_bg(im: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    px = im.load()
    w, h = im.size
    for x in range(w):
        bright_col = 0
        for y in range(0, h, 6):
            r, g, b = px[x, y]
            if _luma(r, g, b) > 215 and (max(r, g, b) - min(r, g, b)) < 40:
                bright_col += 1
        if bright_col > h // 50:
            for y in range(h):
                left = px[max(0, x - 3), y]
                right = px[min(w - 1, x + 3), y]
                px[x, y] = tuple((left[i] * 2 + right[i] * 2) // 4 for i in range(3))

    # Mild denoise on wall grain only via light blur blend
    soft = im.filter(ImageFilter.MedianFilter(size=3))
    return Image.blend(im, soft, 0.25)


def process_sprite(path: Path) -> None:
    im = Image.open(path)
    if path.name.startswith("bg_"):
        out = clean_bg(im)
        out = out.resize((540, 960), Image.Resampling.LANCZOS)
        out.save(path, optimize=True)
        print(f"bg cleaned {path.name} -> {out.size} {out.mode}")
        return

    out = knockout(im)
    out = autocrop(out, pad=10)
    side = max(out.width, out.height, 32)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(out, ((side - out.width) // 2, (side - out.height) // 2), out)
    canvas = canvas.resize((256, 256), Image.Resampling.LANCZOS)
    canvas = knockout(canvas)
    # Harden alpha: almost-transparent -> fully clear; nearly opaque -> solid
    px = canvas.load()
    for y in range(canvas.height):
        for x in range(canvas.width):
            r, g, b, a = px[x, y]
            if a < 40:
                px[x, y] = (0, 0, 0, 0)
            elif a > 200:
                px[x, y] = (r, g, b, 255)
    canvas.save(path, optimize=True)
    alpha = canvas.split()[-1]
    clear = sum(1 for v in alpha.getdata() if v == 0)
    print(f"sprite {path.name} -> {canvas.size} RGBA clear={clear}/{256*256}")


def main() -> int:
    # Prefer freshly generated masters when present
    for name in (
        "bg_booth.png",
        "player_dobby.png",
        "enemy_tote.png",
        "enemy_badge.png",
        "barrier_crate.png",
        "enemy_selfie.png",
        "enemy_linecutter.png",
        "enemy_boss.png",
        "bolt.png",
    ):
        src = SRC_DIR / name
        if src.is_file():
            (SPRITES / name).write_bytes(src.read_bytes())

    names = sorted(SPRITES.glob("*.png"))
    if not names:
        print("No sprites found", file=sys.stderr)
        return 1
    for path in names:
        process_sprite(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
