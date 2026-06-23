"""Benchmark local Ollama models for AI Poker seat calibration."""

import argparse
import json
import statistics
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from ollama_integration import OLLAMA_API_URL, get_available_models  # noqa: E402
from ollama_integration import _parse_json_object, _validate_decision  # noqa: E402


FIXTURE_CONTEXTS = [
    {
        "street": "pre-flop",
        "player": {"id": "atlas", "name": "Atlas", "seat": 0, "stack": 2000, "hole_cards": [{"rank": 14, "suit": "spades"}, {"rank": 14, "suit": "hearts"}]},
        "profile": {"persona": "disciplined analyst", "temperature": 0.2},
        "community_cards": [],
        "pot": 30,
        "blinds": {"small": 10, "big": 20},
        "to_call": 20,
        "legal_actions": [{"action": "fold"}, {"action": "call", "amount": 20, "target": 20}, {"action": "raise", "min_target": 40, "max_target": 2000}],
        "players": [{"id": "vega", "name": "Vega", "seat": 1, "stack": 1980, "status": "active"}],
        "action_history": [{"seat": 1, "action": "big_blind", "amount": 20}],
    },
    {
        "street": "flop",
        "player": {"id": "nova", "name": "Nova", "seat": 2, "stack": 1430, "hole_cards": [{"rank": 10, "suit": "clubs"}, {"rank": 9, "suit": "clubs"}]},
        "profile": {"persona": "balanced adaptive reader", "temperature": 0.35},
        "community_cards": [{"rank": 11, "suit": "clubs"}, {"rank": 8, "suit": "clubs"}, {"rank": 2, "suit": "diamonds"}],
        "pot": 280,
        "blinds": {"small": 10, "big": 20},
        "to_call": 0,
        "legal_actions": [{"action": "check"}, {"action": "bet", "min_target": 20, "max_target": 1430}],
        "players": [{"id": "echo", "name": "Echo", "seat": 3, "stack": 1710, "status": "active"}],
        "action_history": [{"seat": 0, "action": "call", "amount": 20}],
    },
]


def build_payload(model, temperature, context):
    safe_context = {
        key: context.get(key)
        for key in ("street", "player", "community_cards", "pot", "blinds", "to_call", "legal_actions", "players", "action_history")
    }
    system = (
        "You are benchmarking a No-Limit Texas Hold'em decision. Use only supplied data. "
        "Return strict JSON: {\"action\":string,\"amount\":integer|null,\"table_talk\":string}."
    )
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(safe_context, separators=(",", ":"))},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": max(0.0, min(1.5, float(temperature)))},
    }


def benchmark_model(model, temperature, fixture=False, timeout=20):
    latencies = []
    malformed = 0
    illegal = 0
    fallback = 0
    actions = {}
    samples = []
    for context in FIXTURE_CONTEXTS:
        payload = build_payload(model, temperature, context)
        started = time.monotonic()
        if fixture:
            raw = {"action": "raise" if "raise" in {item["action"] for item in context["legal_actions"]} else "check", "amount": 60, "table_talk": ""}
            status = "fixture"
        else:
            try:
                import requests

                response = requests.post(OLLAMA_API_URL, json=payload, timeout=timeout)
                response.raise_for_status()
                raw = response.json().get("message", {}).get("content", "")
                status = "online"
            except Exception:
                raw = {"action": "check", "amount": None, "table_talk": ""}
                status = "unavailable"
                fallback += 1
        latencies.append(time.monotonic() - started)
        try:
            parsed = _parse_json_object(raw)
        except Exception:
            malformed += 1
            parsed = {}
        legal = {entry["action"]: entry for entry in context["legal_actions"]}
        validated = _validate_decision(parsed, legal)
        if not validated:
            illegal += 1
            action = "fallback"
        else:
            action = validated["action"]
        actions[action] = actions.get(action, 0) + 1
        samples.append({"street": context["street"], "status": status, "action": action})
    total = max(1, len(FIXTURE_CONTEXTS))
    return {
        "model": model,
        "temperature": temperature,
        "samples": total,
        "average_latency_ms": round(statistics.mean(latencies) * 1000, 1),
        "timeout_or_fallback_rate": round(100 * fallback / total, 1),
        "malformed_json_rate": round(100 * malformed / total, 1),
        "illegal_action_rate": round(100 * illegal / total, 1),
        "action_distribution": actions,
        "style_hint": style_hint(actions),
        "sample_results": samples,
    }


def style_hint(actions):
    aggressive = actions.get("bet", 0) + actions.get("raise", 0) + actions.get("all_in", 0)
    passive = actions.get("check", 0) + actions.get("call", 0)
    if aggressive > passive:
        return "aggressive"
    if actions.get("fold", 0) > aggressive:
        return "tight"
    return "balanced"


def render_markdown(results):
    lines = ["# AI Poker local model benchmark", ""]
    for result in results:
        lines.extend(
            [
                f"## {result['model']} @ temperature {result['temperature']}",
                f"- Average latency: {result['average_latency_ms']} ms",
                f"- Timeout/fallback rate: {result['timeout_or_fallback_rate']}%",
                f"- Malformed JSON rate: {result['malformed_json_rate']}%",
                f"- Illegal-action rate before engine correction: {result['illegal_action_rate']}%",
                f"- Action distribution: `{json.dumps(result['action_distribution'], sort_keys=True)}`",
                f"- Seat calibration hint: **{result['style_hint']}**",
                "",
            ]
        )
    return "\n".join(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark local Ollama models for AI Poker")
    parser.add_argument("--models", nargs="*", help="Model names; defaults to installed Ollama models or fixture-local")
    parser.add_argument("--temperatures", nargs="*", type=float, default=[0.2, 0.35])
    parser.add_argument("--fixture", action="store_true", help="Run deterministic fixture mode without Ollama")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    models = args.models or ([] if args.fixture else get_available_models(force=True)) or ["fixture-local"]
    results = [
        benchmark_model(model, temperature, fixture=args.fixture or model == "fixture-local")
        for model in models
        for temperature in args.temperatures
    ]
    output = json.dumps(results, indent=2) if args.format == "json" else render_markdown(results)
    if args.output:
        from pathlib import Path

        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
