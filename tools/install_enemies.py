"""Install new enemy roster sprites with transparency knockout."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

SRC = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")
SPRITES = Path(r"C:\Users\Dad\Documents\DobbyCatRomGame\assets\sprites")

NAMES = (
    "enemy_box.png",
    "enemy_tote.png",
    "enemy_child.png",
    "enemy_adult.png",
    "enemy_maid_pink.png",
    "enemy_maid_cyan.png",
    "enemy_maid_lime.png",
    "enemy_boss.png",
)


def _luma(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def knockout(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    corners = [
        im.getpixel((2, 2))[:3],
        im.getpixel((w - 3, 2))[:3],
        im.getpixel((2, h - 3))[:3],
        im.getpixel((w - 3, h - 3))[:3],
    ]
    bg = tuple(sum(c[i] for c in corners) // 4 for i in range(3))
    px = im.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            sat = max(r, g, b) - min(r, g, b)
            if _luma(r, g, b) >= 228 and sat <= 32:
                px[x, y] = (0, 0, 0, 0)
                continue
            dist = ((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2) ** 0.5
            if dist < 42 and (_luma(*bg) > 200 or _luma(*bg) < 30):
                px[x, y] = (0, 0, 0, 0)
    return im


def install(name: str) -> None:
    src = SRC / name
    if not src.is_file():
        print("missing", name)
        return
    im = knockout(Image.open(src))
    bbox = im.split()[-1].getbbox()
    if bbox:
        im = im.crop(bbox)
    side = max(im.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    canvas = canvas.resize((256, 256), Image.Resampling.NEAREST)
    px = canvas.load()
    for y in range(256):
        for x in range(256):
            r, g, b, a = px[x, y]
            if a < 40:
                px[x, y] = (0, 0, 0, 0)
            elif a > 200:
                px[x, y] = (r, g, b, 255)
    canvas.save(SPRITES / name)
    print("ok", name)


def main() -> None:
    for name in NAMES:
        install(name)


if __name__ == "__main__":
    main()
