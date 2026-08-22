"""Touch-friendly mute + music/SFX volume controls."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import pygame

from config import SCALE
from core import audio
from core.platform import load_font

ACCENT = (255, 105, 180)
HUD = (245, 235, 210)
PANEL = (20, 24, 40, 200)
OK = (120, 220, 160)
MUTED = (255, 80, 80)


@dataclass
class _Btn:
    rect: pygame.Rect
    kind: str  # mute | music_down | music_up | sfx_down | sfx_up


class AudioPanel:
    """Compact panel: [MUTE]  MUSIC [-][bar][+]  SFX [-][bar][+]"""

    def __init__(self, top_right: tuple[int, int], scale: float = 1.0) -> None:
        self._font = load_font(max(18, int(28 * scale)))
        self._font_sm = load_font(max(16, int(22 * scale)))
        self.buttons: list[_Btn] = []
        self._cache: Optional[pygame.Surface] = None
        self._cache_key: Optional[tuple] = None
        self._layout(top_right, scale)

    def _layout(self, top_right: tuple[int, int], scale: float) -> None:
        right, top = top_right
        # Match half-res web canvas so panel geometry tracks font scaling.
        s = scale * SCALE
        pad = int(12 * s)
        btn_h = int(52 * s)
        mute_w = int(120 * s)
        step_w = int(56 * s)
        bar_w = int(140 * s)
        gap = int(10 * s)

        # Row width from right edge
        x = right
        y = top

        mute = pygame.Rect(0, y, mute_w, btn_h)
        mute.right = x
        self.mute_rect = mute

        # Music row below
        y2 = y + btn_h + gap
        y3 = y2 + btn_h + gap

        music_up = pygame.Rect(0, y2, step_w, btn_h)
        music_up.right = x
        music_bar = pygame.Rect(0, y2, bar_w, btn_h)
        music_bar.right = music_up.left - gap
        music_down = pygame.Rect(0, y2, step_w, btn_h)
        music_down.right = music_bar.left - gap

        sfx_up = pygame.Rect(0, y3, step_w, btn_h)
        sfx_up.right = x
        sfx_bar = pygame.Rect(0, y3, bar_w, btn_h)
        sfx_bar.right = sfx_up.left - gap
        sfx_down = pygame.Rect(0, y3, step_w, btn_h)
        sfx_down.right = sfx_bar.left - gap

        self.music_bar = music_bar
        self.sfx_bar = sfx_bar
        self.panel_rect = pygame.Rect(
            min(mute.left, music_down.left, sfx_down.left) - pad,
            y - pad,
            0,
            0,
        )
        self.panel_rect.width = right - self.panel_rect.left + pad
        self.panel_rect.height = (y3 + btn_h) - self.panel_rect.top + pad

        self.buttons = [
            _Btn(mute, "mute"),
            _Btn(music_down, "music_down"),
            _Btn(music_up, "music_up"),
            _Btn(sfx_down, "sfx_down"),
            _Btn(sfx_up, "sfx_up"),
        ]

    def contains(self, pos: tuple[int, int]) -> bool:
        return self.panel_rect.collidepoint(pos)

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Return True if a control consumed the click."""
        now = time.time()
        # Android SDL emits both MOUSEBUTTONDOWN and FINGERDOWN for one tap.
        if now - getattr(self, "_last_click_ts", 0.0) < 0.12:
            # Only swallow duplicates when the prior click actually hit a control.
            return bool(getattr(self, "_last_click_hit", False))
        for btn in self.buttons:
            if btn.rect.collidepoint(pos):
                self._last_click_ts = now
                self._last_click_hit = True
                if btn.kind == "mute":
                    audio.toggle_mute()
                    if not audio.is_muted():
                        audio.play("ui_blip")
                elif btn.kind == "music_down":
                    audio.nudge_music_volume(-0.1)
                    audio.play("ui_blip")
                elif btn.kind == "music_up":
                    audio.nudge_music_volume(0.1)
                    audio.play("ui_blip")
                elif btn.kind == "sfx_down":
                    audio.nudge_sfx_volume(-0.1)
                    audio.play("ui_blip")
                elif btn.kind == "sfx_up":
                    audio.nudge_sfx_volume(0.1)
                    audio.play("ui_blip")
                return True
        self._last_click_hit = False
        return False

    def draw(self, surface: pygame.Surface) -> None:
        settings = audio.get_settings()
        key = (
            bool(settings.muted),
            round(float(settings.music_volume), 2),
            round(float(settings.sfx_volume), 2),
        )
        if self._cache is None or self._cache_key != key:
            layer = pygame.Surface(self.panel_rect.size, pygame.SRCALPHA)
            layer.fill(PANEL)
            origin = self.panel_rect.topleft

            def local(rect: pygame.Rect) -> pygame.Rect:
                return rect.move(-origin[0], -origin[1])

            mute_label = "UNMUTE" if settings.muted else "MUTE"
            mute_color = MUTED if settings.muted else OK
            self._draw_btn(layer, local(self.mute_rect), mute_label, mute_color)
            for btn in self.buttons:
                if btn.kind == "mute":
                    continue
                label = "-" if btn.kind.endswith("down") else "+"
                self._draw_btn(layer, local(btn.rect), label, HUD)
            self._draw_bar(
                layer, local(self.music_bar), "MUSIC", settings.music_volume, settings.muted
            )
            self._draw_bar(layer, local(self.sfx_bar), "SFX", settings.sfx_volume, settings.muted)
            self._cache = layer
            self._cache_key = key
        surface.blit(self._cache, self.panel_rect.topleft)

    def _draw_btn(
        self, surface: pygame.Surface, rect: pygame.Rect, label: str, color: tuple[int, int, int]
    ) -> None:
        pygame.draw.rect(surface, (40, 48, 70), rect, border_radius=10)
        pygame.draw.rect(surface, color, rect, width=2, border_radius=10)
        text = self._font.render(label, True, color)
        surface.blit(text, text.get_rect(center=rect.center))

    def _draw_bar(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        value: float,
        muted: bool,
    ) -> None:
        pygame.draw.rect(surface, (40, 48, 70), rect, border_radius=10)
        pygame.draw.rect(surface, ACCENT, rect, width=2, border_radius=10)
        fill = rect.inflate(-10, -18)
        fill.width = max(0, int(fill.width * (0.0 if muted else value)))
        if fill.width > 0:
            pygame.draw.rect(surface, ACCENT, fill, border_radius=6)
        caption = self._font_sm.render(label, True, HUD)
        surface.blit(caption, caption.get_rect(center=rect.center))


