"""Campaign boss roster and projectile typing."""

from __future__ import annotations

import unittest

import pygame

from games.booth_blaster import (
    CAMPAIGN_WAVES,
    EnemyKind,
    BoothBlaster,
    Bolt,
    PLAYER_SKINS,
    PRACTICE_SKINS,
    _PARENT_KINDS,
    boss_shoot_rate,
    boss_step_interval,
    is_practice_skin,
    load_player_skin_index,
    player_skin_filename,
    save_player_skin_index,
)


class CampaignBossTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass

    def test_spawn_boss_by_wave(self) -> None:
        game = BoothBlaster(from_title=False)
        game.wave.index = 1
        game._spawn_boss()
        self.assertEqual([e.kind for e in game.enemies], [EnemyKind.BOSS])

        game.wave.index = 2
        game._spawn_boss()
        self.assertEqual([e.kind for e in game.enemies], [EnemyKind.BOSS_KITTEN])

        game.wave.index = 3
        game._spawn_boss()
        self.assertEqual([e.kind for e in game.enemies], [EnemyKind.BOSS_NANA])

        game.wave.index = 4
        game._spawn_boss()
        kinds = [e.kind for e in game.enemies]
        self.assertEqual(set(kinds), {EnemyKind.BOSS_PARENT_A, EnemyKind.BOSS_PARENT_B})
        self.assertEqual(len(kinds), 2)

    def test_final_wave_is_boss_only(self) -> None:
        game = BoothBlaster(from_title=False)
        game.wave.index = CAMPAIGN_WAVES
        game._spawn_wave(CAMPAIGN_WAVES)
        self.assertTrue(game.wave.boss_active)
        kinds = {e.kind for e in game.enemies}
        self.assertEqual(kinds, {EnemyKind.BOSS_PARENT_A, EnemyKind.BOSS_PARENT_B})
        self.assertFalse(any(e.kind == EnemyKind.PILLOW for e in game.enemies))

    def test_final_boss_starts_victory(self) -> None:
        game = BoothBlaster(from_title=False)
        game.wave.index = CAMPAIGN_WAVES
        game.wave.boss_active = True
        game.enemies.clear()
        game.won_wave_flash = 0.0
        game.victory_timer = 0.0
        # Drive one update tick through the clear branch without player input noise.
        from core.input import InputState

        inp = InputState()
        game.update(0.016, inp)
        self.assertGreater(game.victory_timer, 0.0)
        self.assertTrue(game.campaign_won)

    def test_parent_kinds_and_bolt_kinds(self) -> None:
        self.assertIn(EnemyKind.BOSS_PARENT_A, _PARENT_KINDS)
        b = Bolt(0, 0, 1, False, kind="treat")
        self.assertEqual(b.kind, "treat")
        n = Bolt(0, 0, 1, False, kind="net")
        self.assertEqual(n.kind, "net")

    def test_player_skins_roster(self) -> None:
        self.assertGreaterEqual(len(PLAYER_SKINS), 10)
        self.assertIn("player_dobby_original.png", PLAYER_SKINS)
        self.assertIn("player_dobby_ugly.png", PLAYER_SKINS)
        self.assertIn("player_dobby_cute.png", PLAYER_SKINS)
        self.assertIn("player_dobby_pickle.png", PLAYER_SKINS)
        self.assertEqual(PLAYER_SKINS[-1], "player_dobby_thriller.png")
        self.assertIn("player_dobby_thriller.png", PRACTICE_SKINS)

    def test_practice_skin_infinite_lives_and_no_board(self) -> None:
        from unittest import mock

        practice_idx = PLAYER_SKINS.index("player_dobby_thriller.png")
        with mock.patch("games.booth_blaster.load_player_skin_index", return_value=practice_idx):
            self.assertTrue(is_practice_skin())
            game = BoothBlaster(from_title=False)
            game.player.lives = 1
            game.player.invuln = 0.0
            game._player_hit("paw")
            self.assertEqual(game.player.lives, 1)
            self.assertFalse(game.game_over)
            game.score = 99999
            game._begin_score_entry()
            self.assertFalse(game._entering_score)
            self.assertIsNone(game._initials_picker)

    def test_boss_difficulty_ramps_between_waves(self) -> None:
        # ~12.5% faster / hotter each solo-boss wave.
        self.assertAlmostEqual(boss_step_interval(2), boss_step_interval(1) / 1.125)
        self.assertAlmostEqual(boss_step_interval(3), boss_step_interval(2) / 1.125)
        self.assertAlmostEqual(boss_shoot_rate(2), boss_shoot_rate(1) * 1.125)
        self.assertAlmostEqual(boss_shoot_rate(3), boss_shoot_rate(2) * 1.125)
        # Parents match Nana cadence (wave 3).
        self.assertAlmostEqual(boss_step_interval(4), boss_step_interval(3))
        self.assertAlmostEqual(boss_shoot_rate(4), boss_shoot_rate(3))

    def test_parents_spawn_independent_and_match_nana_cadence(self) -> None:
        game = BoothBlaster(from_title=False)
        game.wave.index = 3
        game._spawn_boss()
        nana_interval = game.step_interval
        nana_rate = game._shoot_rate_for(game.enemies[0])

        game.wave.index = 4
        game._spawn_boss()
        parents = game.enemies
        self.assertEqual(len(parents), 2)
        self.assertAlmostEqual(game.step_interval, nana_interval)
        dirs = {e.march_dir for e in parents}
        self.assertEqual(dirs, {1.0, -1.0})
        for e in parents:
            self.assertAlmostEqual(e.step_interval, nana_interval)
            self.assertAlmostEqual(game._shoot_rate_for(e), nana_rate)
        self.assertNotEqual(parents[0].step_timer, parents[1].step_timer)


class PlayerSkinPersistTests(unittest.TestCase):
    def test_skin_index_roundtrip(self) -> None:
        from unittest import mock

        store: dict[str, str] = {}

        def _read(name: str):
            return store.get(name)

        def _write(name: str, text: str) -> None:
            store[name] = text

        with mock.patch("games.booth_blaster.storage.read_text", side_effect=_read):
            with mock.patch("games.booth_blaster.storage.write_text", side_effect=_write):
                save_player_skin_index(3)
                self.assertEqual(load_player_skin_index(), 3)
                self.assertEqual(player_skin_filename(), PLAYER_SKINS[3])


if __name__ == "__main__":
    unittest.main()
