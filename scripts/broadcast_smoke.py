"""Generate broadcast smoke artifacts without Ollama or OBS."""

import argparse
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game import PokerGame  # noqa: E402
from metrics import MetricsStore  # noqa: E402
from overlay_server import OverlayServer  # noqa: E402
from scripts.preview_overlay import preview_decision  # noqa: E402
from settings import default_profiles  # noqa: E402


CRITICAL_MARKERS = (
    "AI POKER",
    "DEALER STATION",
    "TOTAL POT",
    "LIVE ACTION",
    "PRIVATE CARDS",
    "Program warming up",
)
VISUAL_FIXTURES = ("table", "decision", "big_pot", "all_in", "showdown", "recap", "bumper")


def fetch(url):
    with urlopen(url, timeout=4) as response:
        return response.read()


def apply_visual_fixture(game, fixture):
    game.hand_number = 1
    game.tournament_hand_number = 1
    game.stage = "Pre-Flop"
    game.pot = 80
    game.pots = [{"index": 0, "kind": "main", "amount": 80, "eligible": [player.id for player in game.players]}]
    game.community_cards = []
    game.action_history.clear()
    game.commentary.clear()
    game.next_to_act = None
    game.current_bet_to_match = 0
    game.dealer_position = 0
    game.small_blind_position = 1 if game.num_players > 2 else 0
    game.big_blind_position = 2 if game.num_players > 2 else 1
    hands = [
        [(14, "spades"), (14, "hearts")],
        [(13, "clubs"), (12, "clubs")],
        [(9, "diamonds"), (9, "clubs")],
        [(7, "spades"), (6, "spades")],
        [(5, "hearts"), (5, "diamonds")],
        [(4, "clubs"), (3, "clubs")],
    ]
    for index, player in enumerate(game.players):
        player.reset_for_next_round()
        player.deal_hand(hands[index])
        player.chips = 2000 - index * 90
        player.is_active = True
        player.last_action = "Waiting"
    if fixture == "table":
        game.stage = "Waiting"
        game.pot = 0
        game.pots = []
        return
    game.hand_in_progress = fixture not in {"recap", "bumper"}
    game.action_history.extend(
        [
            {"seat": game.small_blind_position, "action": "small_blind", "amount": game.small_blind},
            {"seat": game.big_blind_position, "action": "big_blind", "amount": game.big_blind},
        ]
    )
    if fixture == "decision":
        game.next_to_act = 0
        game.current_bet_to_match = 80
        game.players[0].current_bet = 20
        game.players[0].last_action = "Thinking"
        game.pot = 170
        game.commentary.append("Atlas is facing pressure before the flop.")
    elif fixture == "big_pot":
        game.stage = "Turn"
        game.community_cards = [(11, "clubs"), (10, "diamonds"), (3, "spades"), (8, "hearts")]
        game.pot = 520
        game.pots = [{"index": 0, "kind": "main", "amount": 520, "eligible": [player.id for player in game.players]}]
        game.commentary.append("The pot crosses monster territory.")
    elif fixture == "all_in":
        game.stage = "River"
        game.community_cards = [(11, "clubs"), (10, "diamonds"), (3, "spades"), (8, "hearts"), (2, "clubs")]
        game.players[1].chips = 0
        game.players[1].all_in = True
        game.players[1].last_action = "All-in 900"
        game.pot = 1900
        game.pots = [{"index": 0, "kind": "main", "amount": 1900, "eligible": [player.id for player in game.players[:2]]}]
        game.commentary.append("Vega is all-in with the tournament life on the line.")
    elif fixture == "showdown":
        game.stage = "Showdown"
        game.community_cards = [(11, "clubs"), (10, "diamonds"), (3, "spades"), (8, "hearts"), (2, "clubs")]
        game.pot = 1900
        game.pots = [{"index": 0, "kind": "main", "amount": 1900, "eligible": [player.id for player in game.players[:2]]}]
        game.commentary.append("Cards are being compared at showdown.")
    elif fixture == "recap":
        game.stage = "Showdown"
        game.hand_in_progress = False
        game.community_cards = [(11, "clubs"), (10, "diamonds"), (3, "spades"), (8, "hearts"), (2, "clubs")]
        game.players[0].chips = 2920
        game.players[0].last_action = "Won 920"
        game.players[1].folded = True
        game.players[1].is_active = False
        game.pot = 0
        game.pots = []
        game.commentary.append("Atlas wins 920 with pair of aces.")
    elif fixture == "bumper":
        game.stage = "Showdown"
        game.hand_number = 3
        game.hand_in_progress = False
        game.community_cards = [(11, "clubs"), (10, "diamonds"), (3, "spades"), (8, "hearts"), (2, "clubs")]
        game.players[0].chips = 2920
        game.players[0].last_action = "Won 920"
        game.players[1].folded = True
        game.players[1].is_active = False
        game.pot = 0
        game.pots = []
        game.commentary.append("Atlas wins 920 with pair of aces.")


