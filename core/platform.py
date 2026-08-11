"""Android / desktop / web runtime helpers for Booth Blaster."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pygame

import config

# Bundled monospace font for Android (SysFont consolas is missing there).
FONT_CANDIDATES = (
    config.ASSETS_DIR / "fonts" / "game_font.ttf",
    config.ASSETS_DIR / "fonts" / "DejaVuSansMono.ttf",
    config.ASSETS_DIR / "fonts" / "PressStart2P.ttf",
)


def is_web() -> bool:
    """True when running under pygbag / pygame-wasm (browser)."""
    return sys.platform == "emscripten"


def is_android() -> bool:
    """True when running under python-for-android / Buildozer."""
    if is_web():
        return False
    if os.environ.get("ANDROID_ARGUMENT") is not None:
        return True
    if os.environ.get("ANDROID_PRIVATE") is not None:
        return True
    if os.environ.get("ANDROID_APP_PATH") is not None:
        return True
    try:
        import android  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


def is_mobile_runtime() -> bool:
    """Phone-oriented runtime (Android APK or browser on phone/tablet)."""
    return is_android() or is_web()


def writable_data_dir() -> Path:
    """App-private writable directory for leaderboard JSON etc."""
    # RCARS kiosk / Pi: prefer env so the game tree under /opt can stay read-only.
    override = (os.environ.get("DOBBY_DATA_DIR") or "").strip()
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path
    if is_android():
        for key in ("ANDROID_PRIVATE", "ANDROID_APP_PATH"):
            raw = os.environ.get(key)
            if raw:
                path = Path(raw)
                path.mkdir(parents=True, exist_ok=True)
                return path
        # Fallback used by some p4a bootstraps
        path = Path("/data/data/org.dobbycat.boothblaster/files")
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            pass
    path = config.ROOT / "data"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def leaderboard_path() -> Path:
    return writable_data_dir() / "leaderboard.json"


def apply_android_runtime_tweaks() -> None:
    """Back-compat alias for apply_mobile_runtime_tweaks()."""
    apply_mobile_runtime_tweaks()


def apply_mobile_runtime_tweaks() -> None:
    """Adjust config for phone/web (idle timeout, display). Call before main loop."""
    if is_web():
        # Arcade idle quit is wrong in a browser tab.
        config.IDLE_QUIT_SECONDS = 86_400.0
        config.FULLSCREEN = False
        # 1080x1920 WASM draws are heavy; 30 FPS keeps the tab responsive.
        config.FPS = 30
        config.LEADERBOARD_PATH = leaderboard_path()
        _apply_web_browser_smoothness()
        return
    if not is_android():
        return
    # Arcade 90s idle quit is wrong on a phone — effectively disable.
    config.IDLE_QUIT_SECONDS = 86_400.0
    config.FULLSCREEN = True
    config.LEADERBOARD_PATH = leaderboard_path()


def _apply_web_browser_smoothness() -> None:
    """Web-only DOM/CSS tweaks for smoother phone-browser play (no Android impact)."""
    try:
        import platform as _plat

        # Keep chunky pixel look when the canvas is CSS-scaled.
        canvas = _plat.window.canvas
        canvas.style.imageRendering = "pixelated"
        canvas.style.touchAction = "none"
        canvas.style.userSelect = "none"
        canvas.style.webkitUserSelect = "none"
        canvas.style.webkitTouchCallout = "none"

        doc = getattr(_plat.window, "document", None)
        if doc is not None:
            for tag in ("html", "body"):
                try:
                    el = doc.getElementsByTagName(tag)[0]
                    el.style.margin = "0"
                    el.style.padding = "0"
                    el.style.overflow = "hidden"
                    el.style.overscrollBehavior = "none"
                    el.style.touchAction = "none"
                    el.style.userSelect = "none"
                    el.style.webkitUserSelect = "none"
                    el.style.background = "#000"
                except Exception:
                    pass
            # Long-press / right-click menus steal focus on mobile Safari.
            try:
                doc.addEventListener("contextmenu", lambda e: e.preventDefault())
            except Exception:
                pass
    except Exception:
        pass


def web_tab_hidden() -> bool:
    """True when the browser tab is in the background (web only)."""
    if not is_web():
        return False
    try:
        import platform as _plat

        doc = getattr(_plat.window, "document", None)
        if doc is None:
            return False
        return bool(getattr(doc, "hidden", False))
    except Exception:
        return False


def mixer_frequency() -> int:
    """Mixer sample rate — keep in sync with generated assets (44.1 kHz)."""
    return 44100


def mixer_buffer() -> int:
    """Larger buffer is more stable on Android Bluetooth / weak devices / WASM.

    pygbag/WebAudio underruns with the pygame default (512) sound like crackle /
    distortion; use a generous buffer on web and mobile.
    """
    if is_web():
        return 8192
    if is_android():
        return 4096
    return 512


def load_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Load bundled TTF; fall back to SysFont only on desktop.

    On web the canvas is half-res (config.SCALE=0.5); shrink pt size so UI
    is not double-zoomed when CSS scales the canvas back up.
    """
    try:
        from config import SCALE

        if SCALE != 1.0:
            size = max(8, int(round(float(size) * SCALE)))
    except Exception:
        pass
    for path in FONT_CANDIDATES:
        if path.is_file():
            try:
                font = pygame.font.Font(str(path), size)
                if bold and hasattr(font, "set_bold"):
                    font.set_bold(True)
                return font
            except pygame.error:
                continue
    name = "consolas"
    try:
        return pygame.font.SysFont(name, size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


def _fullscreen_display_index() -> int:
    """SDL/pygame display index for stage TV (launcher sets SDL_VIDEO_FULLSCREEN_DISPLAY)."""
    for key in ("SDL_VIDEO_FULLSCREEN_DISPLAY", "DOBBY_GAME_DISPLAY_INDEX"):
        raw = (os.environ.get(key) or "").strip()
        if not raw:
            continue
        try:
            return max(0, int(raw))
        except ValueError:
            continue
    return 0


def _desktop_size_for(display: int, fallback: tuple[int, int]) -> tuple[int, int]:
    try:
        sizes = pygame.display.get_desktop_sizes()
        if 0 <= display < len(sizes):
            w, h = sizes[display]
            if w > 0 and h > 0:
                return int(w), int(h)
    except (pygame.error, AttributeError, TypeError, IndexError):
        pass
    try:
        info = pygame.display.Info()
        if info.current_w > 0 and info.current_h > 0:
            return int(info.current_w), int(info.current_h)
    except pygame.error:
        pass
    return fallback


def _set_mode_fullscreen(size: tuple[int, int], display: int) -> pygame.Surface:
    """Fullscreen on a specific monitor (stage TV). Never silently retarget display 0."""
    try:
        return pygame.display.set_mode(size, pygame.FULLSCREEN, display=display)
    except TypeError:
        # Older pygame without display= — rely on SDL_VIDEO_FULLSCREEN_DISPLAY / WINDOW_POS.
        return pygame.display.set_mode(size, pygame.FULLSCREEN)
    except pygame.error:
        # Retry once without an explicit index; env WINDOW_POS may still place it.
        return pygame.display.set_mode(size, pygame.FULLSCREEN)


def create_display(logical_size: tuple[int, int]) -> pygame.Surface:
    """Fullscreen on Android/Pi stage TV; logical canvas on web; scaled on desktop."""
    width, height = logical_size
    if is_web():
        # Browser canvas is CSS-scaled by the pygbag template; keep native logical size.
        return pygame.display.set_mode(logical_size)
    if is_android() or config.FULLSCREEN:
        display = _fullscreen_display_index()
        # Prefer that monitor's native size (Info() alone is often the primary/touch bar).
        size = _desktop_size_for(display, logical_size)
        return _set_mode_fullscreen(size, display)

    info = pygame.display.Info()
    max_w, max_h = max(320, info.current_w - 80), max(480, info.current_h - 80)
    scale = min(1.0, max_w / width, max_h / height)
    window_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return pygame.display.set_mode(window_size)
