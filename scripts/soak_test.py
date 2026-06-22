"""Accelerated rules/invariant soak; defaults to the release gate of 10,000 hands."""

import argparse
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game import PokerGame


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--hands", type=int, default=10000)
    parser.add_argument("--players", type=int, default=6, choices=range(2, 7))
    parser.add_argument("--mode", choices=("cash", "tournament"), default="cash")
    parser.add_argument("--seed", type=int, default=20260621)
    args = parser.parse_args(argv)
    rng = random.Random(args.seed)

    def decide(context):
        legal = context["legal_actions"]
        choice = rng.choice(legal)
        result = {"action": choice["action"]}
        if choice["action"] in {"bet", "raise"}:
            result["amount"] = rng.randint(choice["min_target"], choice["max_target"])
        return result

    game = PokerGame(
        args.players,
        starting_chips=2000,
        decision_provider=decide,
        rng_seed=args.seed,
        mode=args.mode,
    )
    started = time.monotonic()
    previous_total = sum(player.chips for player in game.players)
    for hand in range(1, args.hands + 1):
        game.play_hand()
        total = sum(player.chips for player in game.players)
        if total != previous_total or game.pot or any(player.chips < 0 for player in game.players):
            raise AssertionError(f"invariant failed at hand {hand}: total={total}, pot={game.pot}")
        # Prevent cash reloads from obscuring chip-conservation checks by
        # reseeding busted stacks outside the measured hand.
        if args.mode == "cash":
            for player in game.players:
                if player.chips == 0:
                    player.chips = game.starting_chips
                    previous_total += game.starting_chips
    elapsed = time.monotonic() - started
    print(f"PASS {args.hands} {args.mode} hands · {args.players} players · {elapsed:.2f}s · seed {args.seed}")


if __name__ == "__main__":
    main()