class MuteChip:
    """Tiny in-game mute toggle."""

    def __init__(self, topleft: tuple[int, int]) -> None:
        self._font = load_font(28)
        w, h = max(1, int(110 * SCALE)), max(1, int(48 * SCALE))
        self.rect = pygame.Rect(topleft[0], topleft[1], w, h)
        self._last_click_ts = 0.0
        self._cache: Optional[pygame.Surface] = None
        self._cache_muted: Optional[bool] = None

    def handle_click(self, pos: tuple[int, int]) -> bool:
        if not self.rect.collidepoint(pos):
            return False
        now = time.time()
        if now - self._last_click_ts < 0.12:
            return True
        self._last_click_ts = now
        audio.toggle_mute()
        if not audio.is_muted():
            audio.play("ui_blip")
        return True

    def draw(self, surface: pygame.Surface) -> None:
        muted = audio.is_muted()
        if self._cache is None or self._cache_muted != muted:
            color = MUTED if muted else OK
            chip = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            chip.fill((20, 24, 40, 180))
            pygame.draw.rect(chip, color, chip.get_rect(), width=2, border_radius=10)
            label = "MUTED" if muted else "MUTE"
            text = self._font.render(label, True, color)
            chip.blit(text, text.get_rect(center=chip.get_rect().center))
            self._cache = chip
            self._cache_muted = muted
        surface.blit(self._cache, self.rect.topleft)


class PauseChip:
    """Tiny in-game pause toggle."""

    def __init__(self, topleft: tuple[int, int]) -> None:
        self._font = load_font(28)
        w, h = max(1, int(110 * SCALE)), max(1, int(48 * SCALE))
        self.rect = pygame.Rect(topleft[0], topleft[1], w, h)
        self._last_click_ts = 0.0
        self._cache: Optional[pygame.Surface] = None

    def handle_click(self, pos: tuple[int, int]) -> bool:
        if not self.rect.collidepoint(pos):
            return False
        now = time.time()
        if now - self._last_click_ts < 0.12:
            return True
        self._last_click_ts = now
        return True

    def draw(self, surface: pygame.Surface) -> None:
        if self._cache is None:
            chip = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            chip.fill((20, 24, 40, 180))
            pygame.draw.rect(chip, OK, chip.get_rect(), width=2, border_radius=10)
            text = self._font.render("PAUSE", True, OK)
            chip.blit(text, text.get_rect(center=chip.get_rect().center))
            self._cache = chip
        surface.blit(self._cache, self.rect.topleft)


class HoldChip:
    """HUD chip that fires only after being held for ``hold_seconds`` (anti-mis-tap)."""

    def __init__(
        self,
        topleft: tuple[int, int],
        label: str = "TITLE",
        hold_seconds: float = 0.4,
        width: int | None = None,
    ) -> None:
        self._font = load_font(28)
        self.label = label
        self.hold_seconds = float(hold_seconds)
        w = max(1, int((width if width is not None else 110) * SCALE))
        h = max(1, int(48 * SCALE))
        self.rect = pygame.Rect(topleft[0], topleft[1], w, h)
        self._holding = False
        self._hold = 0.0
        self._armed = False  # True for one frame when hold completes

    def begin_hold(self, pos: tuple[int, int]) -> bool:
        if not self.rect.collidepoint(pos):
            return False
        self._holding = True
        self._hold = 0.0
        self._armed = False
        return True

    def end_hold(self) -> None:
        self._holding = False
        self._hold = 0.0

    def update(self, dt: float) -> bool:
        """Advance hold; return True once when threshold reached."""
        self._armed = False
        if not self._holding:
            return False
        self._hold += dt
        if self._hold >= self.hold_seconds:
            self._holding = False
            self._hold = 0.0
            self._armed = True
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        color = ACCENT if self._holding else OK
        chip = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        chip.fill((20, 24, 40, 180))
        pygame.draw.rect(chip, color, chip.get_rect(), width=2, border_radius=10)
        if self._holding and self.hold_seconds > 0:
            frac = min(1.0, self._hold / self.hold_seconds)
            fill = pygame.Rect(0, 0, int(self.rect.width * frac), self.rect.height)
            fill_surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            fill_surf.fill((*ACCENT[:3], 70))
            chip.blit(fill_surf, (0, 0), fill)
        text = self._font.render(self.label, True, color)
        chip.blit(text, text.get_rect(center=chip.get_rect().center))
        surface.blit(chip, self.rect.topleft)
