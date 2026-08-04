"""Restore clean gameplay bg and build splash_booth.png with logo + title."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SPRITES = ROOT / "assets" / "sprites"
BG_PATH = SPRITES / "bg_booth.png"
SPLASH_PATH = SPRITES / "splash_booth.png"
LOGO_DEFAULT = Path(r"C:\Users\Dad\Downloads\New Logo 9-3-2025 just monkey.png")
CURSOR_BG = Path(
    r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets\bg_booth.png"
)
TARGET_SIZE = (540, 960)
ICON_OUT = ROOT / "assets" / "icon.png"
DOBBY = SPRITES / "player_dobby.png"


def knockout_black(im: Image.Image, thresh: int = 28) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r <= thresh and g <= thresh and b <= thresh:
                px[x, y] = (0, 0, 0, 0)
    return im


def tight_crop(im: Image.Image, pad: float = 0.04) -> Image.Image:
    bbox = im.split()[-1].getbbox()
    if not bbox:
        return im
    im = im.crop(bbox)
    pad_px = int(max(im.size) * pad)
    canvas = Image.new("RGBA", (im.width + pad_px * 2, im.height + pad_px * 2), (0, 0, 0, 0))
    canvas.paste(im, (pad_px, pad_px), im)
    return canvas


def restore_clean_bg() -> Image.Image:
    """Gameplay bg without logo, at TARGET_SIZE."""
    src = CURSOR_BG if CURSOR_BG.is_file() else BG_PATH
    bg = Image.open(src).convert("RGB")
    if bg.size != TARGET_SIZE:
        bg = bg.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
    bg.save(BG_PATH, optimize=True)
    print(f"gameplay bg restored {BG_PATH} {bg.size}")
    return bg.copy()


def _load_title_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        ROOT / "assets" / "fonts" / "game_font.ttf",
        ROOT / "assets" / "fonts" / "DejaVuSansMono.ttf",
        ROOT / "assets" / "fonts" / "PressStart2P.ttf",
    ]
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def build_splash(bg: Image.Image, logo_path: Path) -> None:
    splash = bg.convert("RGBA")
    logo = tight_crop(knockout_black(Image.open(logo_path)))

    wall_w = int(splash.width * 0.38)
    scale = wall_w / logo.width
    logo = logo.resize((wall_w, max(1, int(logo.height * scale))), Image.Resampling.LANCZOS)
    logo = ImageEnhance.Color(logo).enhance(0.95)
    logo = ImageEnhance.Brightness(logo).enhance(0.92)
    alpha = logo.split()[-1].filter(ImageFilter.GaussianBlur(radius=0.6))
    logo.putalpha(alpha)

    logo_x = (splash.width - logo.width) // 2
    logo_y = int(splash.height * 0.24)
    splash.paste(logo, (logo_x, logo_y), logo)

    # BOOTH BLASTER title above the logo
    draw = ImageDraw.Draw(splash)
    title = "BOOTH BLASTER"
    font = _load_title_font(max(28, splash.width // 14))
    bbox = draw.textbbox((0, 0), title, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (splash.width - tw) // 2
    ty = max(24, logo_y - th - int(splash.height * 0.04))
    # Soft shadow then accent pink
    draw.text((tx + 2, ty + 2), title, font=font, fill=(20, 20, 40, 220))
    draw.text((tx, ty), title, font=font, fill=(255, 105, 180, 255))

    splash.convert("RGB").save(SPLASH_PATH, optimize=True)
    print(f"splash written {SPLASH_PATH} title@{(tx, ty)} logo@{(logo_x, logo_y)}")


def make_icon(dobby_path: Path, out_path: Path, size: int = 512) -> None:
    if not dobby_path.is_file():
        print("skip icon — dobby missing")
        return
    cat = Image.open(dobby_path).convert("RGBA")
    bbox = cat.split()[-1].getbbox()
    if bbox:
        cat = cat.crop(bbox)
    side = int(max(cat.size) * 1.12)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(cat, ((side - cat.width) // 2, (side - cat.height) // 2), cat)
    square = square.resize((size, size), Image.Resampling.NEAREST)
    plate = Image.new("RGBA", (size, size), (28, 42, 72, 255))
    plate.paste(square, (0, 0), square)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plate.convert("RGB").save(out_path, optimize=True)
    print(f"icon written {out_path}")


def main() -> None:
    if not LOGO_DEFAULT.is_file():
        raise SystemExit(f"Logo not found: {LOGO_DEFAULT}")
    bg = restore_clean_bg()
    build_splash(bg, LOGO_DEFAULT)
    make_icon(DOBBY, ICON_OUT)


if __name__ == "__main__":
    main()
