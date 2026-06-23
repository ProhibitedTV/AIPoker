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


def fetch(url):
    with urlopen(url, timeout=4) as response:
        return response.read()


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
        game.play_pre_flop()
        server = OverlayServer(game, port=0, audio_enabled=True).start()
        game.service_health["overlay"] = "online"
        base = f"http://127.0.0.1:{server.port}"
        full_html = fetch(f"{base}/overlay").decode("utf-8")
        compact_html = fetch(f"{base}/overlay?compact=1").decode("utf-8")
        state = json.loads(fetch(f"{base}/state").decode("utf-8"))
        health = json.loads(fetch(f"{base}/health").decode("utf-8"))
        transcript = list(state.get("action_history", []))[-8:]
        missing = [marker for marker in CRITICAL_MARKERS if marker not in full_html]
        if missing or len(full_html.strip()) < 5000:
            raise RuntimeError(f"blank or incomplete overlay smoke render; missing {missing}")
        (output_dir / "overlay-full.html").write_text(full_html, encoding="utf-8")
        (output_dir / "overlay-compact.html").write_text(compact_html, encoding="utf-8")
        (output_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        (output_dir / "health.json").write_text(json.dumps(health, indent=2), encoding="utf-8")
        (output_dir / "event-transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        summary = {
            "ok": True,
            "port": server.port,
            "artifacts": sorted(path.name for path in output_dir.iterdir()),
            "critical_markers": list(CRITICAL_MARKERS),
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
