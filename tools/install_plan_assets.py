"""Install generated skin/boss/splash assets into the game tree."""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

SRC = Path(r"C:\Users\Dad\.cursor\projects\c-Users-Dad-Documents-DobbyCatRomGame\assets")
REPO = Path(r"C:\Users\Dad\Documents\DobbyCatRomGame")
SPRITES = REPO / "assets" / "sprites"
REF = REPO / "assets" / "reference"

sys.path.insert(0, str(REPO / "tools"))
from sprite_alpha import (  # noqa: E402
    harden_alpha,
    knockout_edge_plate,
    luma,
    strip_edge_halo,
)

INSTALL_SPRITES = [
    "player_dobby_bee.png",
    "player_dobby_hoodie_green.png",
    "player_dobby_dino.png",
    "player_dobby_cape.png",
    "player_dobby_pickle.png",
    "player_dobby_octopus.png",
    "player_dobby_hi_vis.png",
    "enemy_boss_parent_a.png",
    "enemy_boss_parent_b.png",
    "enemy_boss_nana.png",
]

SPLASH_CUTOUTS = [
    ("splash_cutout_box_dobby.png", "splash_cutout_box_dobby.png"),
    ("splash_cutout_meow_head.png", "splash_cutout_meow_head.png"),
]


def process_black_bg(img: Image.Image, size: int = 512) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 10:
                continue
            if r < 20 and g < 20 and b < 20:
                px[x, y] = (0, 0, 0, 0)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    pad = 24
    side = max(img.size) + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.size[0]) // 2, (side - img.size[1]) // 2), img)
    black = Image.new("RGBA", (side, side), (0, 0, 0, 255))
    black.paste(canvas, (0, 0), canvas)
    return black.resize((size, size), Image.Resampling.LANCZOS)


def _is_cream_fringe(r: int, g: int, b: int, a: int) -> bool:
    """Warm/white studio-plate crumbs left on cutout edges (not interior fur fills)."""
    if a < 8:
        return False
    sat = max(r, g, b) - min(r, g, b)
    lu = luma(r, g, b)
    if lu >= 215 and sat <= 60:
        return True
    # Warm cream bleed from white plate × subject (sat can be high).
    # Opaque cardboard highlights are usually darker — require brighter plate mix.
    if lu >= 200 and sat <= 120 and r >= 220 and g >= 175:
        return True
    if a < 220 and lu >= 175 and sat <= 110 and r >= 180 and g >= 150:
        return True
    if lu >= 190 and sat <= 35:
        return True
    return False


