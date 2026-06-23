"""Inspect replayable JSONL hand histories without starting the GUI."""

import argparse
import html
import json
from pathlib import Path
import sys


def load_hands(path):
    path = Path(path)
    if not path.exists():
        return []
    hands = []
    with path.open("r", encoding="utf-8") as handle:
        for offset, line in enumerate(handle):
            line = line.strip()
            if not line:
                continue
            try:
                document = json.loads(line)
            except json.JSONDecodeError:
                continue
            document["_offset"] = offset
            hands.append(document)
    return hands


def select_hand(hands, hand_id=None, offset=None):
    if not hands:
        return None
    if offset is not None:
        for hand in hands:
            if hand.get("_offset") == offset:
                return hand
    if hand_id is not None:
        for hand in hands:
            if hand.get("summary", {}).get("hand_number") == hand_id:
                return hand
    return hands[-1]


def recent_table(hands, limit=10):
    rows = []
    for hand in hands[-max(1, int(limit)):]:
        summary = hand.get("summary", {})
        winners = ", ".join(summary.get("winners", []) or summary.get("payouts", {}).keys() or ["unknown"])
        rows.append(
            {
                "offset": hand.get("_offset"),
                "hand": summary.get("hand_number", "?"),
                "mode": summary.get("mode", "?"),
                "pot": summary.get("pot", 0),
                "winners": winners,
                "events": len(hand.get("events", [])),
            }
        )
    return rows


def render_text(hand):
    if not hand:
        return "No hand history entries found."
    summary = hand.get("summary", {})
    lines = [
        f"Hand {summary.get('hand_number', '?')} · {summary.get('mode', '?')} · pot {int(summary.get('pot', 0)):,}",
        f"Winners: {', '.join(summary.get('winners', []) or summary.get('payouts', {}).keys() or ['unknown'])}",
        f"Payouts: {summary.get('payouts', {})}",
        f"Burn cards: {len(summary.get('burned_cards', []))}",
        "",
        "Timeline:",
    ]
    for event in hand.get("events", []):
        message = event.get("message") or event.get("type", "event")
        lines.append(f"- #{event.get('id', '?')} {event.get('type', 'event')}: {message}")
    lines.append("")
    lines.append(_award_explanation(summary))
    return "\n".join(lines)


def render_markdown(hand):
    if not hand:
        return "# No hand history entries found\n"
    text = render_text(hand)
    return "# AI Poker Hand Replay\n\n```text\n" + text.replace("```", "'''") + "\n```\n"


def render_html(hand):
    body = html.escape(render_text(hand))
    return (
        "<!doctype html><meta charset='utf-8'><title>AI Poker Replay</title>"
        "<style>body{font:15px/1.45 system-ui;background:#071c13;color:#f7f3e8;padding:24px}"
        "pre{white-space:pre-wrap;background:#06120e;border:1px solid #315747;border-radius:12px;padding:18px}</style>"
        f"<h1>AI Poker Replay</h1><pre>{body}</pre>"
    )


def _award_explanation(summary):
    payouts = summary.get("payouts", {}) or {}
    if not payouts:
        return "Award explanation: no payout data was recorded for this hand."
    parts = [f"{name} received {int(amount):,} chips" for name, amount in payouts.items()]
    return "Award explanation: " + "; ".join(parts) + "."


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Replay audited AI Poker hand histories")
    parser.add_argument("--history", default="data/hand_history.jsonl")
    parser.add_argument("--list", action="store_true", help="List recent hands")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--hand", type=int, help="Hand number to replay")
    parser.add_argument("--offset", type=int, help="JSONL file offset to replay")
    parser.add_argument("--format", choices=("text", "markdown", "html"), default="text")
    parser.add_argument("--output", help="Write replay output to a file")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    hands = load_hands(args.history)
    if args.list:
        rows = recent_table(hands, args.limit)
        output = "\n".join(
            f"offset={row['offset']} hand={row['hand']} mode={row['mode']} pot={row['pot']} winners={row['winners']} events={row['events']}"
            for row in rows
        ) or "No hand history entries found."
    else:
        hand = select_hand(hands, hand_id=args.hand, offset=args.offset)
        output = {"text": render_text, "markdown": render_markdown, "html": render_html}[args.format](hand)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output + ("\n" if not output.endswith("\n") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
