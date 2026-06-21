"""Durable, season-style player statistics."""

import json
import os
from pathlib import Path
from threading import RLock


class MetricsStore:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = RLock()
        self._data = self._load()

    @staticmethod
    def _blank():
        return {"version": 1, "hands_played": 0, "players": {}, "chip_history": []}

    def _load(self):
        if not self.path.exists():
            return self._blank()
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict) or not isinstance(data.get("players", {}), dict):
                raise ValueError("invalid metrics document")
            return {**self._blank(), **data}
        except (OSError, ValueError, json.JSONDecodeError):
            return self._blank()

    @staticmethod
    def _new_player():
        return {
            "hands_played": 0,
            "hands_won": 0,
            "hands_tied": 0,
            "win_rate": 0.0,
            "tie_rate": 0.0,
            "chips_won": 0,
            "chips_lost": 0,
            "net_chips": 0,
            "current_streak": 0,
            "longest_winning_streak": 0,
            "longest_losing_streak": 0,
        }

    def player(self, name):
        with self._lock:
            return {**self._new_player(), **self._data.get("players", {}).get(name, {})}

    def record_hand(self, players, winner_names, opening_chips):
        with self._lock:
            if isinstance(winner_names, str):
                winner_names = [winner_names]
            winners = set(winner_names or [])
            split_pot = len(winners) > 1
            self._data["hands_played"] += 1
            hand_number = self._data["hands_played"]
            history = {"hand": hand_number, "players": {}}

            for player in players:
                stats = self._data["players"].setdefault(player.name, self._new_player())
                for key, value in self._new_player().items():
                    stats.setdefault(key, value)
                delta = player.chips - opening_chips.get(player.name, player.chips)
                stats["hands_played"] += 1
                if player.name in winners and not split_pot:
                    stats["hands_won"] += 1
                    stats["current_streak"] = max(1, stats["current_streak"] + 1)
                    stats["longest_winning_streak"] = max(
                        stats["longest_winning_streak"], stats["current_streak"]
                    )
                elif player.name in winners:
                    stats["hands_tied"] += 1
                    stats["current_streak"] = 0
                else:
                    stats["current_streak"] = min(-1, stats["current_streak"] - 1)
                    stats["longest_losing_streak"] = max(
                        stats["longest_losing_streak"], abs(stats["current_streak"])
                    )
                stats["chips_won"] += max(0, delta)
                stats["chips_lost"] += max(0, -delta)
                stats["net_chips"] += delta
                stats["win_rate"] = round(
                    100 * stats["hands_won"] / stats["hands_played"], 2
                )
                stats["tie_rate"] = round(
                    100 * stats["hands_tied"] / stats["hands_played"], 2
                )
                history["players"][player.name] = player.chips

            self._data["chip_history"].append(history)
            self._data["chip_history"] = self._data["chip_history"][-1000:]
            self._save()

    def snapshot(self):
        with self._lock:
            return json.loads(json.dumps(self._data))

    def reset(self):
        with self._lock:
            self._data = self._blank()
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
