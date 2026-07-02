"""Static 1080p broadcast visual smoke gate for the OBS overlay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.broadcast_smoke import VISUAL_FIXTURES, generate_artifacts  # noqa: E402


REQUIRED_OVERLAY_MARKERS = (
    "director-lower-third",
    "lower-third",
    "data-lower-third-mode",
    "renderLowerThird",
    "renderHauntTicker",
    "haunt-event",
    "lt-module",
    "hud-minimal",
    "body.lower-third-on .ticker.lower-third",
    "venue-chip",
    "venueThemeOn",
    "card.holo-card",
    "showrunner-focus",
    "playVoiceClip",
    "speakTableTalkCue",
    "persona-card",
    "personaCardMarkup",
    "personaMoment",
    "non-reader-strip",
    "equity-race",
    "recap-card",
    "casino-bumper",
    "casino-room",
    "renderCasinoRoom",
    "stream-scene",
    "renderStreamScene",
    "data-stream-scene",
    "Fictional bankroll ladder",
    "winner-banner",
    "visual-debug",
    "deckToBoard",
    "chipToPot",
    "jackpotSweep",
    "ltModuleWipe",
)


EXPECTED_FIXTURE_MODES = {
    "table": "table",
    "standby": "table",
    "decision": "decision",
    "big_pot": "big_pot",
    "all_in": "all_in",
    "showdown": "showdown",
    "recap": "recap",
    "bumper": "recap",
    "table_reset": "table",
    "casino_blackjack": "table",
    "casino_baccarat": "table",
    "casino_transition": "table",
}


def run_visual_smoke(output_dir, players=4):
    output_dir = Path(output_dir)
    summary = generate_artifacts(output_dir, players=players)
    problems = []
    for fixture in VISUAL_FIXTURES:
        full = output_dir / f"overlay-full-{fixture}.html"
        compact = output_dir / f"overlay-compact-{fixture}.html"
        state_path = output_dir / f"state-{fixture}.json"
        for path in (full, compact, state_path):
            if not path.exists():
                problems.append(f"missing artifact: {path.name}")
        if not full.exists():
            continue
        html = full.read_text(encoding="utf-8")
        missing = [marker for marker in REQUIRED_OVERLAY_MARKERS if marker not in html]
        if missing:
            problems.append(f"{full.name} missing markers: {', '.join(missing)}")
        if "outline-offset:-54px" not in html:
            problems.append(f"{full.name} missing visual safe-area outline")
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            mode = state.get("presentation", {}).get("mode")
            expected = EXPECTED_FIXTURE_MODES[fixture]
            if mode != expected:
                problems.append(f"{state_path.name} expected {expected}, got {mode}")
            if fixture == "bumper" and not state.get("presentation", {}).get("bumper", {}).get("enabled"):
                problems.append(f"{state_path.name} expected an enabled casino bumper")
            scene = state.get("presentation", {}).get("scene_state", {})
            if fixture in {"standby", "table_reset"} and scene.get("state") != fixture:
                problems.append(f"{state_path.name} expected scene_state {fixture}, got {scene.get('state')}")
            if fixture == "bumper" and scene.get("state") != "break":
                problems.append(f"{state_path.name} expected break scene_state for bumper, got {scene.get('state')}")
            if fixture.startswith("casino_") and not state.get("casino", {}).get("enabled"):
                problems.append(f"{state_path.name} expected enabled casino programming")
            if fixture == "casino_blackjack" and state.get("casino", {}).get("active_game") != "blackjack":
                problems.append(f"{state_path.name} expected blackjack room")
            if fixture == "casino_baccarat" and state.get("casino", {}).get("active_game") != "baccarat":
                problems.append(f"{state_path.name} expected baccarat room")
    result = {
        "ok": not problems,
        "output": str(output_dir),
        "players": players,
        "fixtures": list(VISUAL_FIXTURES),
        "problems": problems,
        "broadcast_summary": summary,
    }
    (output_dir / "visual-summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if problems:
        raise RuntimeError("; ".join(problems))
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Validate AI Poker OBS visual fixture artifacts")
    parser.add_argument("--output", default="artifacts/visual-smoke")
    parser.add_argument("--players", type=int, choices=range(2, 7), default=4)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    result = run_visual_smoke(args.output, players=args.players)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
