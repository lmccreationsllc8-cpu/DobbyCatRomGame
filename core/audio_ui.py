"""Touch-friendly mute + music/SFX volume controls."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pygame

from core import audio
from core.platform import load_font, writable_data_dir

ACCENT = (255, 105, 180)
HUD = (245, 235, 210)
PANEL = (20, 24, 40, 200)
OK = (120, 220, 160)
MUTED = (255, 80, 80)


# #region agent log
def _agent_log(hypothesis_id: str, message: str, data: dict | None = None) -> None:
    payload = {
        "sessionId": "b4844d",
        "runId": "mute-pre",
        "hypothesisId": hypothesis_id,
        "location": "audio_ui.py",
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload)
    print(f"AGENT_DEBUG {line}", flush=True)
    for path in (writable_data_dir() / "debug-b4844d.log", Path("debug-b4844d.log")):
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


# #endregion


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
        self._layout(top_right, scale)

    def _layout(self, top_right: tuple[int, int], scale: float) -> None:
        right, top = top_right
        pad = int(12 * scale)
        btn_h = int(52 * scale)
        mute_w = int(120 * scale)
        step_w = int(56 * scale)
        bar_w = int(140 * scale)
        gap = int(10 * scale)

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
        # #region agent log
        _agent_log(
            "A",
            "AudioPanel layout",
            {
                "mute": list(mute),
                "panel": list(self.panel_rect),
                "top_right": list(top_right),
            },
        )
        # #endregion

    def contains(self, pos: tuple[int, int]) -> bool:
        return self.panel_rect.collidepoint(pos)

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Return True if a control consumed the click."""
        now = time.time()
        # Android SDL emits both MOUSEBUTTONDOWN and FINGERDOWN for one tap.
        if now - getattr(self, "_last_click_ts", 0.0) < 0.12:
            # Only swallow duplicates when the prior click actually hit a control.
            # #region agent log
            _agent_log("E", "AudioPanel debounce skip", {"pos": list(pos)})
            # #endregion
            return bool(getattr(self, "_last_click_hit", False))
        hits = [btn.kind for btn in self.buttons if btn.rect.collidepoint(pos)]
        # #region agent log
        _agent_log(
            "A",
            "AudioPanel.handle_click",
            {
                "pos": list(pos),
                "hits": hits,
                "in_panel": self.panel_rect.collidepoint(pos),
                "muted_before": audio.is_muted(),
            },
        )
        # #endregion
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
                # #region agent log
                _agent_log(
                    "B",
                    "AudioPanel action",
                    {
                        "kind": btn.kind,
                        "muted_after": audio.is_muted(),
                        "settings": audio.get_settings().__dict__,
                    },
                )
                # #endregion
                return True
        self._last_click_hit = False
        return False

    def draw(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface(self.panel_rect.size, pygame.SRCALPHA)
        overlay.fill(PANEL)
        surface.blit(overlay, self.panel_rect.topleft)

        settings = audio.get_settings()
        mute_label = "UNMUTE" if settings.muted else "MUTE"
        mute_color = MUTED if settings.muted else OK
        self._draw_btn(surface, self.mute_rect, mute_label, mute_color)

        for btn in self.buttons:
            if btn.kind == "mute":
                continue
            label = "-" if btn.kind.endswith("down") else "+"
            self._draw_btn(surface, btn.rect, label, HUD)

        self._draw_bar(surface, self.music_bar, "MUSIC", settings.music_volume, settings.muted)
        self._draw_bar(surface, self.sfx_bar, "SFX", settings.sfx_volume, settings.muted)

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
        w, h = 110, 48
        self.rect = pygame.Rect(topleft[0], topleft[1], w, h)
        self._last_click_ts = 0.0

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
        color = MUTED if muted else OK
        chip = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        chip.fill((20, 24, 40, 180))
        surface.blit(chip, self.rect.topleft)
        pygame.draw.rect(surface, color, self.rect, width=2, border_radius=10)
        label = "MUTED" if muted else "MUTE"
        text = self._font.render(label, True, color)
        surface.blit(text, text.get_rect(center=self.rect.center))
