import json
from pathlib import Path
import tempfile
from threading import Event, Thread
import time
import unittest
from urllib.request import Request, urlopen
import wave

from game import PokerGame
from metrics import MetricsStore
from overlay_server import OverlayServer
from settings import AppSettings


def write_tiny_wave(path):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\x00\x00\x20\x03\xe0\xfc\x00\x00")


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
            # A legacy provider saying "check" while facing a blind is safely
            # translated to a call; impossible free checks are never accepted.
            self.assertEqual(game.pot, 80)
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
            with urlopen(f"http://127.0.0.1:{server.port}/stream-info", timeout=2) as response:
                stream_info = json.load(response)
            with urlopen(f"http://127.0.0.1:{server.port}/health", timeout=2) as response:
                health = json.load(response)
            self.assertEqual(state["pot"], 0)
            self.assertEqual(state["schema_version"], 2)
            self.assertEqual(len(state["players"]), 2)
            self.assertEqual(state["health"]["overall"], "normal")
            self.assertIn("program", state)
            self.assertIn("league", state)
            self.assertIn("variety", state)
            self.assertEqual(state["variety"]["schema_version"], 1)
            self.assertIn("segment_id", state["variety"])
            self.assertIn("lounge", state)
            self.assertEqual(state["lounge"]["schema_version"], 1)
            self.assertIn("NO REAL ALCOHOL", state["lounge"]["responsible_label"])
            self.assertIn("venue", state["lounge"])
            self.assertIn("pressure_index", state["lounge"])
            self.assertIn("table_effects", state["lounge"])
            self.assertIn("scene_name", state["lounge"])
            self.assertIn("service_bot", state["lounge"])
            self.assertIn("table_mood", state["lounge"])
            self.assertIn("rivalry", state["lounge"])
            self.assertIn("atmosphere_line", state["lounge"])
            self.assertIn("presentation", state)
            self.assertEqual(state["presentation"]["schema_version"], 1)
            self.assertIn(state["presentation"]["mode"], {"table", "decision", "big_pot", "all_in", "showdown", "recap"})
            self.assertIn("spotlight_seat_ids", state["presentation"])
            self.assertEqual(state["presentation"]["showrunner_schema_version"], 1)
            self.assertIn("viewer_focus", state["presentation"])
            self.assertIn("voice_cue", state["presentation"])
            self.assertIn("non_reader_labels", state["presentation"])
            self.assertIn("audience_hook", state["presentation"])
            self.assertIn("bumper", state["presentation"])
            self.assertIn("enabled", state["presentation"]["bumper"])
            self.assertIn("responsible_label", state["presentation"]["bumper"])
            self.assertIn("engagement", state["presentation"])
            self.assertEqual(state["presentation"]["engagement"]["schema_version"], 1)
            self.assertIn("no wagers", state["presentation"]["engagement"]["safe_label"])
            self.assertIn("model_activity", state)
            self.assertEqual(state["model_activity"]["schema_version"], 1)
            self.assertIn("model_health", state["players"][0])
            self.assertIn("lounge", state["players"][0])
            self.assertEqual(state["players"][0]["lounge"]["schema_version"], 1)
            self.assertIn("visual_tell", state["players"][0]["lounge"])
            self.assertIn("service_level", state["players"][0]["lounge"])
            self.assertIn("avatar", state["players"][0]["profile"])
            self.assertIn("sigil", state["players"][0]["profile"])
            self.assertIn("tagline", state["players"][0]["profile"])
            self.assertGreaterEqual(len(state["storylines"]), 3)
            self.assertIn(state["players"][0]["id"], state["personality_arcs"])
            self.assertEqual(health["health"], state["health"])
            self.assertIn("AI Poker Overlay", html)
            self.assertIn("UNDERGROUND AI CASINO", html)
            self.assertIn("avatarMarkup", html)
            self.assertIn("enhancePlayerIdentities", html)
            self.assertIn("cyber-avatar", html)
            self.assertIn("avatar-sigil", html)
            self.assertIn("holo-card", html)
            self.assertIn("holoPulse", html)
            self.assertIn("Night City pass", html)
            self.assertIn("Neon megacity layer", html)
            self.assertIn("Cyberpunk director mode unification", html)
            self.assertIn("Showrunner non-reader layer", html)
            self.assertIn('id="showrunnerFocus"', html)
            self.assertIn('id="nonReaderStrip"', html)
            self.assertIn('id="voiceFlash"', html)
            self.assertIn("speakVoiceCue", html)
            self.assertIn("showrunnerDefault", html)
            self.assertIn("voiceCooldownMs", html)
            self.assertIn("city-backdrop", html)
            self.assertIn("city-skyline", html)
            self.assertIn("city-rain", html)
            self.assertIn("Simulation District", html)
            self.assertIn("NEON BOARD ARRAY", html)
            self.assertIn("Cyberpunk legibility pass", html)
            self.assertIn("loungeMarkup", html)
            self.assertIn("lounge-chip", html)
            self.assertIn("AI lounge service", html)
            self.assertIn("pressure_index", html)
            self.assertIn("service_level", html)
            self.assertIn("service_bot", html)
            self.assertIn("table_mood", html)
            self.assertIn("Real alcohol", html)
            self.assertIn("DEALER STATION", html)
            self.assertIn("deck-stack", html)
            self.assertIn("broadcast-context", html)
            self.assertIn("seat-label", html)
            self.assertIn('aria-live="polite"', html)
            self.assertIn('class="equity-meter"', html)
            self.assertIn("RECONNECTING", html)
            self.assertIn("@keyframes cardFlip", html)
            self.assertIn("class=\"wager", html)
            self.assertIn("highlightedWinners", html)
            self.assertIn("CHANCE TO WIN", html)
            self.assertIn("DECISION TIME", html)
            self.assertIn("PRIVATE CARDS", html)
            self.assertIn('class="winner-banner"', html)
            self.assertIn('id="winnerPlayer"', html)
            self.assertIn('id="winnerHand"', html)
            self.assertIn('id="winnerEngagement"', html)
            self.assertIn('class="winner-card-row"', html)
            self.assertIn("eventWinnerIds", html)
            self.assertIn("maybeRevealWinnerFromState", html)
            self.assertIn("CHIPS AWARDED", html)
            self.assertIn("reduced *", html)
            self.assertIn("SIMULATION ONLY", html)
            self.assertIn('id="healthPill"', html)
            self.assertIn("modelSignal", html)
            self.assertIn("MODEL FALLBACK", html)
            self.assertIn("OLLAMA LIVE", html)
            self.assertIn('id="directorLower"', html)
            self.assertIn('id="equityRace"', html)
            self.assertIn('id="recapCard"', html)
            self.assertIn('id="casinoBumper"', html)
            self.assertIn('id="bumperRelevance"', html)
            self.assertIn('id="bumperEngagement"', html)
            self.assertIn('id="audienceRibbon"', html)
            self.assertIn("renderEngagement", html)
            self.assertIn("Call out the next winner", html)
            self.assertIn('id="broadcastRotator"', html)
            self.assertIn("renderBroadcastRotator", html)
            self.assertIn("Equity studio", html)
            self.assertIn("AI model booth", html)
            self.assertIn("Table talk monitor", html)
            self.assertIn("NARRATION OFF", html)
            self.assertIn("speechSynthesis", html)
            self.assertIn("presentationFor", html)
            self.assertIn("renderDirector", html)
            self.assertIn("renderCasinoBumper", html)
            self.assertIn("SIMULATION ONLY · FICTIONAL CHIPS · NO REAL MONEY", html)
            lowered = html.lower()
            self.assertNotIn("spin again", lowered)
            self.assertNotIn("deposit", lowered)
            self.assertNotIn("cash out", lowered)
            self.assertIn("tableSkin", html)
            self.assertIn("@keyframes deckToBoard", html)
            self.assertIn("No Real Money", stream_info["title"])
            self.assertIn("fictional chips", stream_info["description"])
            self.assertEqual(len(stream_info["players"]), 2)
            self.assertNotIn("hole_cards", json.dumps(stream_info))
        finally:
            server.close()

    def test_overlay_director_query_overrides_and_visual_debug(self):
        game = PokerGame(2, decision_provider=lambda *_: "check")
        server = OverlayServer(
            game,
            port=0,
            director_enabled=True,
            visual_debug=False,
            rotation_enabled=True,
            rotation_interval_ms=11000,
            narration_enabled=False,
            showrunner_enabled=True,
            voice_cues_enabled=True,
            voice_cooldown_ms=13000,
            non_reader_mode=True,
            night_city_intensity="high",
        ).start()
        try:
            with urlopen(f"{server.url}?director=0&showrunner=0&nonreader=0&voice=0&night_city=low&visual_debug=1", timeout=2) as response:
                html = response.read().decode("utf-8")
            with urlopen(f"{server.url}?rotation=0&narration=1", timeout=2) as response:
                narrated_html = response.read().decode("utf-8")
            self.assertIn('data-director="off"', html)
            self.assertIn("q.get('showrunner')==='0'", html)
            self.assertIn("q.get('nonreader')==='0'", html)
            self.assertIn("q.get('voice')==='0'", html)
            self.assertIn("nightCityIntensity=q.get('night_city')||'high'", html)
            self.assertIn("visual-debug", html)
            self.assertIn("director-off", html)
            self.assertIn('id="directorDebug"', html)
            self.assertIn("rotationDefault='on'==='on'", narrated_html)
            self.assertIn("rotationMs=Math.max(5000,Number(q.get('rotation_ms')||'11000')||9000)", narrated_html)
            self.assertIn("narrationDefault='off'==='on'", narrated_html)
            self.assertIn("q.get('narration')==='1'", narrated_html)
            self.assertIn("voiceCooldownMs=Math.max(3000,Number(q.get('voice_ms')||'13000')||9000)", narrated_html)
        finally:
            server.close()

    def test_overlay_browser_audio_and_music_can_be_enabled_for_obs_source(self):
        with tempfile.TemporaryDirectory() as directory:
            music_dir = Path(directory) / "music"
            music_dir.mkdir()
            write_tiny_wave(music_dir / "Casino Bed.wav")
            sound_dir = Path(directory) / "sound_effects"
            sound_dir.mkdir()
            (sound_dir / "card_flip.mp3").write_bytes(b"ID3cardflip")
            game = PokerGame(2, decision_provider=lambda *_: "check")
            server = OverlayServer(game, port=0, audio_enabled=True, music_dir=music_dir, sound_effects_dir=sound_dir).start()
            try:
                with urlopen(server.url, timeout=2) as response:
                    default_html = response.read().decode("utf-8")
                with urlopen(f"{server.url}?audio=0", timeout=2) as response:
                    muted_html = response.read().decode("utf-8")
                with urlopen(f"http://127.0.0.1:{server.port}/music/0.wav", timeout=2) as response:
                    music_head = response.read(12)
                request = Request(
                    f"http://127.0.0.1:{server.port}/music/0.wav",
                    headers={"Range": "bytes=0-3"},
                )
                with urlopen(request, timeout=2) as response:
                    ranged = response.read()
                with urlopen(f"http://127.0.0.1:{server.port}/sound/card_flip.mp3", timeout=2) as response:
                    flip_head = response.read(3)

                self.assertIn("audio-on", default_html)
                self.assertIn('data-music="on"', default_html)
                self.assertIn('"/music/0.wav"', default_html)
                self.assertIn('"/sound/card_flip.mp3"', default_html)
                self.assertIn('data-music="off"', muted_html)
                self.assertIn('data-director="on" data-director-mode="table" data-intensity="0" class=" "', muted_html)
                self.assertTrue(music_head.startswith(b"RIFF"))
                self.assertEqual(ranged, b"RIFF")
                self.assertEqual(flip_head, b"ID3")
            finally:
                server.close()

    def test_public_health_states_are_bounded_and_viewer_safe(self):
        game = PokerGame(2, decision_provider=lambda *_: "check")
        scenarios = [
            ({"ollama": "online"}, {"enabled": True}, "normal"),
            ({"ollama": "fallback"}, {"enabled": True}, "degraded"),
            ({"ollama": "unavailable"}, {"enabled": True}, "degraded"),
            ({"checkpoint": "restored"}, {"enabled": True}, "recovered"),
            ({"ollama": "online"}, {"enabled": False}, "notice"),
            ({"persistence": "warning"}, {"enabled": True}, "warning"),
        ]
        for services, audio, expected in scenarios:
            game.service_health.update({"ollama": "online", "persistence": "ready", "checkpoint": "standby"})
            game.service_health.update(services)
            game.audio_state.update(audio)
            health = game.health_snapshot()
            self.assertEqual(health["overall"], expected)
            public = json.dumps(health).lower()
            self.assertNotIn("traceback", public)
            self.assertNotIn("\\", public)
            self.assertNotIn("/users/", public)

    def test_model_activity_distinguishes_ollama_from_fallback_decisions(self):
        decisions = [
            {"action": "call", "amount": 20, "table_talk": "", "_model_status": "online", "_model": "qwen2.5:7b"},
            {"action": "check", "amount": None, "table_talk": "", "_model_status": "fallback", "_model": "qwen2.5:7b"},
        ]

        def provider(_context):
            return decisions.pop(0) if decisions else {"action": "check", "_model_status": "fallback", "_model": "qwen2.5:7b"}

        game = PokerGame(2, decision_provider=provider)
        game.play_pre_flop()
        state = game.state_snapshot()

        self.assertEqual(state["model_activity"]["fallback_decisions"], 1)
        self.assertEqual(state["model_activity"]["ollama_decisions"], 1)
        self.assertEqual(state["services"]["ollama"], "fallback")
        self.assertEqual(state["health"]["overall"], "degraded")
        sources = {player["model_health"]["source"] for player in state["players"]}
        self.assertIn("ollama", sources)
        self.assertIn("fallback", sources)

    def test_overlay_simulation_disclaimer_can_be_hidden(self):
        game = PokerGame(2, decision_provider=lambda *_: "check")
        server = OverlayServer(game, port=0, disclaimer_enabled=False).start()
        try:
            with urlopen(server.url, timeout=2) as response:
                html = response.read().decode("utf-8")
            self.assertIn('class="simulation-tag hidden"', html)
        finally:
            server.close()

    def test_overlay_event_stream_replays_from_sequence(self):
        game = PokerGame(2, decision_provider=lambda *_: "check")
        event = game._emit("diagnostic", "event stream ready")
        server = OverlayServer(game, port=0).start()
        try:
            with urlopen(f"http://127.0.0.1:{server.port}/events?since={event['id'] - 1}", timeout=2) as response:
                first = response.readline().decode("utf-8")
                second = response.readline().decode("utf-8")
            self.assertEqual(first.strip(), f"id: {event['id']}")
            self.assertIn('"type":"diagnostic"', second)
        finally:
            server.close()

    def test_settings_ignore_unknown_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"stage_delay_ms": 123, "future_key": true}', encoding="utf-8")
            settings = AppSettings.load(path)
            self.assertEqual(settings.stage_delay_ms, 123)
            self.assertTrue(settings.continuous_play)

    def test_tied_showdown_splits_odd_pot_and_records_ties(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MetricsStore(Path(directory) / "leaderboard.json")
            game = PokerGame(2, metrics_store=store, decision_provider=lambda *_: "check")
            game.dealer_position = 0
            game.hand_in_progress = True
            game.players[0].hand = [(2, "hearts"), (3, "clubs")]
            game.players[1].hand = [(4, "hearts"), (5, "clubs")]
            game.community_cards = [
                (10, "hearts"), (11, "clubs"), (12, "diamonds"),
                (13, "spades"), (14, "hearts"),
            ]
            game.players[0].chips = 990
            game.players[1].chips = 979
            game._opening_chips = {player.name: 1000 for player in game.players}
            game.pot = 31

            game.determine_winner()

            self.assertEqual([player.chips for player in game.players], [1005, 995])
            self.assertEqual([player.ties for player in game.players], [1, 1])
            snapshot = store.snapshot()
            self.assertEqual(snapshot["players"]["AI Player 1"]["hands_tied"], 1)
            self.assertEqual(snapshot["players"]["AI Player 2"]["hands_tied"], 1)

    def test_state_endpoint_data_remains_available_while_model_thinks(self):
        started = Event()
        release = Event()

        def slow_decision(*_args):
            started.set()
            release.wait(timeout=2)
            return "check"

        game = PokerGame(2, decision_provider=slow_decision)
        worker = Thread(target=game.play_pre_flop)
        worker.start()
        self.assertTrue(started.wait(timeout=1))
        before = time.monotonic()
        state = game.state_snapshot()
        elapsed = time.monotonic() - before
        release.set()
        worker.join(timeout=2)

        self.assertLess(elapsed, 0.2)
        self.assertEqual(state["stage"], "Pre-Flop")
        self.assertIsNotNone(state["players"])

    def test_interrupted_hand_is_refunded_for_continuous_play(self):
        def failed_decision(*_args):
            raise RuntimeError("model process stopped")

        game = PokerGame(4, decision_provider=failed_decision)
        with self.assertRaises(RuntimeError):
            game.play_pre_flop()
        game.recover_from_error("model process stopped")

        self.assertEqual(sum(player.chips for player in game.players), 4000)
        self.assertEqual(game.pot, 0)
        self.assertFalse(game.hand_in_progress)
        self.assertEqual(game.stage, "Recovering")

    def test_game_log_is_bounded_for_long_running_streams(self):
        game = PokerGame(2, decision_provider=lambda *_: "check")
        for index in range(2100):
            game._emit("diagnostic", f"event {index}")
        self.assertEqual(len(game.get_log()), 2000)
        self.assertEqual(game.get_log()[0], "event 100")


if __name__ == "__main__":
    unittest.main()
