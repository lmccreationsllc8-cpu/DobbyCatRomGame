"""DBY ghost score is a hard-coded vanity top entry."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import leaderboard


class DbyScoreTests(unittest.TestCase):
    def test_dby_is_hardcoded_top_and_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "leaderboard.json"
            store.write_text(
                json.dumps([{"name": "AAA", "score": 100, "wave": 1}]),
                encoding="utf-8",
            )
            with mock.patch("core.leaderboard.storage.read_text", side_effect=lambda _n: store.read_text(encoding="utf-8")):
                with mock.patch("core.leaderboard.storage.write_text"):
                    scores = leaderboard.load_scores()
            self.assertEqual(scores[0].name, "DBY")
            self.assertEqual(scores[0].score, leaderboard.DBY_SCORE)
            self.assertEqual(scores[0].wave, leaderboard.DBY_WAVE)
            self.assertEqual(leaderboard.DBY_SCORE, 99999)

    def test_dby_ignores_human_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "leaderboard.json"
            store.write_text(
                json.dumps([{"name": "ZZZ", "score": 90000, "wave": 3}]),
                encoding="utf-8",
            )
            with mock.patch("core.leaderboard.storage.read_text", side_effect=lambda _n: store.read_text(encoding="utf-8")):
                scores = leaderboard.load_scores()
            self.assertEqual(scores[0].name, "DBY")
            self.assertEqual(scores[0].score, 99999)


class CampaignConstantsTests(unittest.TestCase):
    def test_campaign_wave_matches_dby_wave(self) -> None:
        from games.booth_blaster import CAMPAIGN_WAVES

        self.assertEqual(CAMPAIGN_WAVES, 4)
        self.assertEqual(leaderboard.DBY_WAVE, 4)


if __name__ == "__main__":
    unittest.main()
