"""Install regenerated bg + player, knockout plate, tighten crop."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

SRC = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")
SPRITES = Path(r"C:\Users\Dad\Documents\DobbyCatRomGame\assets\sprites")


def _luma(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def knockout(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    # Sample corners for plate color
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
            if _luma(r, g, b) >= 230 and sat <= 30:
                px[x, y] = (0, 0, 0, 0)
                continue
            dist = ((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2) ** 0.5
            if dist < 40 and (_luma(*bg) > 200 or _luma(*bg) < 35):
                px[x, y] = (0, 0, 0, 0)
    return im


def main() -> None:
    bg_src = SRC / "bg_booth.png"
    pl_src = SRC / "player_dobby.png"
    bg_dst = SPRITES / "bg_booth.png"
    pl_dst = SPRITES / "player_dobby.png"

    bg = Image.open(bg_src).convert("RGB").resize((540, 960), Image.Resampling.LANCZOS)
    bg.save(bg_dst, optimize=True)
    print("bg installed", bg.size)

    cat = knockout(Image.open(pl_src))
    bbox = cat.split()[-1].getbbox()
    if bbox:
        cat = cat.crop(bbox)
    side = int(max(cat.size) * 1.05)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cat, ((side - cat.width) // 2, (side - cat.height) // 2), cat)
    canvas = canvas.resize((256, 256), Image.Resampling.NEAREST)
    # Harden alpha
    px = canvas.load()
    for y in range(256):
        for x in range(256):
            r, g, b, a = px[x, y]
            if a < 40:
                px[x, y] = (0, 0, 0, 0)
            elif a > 200:
                px[x, y] = (r, g, b, 255)
    canvas.save(pl_dst)
    print("player installed", canvas.size, "bbox", bbox)


if __name__ == "__main__":
    main()