def _strip_cream_edge_flood(img: Image.Image, max_depth: int = 12) -> Image.Image:
    """Flood from transparent edge into cream/white fringe only."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    visited = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int, int]] = deque()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if not _is_cream_fringe(r, g, b, a):
                continue
            if any(
                0 <= x + dx < w
                and 0 <= y + dy < h
                and px[x + dx, y + dy][3] < 8
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
            ):
                visited[y][x] = True
                q.append((x, y, 0))
    kill: list[tuple[int, int]] = []
    while q:
        x, y, depth = q.popleft()
        kill.append((x, y))
        if depth >= max_depth:
            continue
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h) or visited[ny][nx]:
                continue
            r, g, b, a = px[nx, ny]
            if _is_cream_fringe(r, g, b, a):
                visited[ny][nx] = True
                q.append((nx, ny, depth + 1))
    for x, y in kill:
        px[x, y] = (0, 0, 0, 0)
    return img


def _decontaminate_cutout_edges(img: Image.Image) -> Image.Image:
    """Drop cream crumbs; pull remaining edge RGB toward darker interior neighbors."""
    img = img.convert("RGBA")
    w, h = img.size
    src = img.copy()
    sp = src.load()
    px = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a < 8:
                continue
            near_clear = any(
                0 <= x + dx < w
                and 0 <= y + dy < h
                and sp[x + dx, y + dy][3] < 8
                for dy, dx in (
                    (-1, 0),
                    (1, 0),
                    (0, -1),
                    (0, 1),
                    (-1, -1),
                    (1, 1),
                    (-1, 1),
                    (1, -1),
                )
            )
            if not near_clear:
                continue
            if _is_cream_fringe(r, g, b, a):
                px[x, y] = (0, 0, 0, 0)
                continue
            cr = cg = cb = cn = 0
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < w and 0 <= ny < h):
                        continue
                    nr, ng, nb, na = sp[nx, ny]
                    if na < 200 or _is_cream_fringe(nr, ng, nb, na):
                        continue
                    if luma(nr, ng, nb) < luma(r, g, b) - 5:
                        cr += nr
                        cg += ng
                        cb += nb
                        cn += 1
            if cn and luma(r, g, b) > 140:
                px[x, y] = (cr // cn, cg // cn, cb // cn, a)
    return img


def _erode_alpha(img: Image.Image, radius: int = 1) -> Image.Image:
    """Contract silhouette to eat leftover 1px plate outline."""
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    for _ in range(radius):
        alpha = alpha.filter(ImageFilter.MinFilter(3))
    img.putalpha(alpha)
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a < 8:
                px[x, y] = (0, 0, 0, 0)
    return img


def _count_cream_edge(img: Image.Image) -> int:
    px = img.load()
    w, h = img.size
    n = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 8 or not _is_cream_fringe(r, g, b, a):
                continue
            if any(
                0 <= x + dx < w
                and 0 <= y + dy < h
                and px[x + dx, y + dy][3] < 8
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
            ):
                n += 1
    return n


def _apply_sprite_pixel_grain(img: Image.Image, size: int, cells: int = 256) -> Image.Image:
    """NEAREST down/up like player_dobby — chunky grain without palette crush."""
    img = img.convert("RGBA")
    small = img.resize((cells, cells), Image.Resampling.NEAREST)
    return small.resize((size, size), Image.Resampling.NEAREST)


def _guard_cutout_quality(img: Image.Image, *, label: str = "cutout") -> Image.Image:
    """Fail loud if output drifted into muddy dither / opaque plate / heavy fringe."""
    img = img.convert("RGBA")
    w, h = img.size
    colors = img.getcolors(maxcolors=w * h)
    n_colors = len(colors) if colors else w * h
    alpha = img.getchannel("A")
    clear = sum(1 for v in alpha.getdata() if v < 8)
    clear_ratio = clear / float(w * h)
    cream = _count_cream_edge(img)
    corners = [img.getpixel((2, 2))[3], img.getpixel((w - 3, h - 3))[3]]
    problems: list[str] = []
    if clear_ratio < 0.15:
        problems.append(f"clear_ratio={clear_ratio:.3f} (need transparent plate)")
    if any(a > 0 for a in corners):
        problems.append(f"opaque corners alpha={corners}")
    if n_colors < 1500:
        problems.append(f"unique_colors={n_colors} (palette crush / over-dither)")
    if cream > 120:
        problems.append(f"cream_edge={cream} (white fringe too heavy)")
    if problems:
        raise RuntimeError(f"{label} quality gate failed: " + "; ".join(problems))
    print(
        f"quality ok {label}: colors={n_colors} clear={clear_ratio:.3f} cream_edge={cream}"
    )
    return img


def _recolor_white_strokes(img: Image.Image) -> Image.Image:
    """Recolor thin near-white outline strokes from darker neighbors; drop outer crumbs."""
    img = img.convert("RGBA")
    w, h = img.size
    src = img.copy()
    sp = src.load()
    px = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a < 8:
                continue
            sat = max(r, g, b) - min(r, g, b)
            lu = luma(r, g, b)
            if not (lu >= 205 and sat <= 55):
                continue
            cr = cg = cb = cn = 0
            clear_n = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < w and 0 <= ny < h):
                        clear_n += 1
                        continue
                    nr, ng, nb, na = sp[nx, ny]
                    if na < 8:
                        clear_n += 1
                        continue
                    nlu = luma(nr, ng, nb)
                    nsat = max(nr, ng, nb) - min(nr, ng, nb)
                    if nlu >= 205 and nsat <= 55:
                        continue
                    if nlu < lu - 15:
                        cr += nr
                        cg += ng
                        cb += nb
                        cn += 1
            if cn >= 2:
                px[x, y] = (cr // cn, cg // cn, cb // cn, a)
            elif clear_n >= 2 and (cn >= 1 or lu >= 220):
                px[x, y] = (0, 0, 0, 0)
    return img


def _strip_light_outer_rim(img: Image.Image, passes: int = 2) -> Image.Image:
    """Drop thin light rim pixels touching clear (outer halo only)."""
    img = img.convert("RGBA")
    w, h = img.size
    for _ in range(passes):
        src = img.copy()
        sp = src.load()
        px = img.load()
        for y in range(h):
            for x in range(w):
                r, g, b, a = sp[x, y]
                if a < 8:
                    continue
                near_clear = any(
                    0 <= x + dx < w
                    and 0 <= y + dy < h
                    and sp[x + dx, y + dy][3] < 8
                    for dy, dx in (
                        (-1, 0),
                        (1, 0),
                        (0, -1),
                        (0, 1),
                        (-1, -1),
                        (1, 1),
                        (-1, 1),
                        (1, -1),
                    )
                )
                if not near_clear:
                    continue
                sat = max(r, g, b) - min(r, g, b)
                lu = luma(r, g, b)
                opaque_n = sum(
                    1
                    for dy in (-1, 0, 1)
                    for dx in (-1, 0, 1)
                    if not (dx == 0 and dy == 0)
                    and 0 <= x + dx < w
                    and 0 <= y + dy < h
                    and sp[x + dx, y + dy][3] > 200
                )
                if opaque_n > 5:
                    continue
                if lu >= 175 and sat <= 70:
                    px[x, y] = (0, 0, 0, 0)
                elif lu >= 155 and sat <= 45 and opaque_n <= 3:
                    px[x, y] = (0, 0, 0, 0)
                elif lu >= 185 and r >= 190 and g >= 150 and opaque_n <= 4:
                    px[x, y] = (0, 0, 0, 0)
    return img


def process_generated_cutout(img: Image.Image, size: int = 768) -> Image.Image:
    """Knock out black-plate generative cutouts; recolor white strokes; sprite grain."""
    img = knockout_edge_plate(img.convert("RGBA"))
    img = strip_edge_halo(img)
    img = _recolor_white_strokes(img)
    img = _strip_light_outer_rim(img, passes=3)
    img = _strip_cream_edge_flood(img, max_depth=10)
    img = _decontaminate_cutout_edges(img)
    img = _recolor_white_strokes(img)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    pad = 12
    side = max(img.size) + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.size[0]) // 2, (side - img.size[1]) // 2), img)
    out = canvas.resize((256, 256), Image.Resampling.NEAREST)
    out = out.resize((size, size), Image.Resampling.NEAREST)
    out = harden_alpha(out)
    out = _strip_light_outer_rim(out, passes=2)
    out = _strip_cream_edge_flood(out, max_depth=3)
    out = _recolor_white_strokes(out)
    return _guard_cutout_quality(out, label="generated_cutout")


def process_transparent_cutout(img: Image.Image, size: int = 768) -> Image.Image:
    """Edge-connected plate knockout + cream fringe strip; keep interior whites."""
    img = knockout_edge_plate(img.convert("RGBA"))
    img = strip_edge_halo(img)
    img = _strip_cream_edge_flood(img, max_depth=14)
    img = _decontaminate_cutout_edges(img)
    img = _erode_alpha(img, radius=2)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    pad = 16
    side = max(img.size) + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.size[0]) // 2, (side - img.size[1]) // 2), img)
    # Build clean master at size, then sprite-style NEAREST grain (no quantize/dither).
    out = canvas.resize((size, size), Image.Resampling.LANCZOS)
    out = strip_edge_halo(out)
    out = _strip_cream_edge_flood(out, max_depth=5)
    out = _decontaminate_cutout_edges(out)
    out = _erode_alpha(out, radius=1)
    out = harden_alpha(out)
    out = _strip_cream_edge_flood(out, max_depth=3)
    out = _decontaminate_cutout_edges(out)
    out = _apply_sprite_pixel_grain(out, size=size, cells=256)
    # Grain can re-expose cream rim crumbs on block edges.
    out = _strip_cream_edge_flood(out, max_depth=2)
    out = _decontaminate_cutout_edges(out)
    return _guard_cutout_quality(out, label="splash_cutout")


def main() -> None:
    REF.mkdir(parents=True, exist_ok=True)
    for name in INSTALL_SPRITES:
        p = SRC / name
        if not p.is_file():
            print("MISSING", name)
            continue
        size = 512 if name.startswith("player") else 640
        out = process_black_bg(Image.open(p), size)
        out.save(SPRITES / name)
        print("installed", name, out.size, (SPRITES / name).stat().st_size)

    for src_name, dst_name in SPLASH_CUTOUTS:
        p = SRC / src_name
        if not p.is_file():
            print("MISSING cutout", src_name)
            continue
        out = process_transparent_cutout(Image.open(p))
        out.save(REF / dst_name)
        print("cutout", dst_name, out.size)

    print("skins:", sorted(p.name for p in SPRITES.glob("player_dobby*.png")))
    print("bosses:", sorted(p.name for p in SPRITES.glob("enemy_boss*.png")))


if __name__ == "__main__":
    main()
