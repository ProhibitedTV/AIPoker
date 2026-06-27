"""Run a continuously playing deterministic table for OBS/UI review."""

import argparse
from pathlib import Path
import random
import sys
import tempfile
from threading import Event, Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game import PokerGame
from metrics import MetricsStore
from overlay_server import OverlayServer
from settings import default_profiles, default_variety_segments


TABLE_TALK = {
    "atlas": ("The price is the price.", "I have enough information."),
    "vega": ("Let's make this interesting.", "Pressure is a privilege."),
    "nova": ("That line tells a story.", "I can work with this."),
    "echo": ("Silence can be expensive.", "You may want that one back."),
}


def preview_decision(rng):
    def decide(context):
        legal = {entry["action"]: entry for entry in context["legal_actions"]}
        player = context["player"]
        roll = rng.random()
        result = {}
        if "raise" in legal and roll < 0.13:
            contract = legal["raise"]
            spread = max(0, contract["max_target"] - contract["min_target"])
            result = {
                "action": "raise",
                "amount": contract["min_target"] + min(spread, context["pot"] // 2),
            }
        elif "bet" in legal and roll < 0.28:
            contract = legal["bet"]
            result = {
                "action": "bet",
                "amount": min(contract["max_target"], max(contract["min_target"], context["pot"] // 2)),
            }
        elif "call" in legal:
            call = legal["call"]["amount"]
            result = {"action": "call" if call <= max(context["blinds"]["big"] * 6, player["stack"] // 4) else "fold"}
        elif "check" in legal:
            result = {"action": "check"}
        else:
            result = {"action": "fold"}
        lines = TABLE_TALK.get(player["id"], ())
        result["table_talk"] = rng.choice(lines) if lines and rng.random() < 0.16 else ""
        return result

    return decide


def run_table(game, stop, street_delay, hand_delay):
    while not stop.is_set():
        try:
            game.play_pre_flop()
            if stop.wait(street_delay):
                break
            for street in (game.play_flop, game.play_turn, game.play_river):
                if sum(player.is_active for player in game.players) <= 1:
                    break
                street()
                if stop.wait(street_delay):
                    break
            if stop.is_set():
                break
            game.determine_winner()
            if stop.wait(hand_delay):
                break
        except Exception as error:
            game.recover_from_error(error)
            if stop.wait(hand_delay):
                break


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Serve the continuously playing casino overlay")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--players", type=int, choices=range(2, 7), default=4)
    parser.add_argument("--street-delay", type=float, default=3.8)
    parser.add_argument("--hand-delay", type=float, default=7.5)
    parser.add_argument("--action-delay", type=float, default=1.15)
    parser.add_argument("--deal-delay", type=float, default=0.28)
    parser.add_argument("--seed", type=int, default=20260622)
    parser.add_argument("--audio", action="store_true", help="Enable browser-source cue and music audio")
    parser.add_argument("--reduced-motion", action="store_true")
    parser.add_argument("--no-simulation-disclaimer", action="store_true")
    parser.add_argument("--no-director", action="store_true", help="Disable directed visual moments")
    parser.add_argument("--no-variety-rotation", action="store_true", help="Keep the preview on one table segment")
    parser.add_argument("--no-casino-bumpers", action="store_true", help="Disable non-wagering casino bumper intermissions")
    parser.add_argument("--visual-debug", action="store_true", help="Show OBS safe-area and director labels")
    parser.add_argument("--recap-duration", type=float, default=7.5, help="Seconds to hold recap visuals")
    parser.add_argument("--moment-duration", type=float, default=6.2, help="Seconds to hold major moment visuals")
    parser.add_argument(
        "--health-state",
        choices=("normal", "degraded", "recovered", "persistence-warning", "audio-muted"),
        default="normal",
        help="Render a viewer-safe broadcast health fixture without Ollama",
    )
    return parser.parse_args(argv)


def apply_health_fixture(game, state):
    game.service_health["ollama"] = "fallback" if state == "degraded" else "preview"
    if state == "recovered":
        game.service_health["checkpoint"] = "restored"
    elif state == "persistence-warning":
        game.service_health["persistence"] = "warning"
    if state == "audio-muted":
        game.audio_state["enabled"] = False


def main(argv=None):
    args = parse_args(argv)
    rng = random.Random(args.seed)
    metrics_directory = tempfile.TemporaryDirectory(prefix="ai-poker-preview-")
    metrics = MetricsStore(Path(metrics_directory.name) / "leaderboard.json")
    game = PokerGame(
        args.players,
        starting_chips=2000,
        mode="tournament",
        profiles=default_profiles()[:args.players],
        decision_provider=preview_decision(rng),
        metrics_store=metrics,
        rng_seed=args.seed,
        auto_restore=False,
        variety_rotation_enabled=not args.no_variety_rotation,
        variety_segments=default_variety_segments(),
        casino_bumpers_enabled=not args.no_casino_bumpers,
        action_delay_ms=round(max(0.0, args.action_delay) * 1000),
        deal_delay_ms=round(max(0.0, args.deal_delay) * 1000),
    )
    apply_health_fixture(game, args.health_state)
    server = OverlayServer(
        game,
        host=args.host,
        port=args.port,
        reduced_motion=args.reduced_motion,
        audio_enabled=args.audio,
        disclaimer_enabled=not args.no_simulation_disclaimer,
        director_enabled=not args.no_director,
        recap_duration_ms=round(max(1.2, args.recap_duration) * 1000),
        moment_duration_ms=round(max(1.2, args.moment_duration) * 1000),
        visual_debug=args.visual_debug,
    ).start()
    game.service_health["overlay"] = "online"
    stop = Event()
    worker = Thread(
        target=run_table,
        args=(game, stop, max(0.1, args.street_delay), max(0.2, args.hand_delay)),
        name="preview-table",
        daemon=True,
    )
    worker.start()
    print(f"Live casino preview: {server.url}")
    try:
        Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        worker.join(timeout=3)
        server.close()
        game.close()
        metrics_directory.cleanup()


if __name__ == "__main__":
    main()
