"""Fix washed-out floor and tighten Dobby sprite fill."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

MASTER = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets\bg_booth.png")
BG = Path(r"C:\Users\Dad\Documents\DobbyCatRomGame\assets\sprites\bg_booth.png")
PLAYER = Path(r"C:\Users\Dad\Documents\DobbyCatRomGame\assets\sprites\player_dobby.png")


def fix_bg() -> None:
    im = Image.open(MASTER if MASTER.is_file() else BG).convert("RGB")
    w, h = im.size
    px = im.load()
    y0 = int(h * 0.78)
    for y in range(y0, h):
        t = (y - y0) / max(1, h - y0)
        t = t * t * (3 - 2 * t)
        strength = 0.12 + 0.30 * t
        tr, tg, tb = 78, 96, 118
        for x in range(w):
            r, g, b = px[x, y]
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            local = strength * (0.12 if luma > 155 else 1.0)
            # Mid cool concrete — never near-white
            nr = min(145, int(r * (1 - local) + tr * local + 8 * t))
            ng = min(158, int(g * (1 - local) + tg * local + 8 * t))
            nb = min(172, int(b * (1 - local) + tb * local + 10 * t))
            px[x, y] = (nr, ng, nb)
    im = im.resize((540, 960), Image.Resampling.LANCZOS)
    im.save(BG, optimize=True)
    print("bg fixed", im.size)


def tighten_player() -> None:
    cat = Image.open(PLAYER).convert("RGBA")
    bbox = cat.split()[-1].getbbox()
    print("player bbox", bbox, cat.size)
    if not bbox:
        return
    cropped = cat.crop(bbox)
    side = int(max(cropped.size) * 1.05)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2), cropped)
    canvas = canvas.resize((256, 256), Image.Resampling.NEAREST)
    canvas.save(PLAYER)
    print("player tightened")


if __name__ == "__main__":
    fix_bg()
    tighten_player()
