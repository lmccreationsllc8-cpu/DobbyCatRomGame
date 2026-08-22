"""Kiosk fullscreen must keep a logical pygame buffer on a 4K TV."""

from __future__ import annotations

import unittest

from core.display_mode import resolve_fullscreen_mode


class ResolveFullscreenModeTests(unittest.TestCase):
    def test_4k_tv_keeps_logical_buffer_and_asks_sdl_to_scale(self) -> None:
        size, scaled = resolve_fullscreen_mode((1080, 1920), (2160, 3840))
        self.assertEqual(size, (1080, 1920))
        self.assertTrue(scaled)

    def test_matching_desktop_skips_scaled(self) -> None:
        size, scaled = resolve_fullscreen_mode((1080, 1920), (1080, 1920))
        self.assertEqual(size, (1080, 1920))
        self.assertFalse(scaled)
