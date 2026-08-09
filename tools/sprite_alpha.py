"""Safe sprite alpha helpers: magenta chroma + edge-connected plate knockout.

Never blanket-delete luma>=230 whites — that punches eyes, socks, fur fills.
"""

from __future__ import annotations

from collections import Counter, deque

from PIL import Image


def luma(r: int, g: int, b: int) -> float:
    return 0.299 * r + 0.587 * g + 0.114 * b


def dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def is_magenta(r: int, g: int, b: int) -> bool:
    if r >= 180 and b >= 180 and g <= 120:
        return True
    if r >= 200 and b >= 160 and g <= 140 and (r + b) - 2 * g > 180:
        return True
    if abs(r - 255) < 40 and abs(b - 255) < 40 and g < 100:
        return True
    return False


def corner_bg(im: Image.Image) -> tuple[int, int, int]:
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
    buckets = Counter((r // 8 * 8, g // 8 * 8, b // 8 * 8) for r, g, b in samples)
    return buckets.most_common(1)[0][0]


def knockout_magenta(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, _a = px[x, y]
            if is_magenta(r, g, b):
                px[x, y] = (0, 0, 0, 0)

    # Magenta fringe only (never white fills)
    for _ in range(2):
        src = im.copy()
        sp = src.load()
        px = im.load()
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                r, g, b, a = sp[x, y]
                if a == 0:
                    continue
                mag_tint = (r + b) / 2 - g
                if mag_tint <= 40 or g >= 180:
                    continue
                tn = sum(
                    1
                    for dy in (-1, 0, 1)
                    for dx in (-1, 0, 1)
                    if sp[x + dx, y + dy][3] == 0
                )
                if tn >= 2 or mag_tint > 110:
                    px[x, y] = (0, 0, 0, 0)
                elif mag_tint > 40:
                    px[x, y] = (min(r, g + 40), g, min(b, g + 40), 255)
    return im


def _is_plate_pixel(
    r: int, g: int, b: int, a: int, bg: tuple[int, int, int], bg_luma: float
) -> bool:
    if a < 8:
        return True
    if is_magenta(r, g, b):
        return True
    sat = max(r, g, b) - min(r, g, b)
    lu = luma(r, g, b)
    d = dist((r, g, b), bg)
    # Light studio plate — match corner gray/white plate, but not saturated creams
    # that diverge from the plate hue (restore pass also recovers content whites).
    if bg_luma >= 200 and sat <= 30 and d <= 42 and abs(lu - bg_luma) <= 36:
        return True
    # Near-black plate
    if bg_luma <= 40 and lu <= 28 and sat <= 35 and d <= 40:
        return True
    # Generic near-bg empty (colored plates)
    if 40 < bg_luma < 200 and d <= 28 and sat <= 40:
        return True
    return False


def _is_content_pixel(r: int, g: int, b: int, a: int, bg: tuple[int, int, int], bg_luma: float) -> bool:
    if a < 8:
        return False
    if _is_plate_pixel(r, g, b, a, bg, bg_luma):
        return False
    return True


def knockout_edge_plate(im: Image.Image) -> Image.Image:
    """Remove studio plate only where flood-reachable from the image edge.

    After flood, restore bright fills that still have solid content neighbors
    (eyes/socks/apron that briefly touched the plate). Never blanket-delete whites.
    """
    im = im.convert("RGBA")
    w, h = im.size
    bg = corner_bg(im)
    bg_luma = luma(*bg)
    original = im.copy()
    opx = original.load()
    px = im.load()

    plate = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            plate[y][x] = _is_plate_pixel(r, g, b, a, bg, bg_luma)

    visited = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if plate[y][x] and not visited[y][x]:
                visited[y][x] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if plate[y][x] and not visited[y][x]:
                visited[y][x] = True
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and plate[ny][nx] and not visited[ny][nx]:
                visited[ny][nx] = True
                q.append((nx, ny))

    for y in range(h):
        for x in range(w):
            if visited[y][x]:
                px[x, y] = (0, 0, 0, 0)

    # Restore bright fills wrongly flooded when they are mostly surrounded by
    # remaining content. Outer halo crumbs touch clear on many sides — skip those.
    for y in range(h):
        for x in range(w):
            if not visited[y][x]:
                continue
            r, g, b, a = opx[x, y]
            if a < 8:
                continue
            sat = max(r, g, b) - min(r, g, b)
            lu = luma(r, g, b)
            if not (lu >= 200 and sat <= 50):
                continue
            content_n = 0
            clear_n = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < w and 0 <= ny < h):
                        clear_n += 1
                        continue
                    nr, ng, nb, na = px[nx, ny]
                    if na < 8:
                        clear_n += 1
                    elif _is_content_pixel(nr, ng, nb, na, bg, bg_luma):
                        content_n += 1
            if content_n >= 4 and clear_n <= 2:
                px[x, y] = (r, g, b, 255)

    # Strip thin plate/magenta fringe touching clear.
    src = im.copy()
    sp = src.load()
    px = im.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a == 0:
                continue
            near_clear = any(
                0 <= x + dx < w
                and 0 <= y + dy < h
                and sp[x + dx, y + dy][3] == 0
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
                if not (dx == 0 and dy == 0)
            )
            if not near_clear:
                continue
            if is_magenta(r, g, b):
                px[x, y] = (0, 0, 0, 0)
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
            # Outer halo from light studio plates
            if lu >= 200 and sat <= 45 and (bg_luma >= 180 or dist((r, g, b), bg) <= 70):
                px[x, y] = (0, 0, 0, 0)
            elif lu <= 22 and sat <= 35 and (bg_luma <= 40 or dist((r, g, b), bg) < 50):
                px[x, y] = (0, 0, 0, 0)
    return im


def knockout(im: Image.Image) -> Image.Image:
    """Auto: magenta key if corners are magenta, else edge-connected plate.

    If the sprite already has real alpha, do not run edge-plate again — corner
    samples become (0,0,0) and would eat black clothing / outlines.
    """
    im = im.convert("RGBA")
    w, h = im.size
    alpha = im.getchannel("A")
    clear_ratio = sum(1 for v in alpha.getdata() if v < 8) / float(w * h)
    if clear_ratio > 0.05:
        # Already keyed: only strip magenta crumbs touching clear
        return strip_edge_halo(im)

    corners = [
        im.getpixel((2, 2))[:3],
        im.getpixel((w - 3, 2))[:3],
        im.getpixel((2, h - 3))[:3],
        im.getpixel((w - 3, h - 3))[:3],
    ]
    mag_corners = sum(1 for c in corners if is_magenta(*c))
    if mag_corners >= 2:
        return knockout_magenta(im)
    return knockout_edge_plate(im)


def harden_alpha(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a < 40 or is_magenta(r, g, b):
                px[x, y] = (0, 0, 0, 0)
            elif a > 200:
                px[x, y] = (r, g, b, 255)
    return im


def autocrop(im: Image.Image, pad: int = 10) -> Image.Image:
    bbox = im.split()[-1].getbbox()
    if not bbox:
        return im
    l, t, r, b = bbox
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(im.width, r + pad)
    b = min(im.height, b + pad)
    return im.crop((l, t, r, b))


def to_square(im: Image.Image, size: int = 256, pad: int = 10) -> Image.Image:
    im = autocrop(im, pad=pad)
    side = max(im.width, im.height, 32)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    return canvas.resize((size, size), Image.Resampling.NEAREST)


def strip_edge_halo(im: Image.Image) -> Image.Image:
    """Remove thin gray/magenta fringe touching clear without eating thick fills."""
    im = im.convert("RGBA")
    w, h = im.size
    for _ in range(2):
        src = im.copy()
        sp = src.load()
        px = im.load()
        for y in range(h):
            for x in range(w):
                r, g, b, a = sp[x, y]
                if a == 0:
                    continue
                near = any(
                    0 <= x + dx < w
                    and 0 <= y + dy < h
                    and sp[x + dx, y + dy][3] == 0
                    for dy in (-1, 0, 1)
                    for dx in (-1, 0, 1)
                    if not (dx == 0 and dy == 0)
                )
                if not near:
                    continue
                if is_magenta(r, g, b):
                    px[x, y] = (0, 0, 0, 0)
                    continue
                sat = max(r, g, b) - min(r, g, b)
                lu = luma(r, g, b)
                if not (lu >= 190 and sat <= 28):
                    continue
                opaque_n = sum(
                    1
                    for dy in (-1, 0, 1)
                    for dx in (-1, 0, 1)
                    if not (dx == 0 and dy == 0)
                    and 0 <= x + dx < w
                    and 0 <= y + dy < h
                    and sp[x + dx, y + dy][3] > 200
                )
                if opaque_n <= 5:
                    px[x, y] = (0, 0, 0, 0)
    return im


def process_sprite(im: Image.Image, size: int = 256) -> Image.Image:
    im = im.convert("RGBA")
    # Speed: knock out on <=512 masters, then nearest to game size
    max_side = max(im.size)
    if max_side > 512:
        scale = 512 / max_side
        im = im.resize(
            (max(1, int(im.width * scale)), max(1, int(im.height * scale))),
            Image.Resampling.NEAREST,
        )
    out = knockout(im)
    out = to_square(out, size=size)
    # Second pass catches plate left after resize; still edge-only / magenta-safe
    out = knockout(out)
    out = strip_edge_halo(out)
    return harden_alpha(out)
