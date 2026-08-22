"""In-run pause overlay: Continue / Return to title / Quit."""

from __future__ import annotations

import time
from typing import Optional

import pygame

from config import HEIGHT, SCALE, WIDTH
from core import audio
from core.platform import load_font

ACCENT = (255, 105, 180)
HUD = (245, 235, 210)
OK = (120, 220, 160)
PANEL = (20, 24, 40, 210)


def _sx(value: float) -> int:
    return max(1, int(round(value * SCALE)))


class PauseMenu:
    CONTINUE = "continue"
    TITLE = "title"
    QUIT = "quit"
    _ACTIONS = (CONTINUE, TITLE, QUIT)
    _LABELS = ("Continue", "Return to title", "Quit")

    def __init__(self) -> None:
        self._font = load_font(40)
        self._font_lg = load_font(72, bold=True)
        self.choice = 0
        self.button_rects: list[pygame.Rect] = []
        self.panel_rect = pygame.Rect(0, 0, 1, 1)
        self._last_click_ts = 0.0
        self._click_debounce_s = 0.28
        self._layout()

    def _layout(self) -> None:
        bw, bh, gap = _sx(640), _sx(110), _sx(28)
        total_h = 3 * bh + 2 * gap
        top = HEIGHT // 2 - total_h // 2 + _sx(40)
        cx = WIDTH // 2
        self.button_rects = []
        for i in range(3):
            rect = pygame.Rect(0, 0, bw, bh)
            rect.centerx = cx
            rect.top = top + i * (bh + gap)
            self.button_rects.append(rect)
        pad = _sx(36)
        self.panel_rect = pygame.Rect(
            self.button_rects[0].left - pad,
            self.button_rects[0].top - _sx(160),
            bw + pad * 2,
            total_h + _sx(200),
        )

    def hit_test(self, pos: tuple[int, int]) -> Optional[str]:
        for i, rect in enumerate(self.button_rects):
            if rect.collidepoint(pos):
                return self._ACTIONS[i]
        return None

    def move(self, direction: int) -> None:
        if direction == 0:
            return
        self.choice = (self.choice + (1 if direction > 0 else -1)) % 3
        audio.play("ui_blip")

    def confirm(self) -> str:
        return self._ACTIONS[self.choice]

    def handle_click(self, pos: tuple[int, int]) -> Optional[str]:
        action = self.hit_test(pos)
        if action is None:
            return None
        now = time.time()
        if now - self._last_click_ts < self._click_debounce_s:
            return None
        self._last_click_ts = now
        self.choice = self._ACTIONS.index(action)
        return action

    def draw(self, surface: pygame.Surface) -> None:
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        surface.blit(dim, (0, 0))
        panel = pygame.Surface(self.panel_rect.size, pygame.SRCALPHA)
        panel.fill(PANEL)
        surface.blit(panel, self.panel_rect.topleft)
        title = self._font_lg.render("PAUSED", True, ACCENT)
        surface.blit(title, title.get_rect(center=(WIDTH // 2, self.panel_rect.top + _sx(80))))
        for i, (rect, label) in enumerate(zip(self.button_rects, self._LABELS)):
            selected = self.choice == i
            color = OK if selected else HUD
            pygame.draw.rect(surface, color, rect, width=3 if selected else 2, border_radius=_sx(12))
            txt = self._font.render(label, True, color)
            surface.blit(txt, txt.get_rect(center=rect.center))
