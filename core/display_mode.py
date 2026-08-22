"""Pure helpers for picking a pygame fullscreen buffer size."""

from __future__ import annotations


def resolve_fullscreen_mode(
    logical: tuple[int, int],
    desktop: tuple[int, int],
) -> tuple[tuple[int, int], bool]:
    """Keep the pygame buffer at *logical* size; ask SDL to scale on larger TVs.

    The booth stage TV is 2160×3840 (4K rotated). Opening a matching pygame
    surface forces a CPU scale of the 1080×1920 canvas every frame (~13ms on
    a Pi 5). Integer 2× SDL SCALED avoids that.
    """
    lw, lh = logical
    dw, dh = desktop
    if lw <= 0 or lh <= 0:
        return logical, False
    use_scaled = dw > lw or dh > lh
    return (lw, lh), use_scaled
