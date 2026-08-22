"""Pause menu + gameplay music pause helpers."""

from __future__ import annotations

import unittest
from unittest import mock

import pygame

from core import audio
from core.audio_ui import PauseChip
from core.input import InputState
from core.pause_ui import PauseMenu
from games.booth_blaster import BoothBlaster, TitleScene


class GameplayMusicPauseTests(unittest.TestCase):
    def test_pause_resume_do_not_flip_mute(self) -> None:
        audio._initialized = True
        audio._settings.muted = False
        with (
            mock.patch.object(pygame.mixer.music, "pause") as paused,
            mock.patch.object(pygame.mixer.music, "unpause") as unpaused,
        ):
            audio.pause_gameplay_music()
            audio.resume_gameplay_music()
        paused.assert_called_once()
        unpaused.assert_called_once()
        self.assertFalse(audio._settings.muted)

    def test_pause_is_noop_when_muted(self) -> None:
        audio._initialized = True
        audio._settings.muted = True
        with mock.patch.object(pygame.mixer.music, "pause") as paused:
            audio.pause_gameplay_music()
        paused.assert_not_called()


class PauseMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass

    def test_hit_test_three_actions(self) -> None:
        menu = PauseMenu()
        self.assertEqual(menu.hit_test(menu.button_rects[0].center), PauseMenu.CONTINUE)
        self.assertEqual(menu.hit_test(menu.button_rects[1].center), PauseMenu.TITLE)
        self.assertEqual(menu.hit_test(menu.button_rects[2].center), PauseMenu.QUIT)
        self.assertIsNone(menu.hit_test((0, 0)))

    def test_move_wraps(self) -> None:
        menu = PauseMenu()
        self.assertEqual(menu.choice, 0)
        menu.move(1)
        self.assertEqual(menu.choice, 1)
        menu.move(1)
        self.assertEqual(menu.choice, 2)
        menu.move(1)
        self.assertEqual(menu.choice, 0)
        menu.move(-1)
        self.assertEqual(menu.choice, 2)
        self.assertEqual(menu.confirm(), PauseMenu.QUIT)


class InputPauseEdgeTests(unittest.TestCase):
    def test_input_state_has_edges(self) -> None:
        inp = InputState()
        self.assertFalse(inp.start_pressed)
        self.assertFalse(inp.pause_pressed)


class PauseChipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    def test_click_inside_and_miss(self) -> None:
        chip = PauseChip((40, 100))
        self.assertTrue(chip.handle_click(chip.rect.center))
        self.assertFalse(chip.handle_click((0, 0)))


class BoothBlasterPauseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass

    def test_pause_freezes_player(self) -> None:
        game = BoothBlaster()
        game._assets_ready = True
        x0 = game.player.x
        game._open_pause()
        nxt = game.update(0.05, InputState(move_x=1.0, aim_x=x0 + 200))
        self.assertIs(nxt, game)
        self.assertTrue(game._paused)
        self.assertEqual(game.player.x, x0)

    def test_title_action_returns_title_scene(self) -> None:
        game = BoothBlaster()
        game._assets_ready = True
        game._open_pause()
        nxt = game._apply_pause_action(PauseMenu.TITLE)
        self.assertIsInstance(nxt, TitleScene)
        self.assertFalse(game.exit_requested)

    def test_quit_action_requests_exit(self) -> None:
        game = BoothBlaster()
        game._assets_ready = True
        nxt = game._apply_pause_action(PauseMenu.QUIT)
        self.assertIsNone(nxt)
        self.assertTrue(game.exit_requested)

    def test_exit_ready_still_quits_while_paused(self) -> None:
        game = BoothBlaster()
        game._assets_ready = True
        game._open_pause()
        nxt = game.update(0.05, InputState(exit_ready=True))
        self.assertIsNone(nxt)
        self.assertTrue(game.exit_requested)