def generate_artifacts(output_dir, players=4):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    temp = tempfile.TemporaryDirectory(prefix="ai-poker-smoke-")
    server = None
    try:
        rng = __import__("random").Random(20260622)
        metrics = MetricsStore(Path(temp.name) / "leaderboard.json")
        game = PokerGame(
            players,
            starting_chips=2000,
            mode="tournament",
            profiles=default_profiles()[:players],
            decision_provider=preview_decision(rng),
            metrics_store=metrics,
            rng_seed=20260622,
            auto_restore=False,
            action_delay_ms=0,
            deal_delay_ms=0,
        )
        server = OverlayServer(game, port=0, audio_enabled=True).start()
        game.service_health["overlay"] = "online"
        base = f"http://127.0.0.1:{server.port}"
        fixture_modes = {}
        for fixture in VISUAL_FIXTURES:
            apply_visual_fixture(game, fixture)
            full_html = fetch(f"{base}/overlay").decode("utf-8")
            compact_html = fetch(f"{base}/overlay?compact=1").decode("utf-8")
            state = json.loads(fetch(f"{base}/state").decode("utf-8"))
            missing = [marker for marker in CRITICAL_MARKERS if marker not in full_html]
            if missing or len(full_html.strip()) < 5000:
                raise RuntimeError(f"blank or incomplete overlay smoke render for {fixture}; missing {missing}")
            (output_dir / f"overlay-full-{fixture}.html").write_text(full_html, encoding="utf-8")
            (output_dir / f"overlay-compact-{fixture}.html").write_text(compact_html, encoding="utf-8")
            (output_dir / f"state-{fixture}.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
            fixture_modes[fixture] = state["presentation"]["mode"]
            if fixture == "table":
                (output_dir / "overlay-full.html").write_text(full_html, encoding="utf-8")
                (output_dir / "overlay-compact.html").write_text(compact_html, encoding="utf-8")
                (output_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        health = json.loads(fetch(f"{base}/health").decode("utf-8"))
        transcript = list(json.loads((output_dir / "state-decision.json").read_text(encoding="utf-8")).get("action_history", []))[-8:]
        (output_dir / "health.json").write_text(json.dumps(health, indent=2), encoding="utf-8")
        (output_dir / "event-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        summary = {
            "ok": True,
            "port": server.port,
            "artifacts": sorted(path.name for path in output_dir.iterdir()),
            "critical_markers": list(CRITICAL_MARKERS),
            "fixture_modes": fixture_modes,
        }
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary
    finally:
        if server:
            server.close()
        temp.cleanup()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate AI Poker broadcast smoke artifacts")
    parser.add_argument("--output", default="artifacts/broadcast-smoke")
    parser.add_argument("--players", type=int, choices=range(2, 7), default=4)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    summary = generate_artifacts(args.output, players=args.players)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
