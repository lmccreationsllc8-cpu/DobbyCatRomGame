"""Touch alphabet picker for high-score initials."""

from __future__ import annotations

import time
from typing import Callable, Optional

import pygame

from core import audio
from core.platform import load_font

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
ACCENT = (255, 105, 180)
HUD = (245, 235, 210)
OK = (120, 220, 160)
PANEL = (20, 24, 40, 210)
BTN = (40, 48, 70)

class InitialsPicker:
    """3 letter slots + A–Z/0–9 grid + DONE."""

    COLS = 6
    ROWS = 6

    def __init__(self, center: tuple[int, int], width: int = 920) -> None:
        self._font = load_font(40)
        self._font_lg = load_font(72, bold=True)
        self._font_sm = load_font(28)
        self.center = center
        self.width = width
        self.slot_rects: list[pygame.Rect] = []
        self.cell_rects: list[tuple[str, pygame.Rect]] = []
        self.done_rect = pygame.Rect(0, 0, 1, 1)
        self.panel_rect = pygame.Rect(0, 0, 1, 1)
        self._last_click_ts = 0.0
        self._layout()

    def _layout(self) -> None:
        cx, cy = self.center
        pad = 16
        cell = 96
        gap = 12
        grid_w = self.COLS * cell + (self.COLS - 1) * gap
        grid_h = self.ROWS * cell + (self.ROWS - 1) * gap
        slot_w, slot_h = 120, 110
        slot_gap = 28
        slots_w = 3 * slot_w + 2 * slot_gap

        # Slots above grid
        slots_y = cy - grid_h // 2 - slot_h - 48
        slots_x0 = cx - slots_w // 2
        self.slot_rects = [
            pygame.Rect(slots_x0 + i * (slot_w + slot_gap), slots_y, slot_w, slot_h) for i in range(3)
        ]

        grid_x0 = cx - grid_w // 2
        grid_y0 = cy - grid_h // 2 + 20
        self.cell_rects = []
        for i, ch in enumerate(ALPHABET):
            r = i // self.COLS
            c = i % self.COLS
            rect = pygame.Rect(
                grid_x0 + c * (cell + gap),
                grid_y0 + r * (cell + gap),
                cell,
                cell,
            )
            self.cell_rects.append((ch, rect))

        self.done_rect = pygame.Rect(0, 0, 280, 88)
        self.done_rect.centerx = cx
        self.done_rect.top = grid_y0 + grid_h + 28

        top = self.slot_rects[0].top - pad
        bottom = self.done_rect.bottom + pad
        left = min(grid_x0, slots_x0) - pad
        right = max(grid_x0 + grid_w, slots_x0 + slots_w) + pad
        self.panel_rect = pygame.Rect(left, top, right - left, bottom - top)

    def handle_click(
        self,
        pos: tuple[int, int],
        initials: list[str],
        initial_idx: int,
        on_done: Callable[[], None],
    ) -> tuple[bool, int]:
        """
        Apply a tap. Returns (consumed, new_initial_idx).
        Mutates initials in place when a letter is chosen.
        """
        now = time.time()
        if now - self._last_click_ts < 0.12:
            return True, initial_idx

        for i, rect in enumerate(self.slot_rects):
            if rect.collidepoint(pos):
                self._last_click_ts = now
                audio.play("ui_blip")
                return True, i

        for ch, rect in self.cell_rects:
            if rect.collidepoint(pos):
                self._last_click_ts = now
                initials[initial_idx] = ch
                audio.play("ui_blip")
                next_idx = min(2, initial_idx + 1) if initial_idx < 2 else initial_idx
                return True, next_idx

        if self.done_rect.collidepoint(pos):
            self._last_click_ts = now
            on_done()
            return True, initial_idx

        if self.panel_rect.collidepoint(pos):
            self._last_click_ts = now
            return True, initial_idx
        return False, initial_idx

    def draw(self, surface: pygame.Surface, initials: list[str], initial_idx: int) -> None:
        overlay = pygame.Surface(self.panel_rect.size, pygame.SRCALPHA)
        overlay.fill(PANEL)
        surface.blit(overlay, self.panel_rect.topleft)
        pygame.draw.rect(surface, ACCENT, self.panel_rect, width=2, border_radius=16)

        tip = self._font_sm.render(
            "Move on the grid — confirm for next letter — DONE to save",
            True,
            HUD,
        )
        surface.blit(tip, tip.get_rect(midbottom=(self.panel_rect.centerx, self.slot_rects[0].top - 10)))

        for i, rect in enumerate(self.slot_rects):
            active = i == initial_idx
            border = ACCENT if active else HUD
            pygame.draw.rect(surface, BTN, rect, border_radius=12)
            pygame.draw.rect(surface, border, rect, width=3 if active else 2, border_radius=12)
            letter = self._font_lg.render(initials[i], True, OK if active else HUD)
            surface.blit(letter, letter.get_rect(center=rect.center))

        for ch, rect in self.cell_rects:
            selected = initials[initial_idx] == ch
            pygame.draw.rect(surface, BTN, rect, border_radius=10)
            pygame.draw.rect(surface, ACCENT if selected else HUD, rect, width=2, border_radius=10)
            text = self._font.render(ch, True, ACCENT if selected else HUD)
            surface.blit(text, text.get_rect(center=rect.center))

        pygame.draw.rect(surface, BTN, self.done_rect, border_radius=14)
        pygame.draw.rect(surface, OK, self.done_rect, width=3, border_radius=14)
        done = self._font_lg.render("DONE", True, OK)
        surface.blit(done, done.get_rect(center=self.done_rect.center))
