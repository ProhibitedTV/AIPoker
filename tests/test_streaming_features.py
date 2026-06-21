import json
from pathlib import Path
import tempfile
import unittest
from urllib.request import urlopen

from game import PokerGame
from metrics import MetricsStore
from overlay_server import OverlayServer
from settings import AppSettings


class StreamingFeatureTests(unittest.TestCase):
    def test_game_state_and_metrics_are_consistent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MetricsStore(Path(directory) / "leaderboard.json")
            game = PokerGame(
                num_players=4,
                metrics_store=store,
                decision_provider=lambda _hand, _community: "check",
            )
            starting_total = sum(player.chips for player in game.players)

            game.play_pre_flop()
            self.assertEqual(game.pot, 30)
            game.play_flop()
            game.play_turn()
            game.play_river()
            winner, hand_name = game.determine_winner()

            self.assertIsNotNone(winner)
            self.assertIn(hand_name, PokerGame.HAND_NAMES.values())
            self.assertEqual(sum(player.chips for player in game.players), starting_total)
            self.assertEqual(store.snapshot()["hands_played"], 1)
            self.assertEqual(sum(p.total_rounds for p in game.players), 4)
            self.assertEqual(game.state_snapshot()["stage"], "Showdown")

    def test_metrics_survive_reload_and_can_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "leaderboard.json"
            store = MetricsStore(path)
            game = PokerGame(2, metrics_store=store, decision_provider=lambda *_: "check")
            game.play_pre_flop()
            game.determine_winner()

            reloaded = MetricsStore(path)
            self.assertEqual(reloaded.snapshot()["hands_played"], 1)
            reloaded.reset()
            self.assertEqual(MetricsStore(path).snapshot()["hands_played"], 0)

    def test_betting_stops_before_the_last_player_can_fold(self):
        game = PokerGame(4, decision_provider=lambda *_: "fold")
        starting_total = sum(player.chips for player in game.players)
        game.play_pre_flop()
        self.assertEqual(sum(player.is_active for player in game.players), 1)
        winner, _ = game.determine_winner()
        self.assertIsNotNone(winner)
        self.assertEqual(sum(player.chips for player in game.players), starting_total)

    def test_overlay_serves_browser_page_and_json_state(self):
        game = PokerGame(2, decision_provider=lambda *_: "check")
        server = OverlayServer(game, port=0).start()
        try:
            with urlopen(f"http://127.0.0.1:{server.port}/state", timeout=2) as response:
                state = json.load(response)
            with urlopen(server.url, timeout=2) as response:
                html = response.read().decode("utf-8")
            self.assertEqual(state["pot"], 0)
            self.assertEqual(len(state["players"]), 2)
            self.assertIn("AI Poker Overlay", html)
        finally:
            server.close()

    def test_settings_ignore_unknown_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"stage_delay_ms": 123, "future_key": true}', encoding="utf-8")
            settings = AppSettings.load(path)
            self.assertEqual(settings.stage_delay_ms, 123)
            self.assertTrue(settings.continuous_play)


if __name__ == "__main__":
    unittest.main()
