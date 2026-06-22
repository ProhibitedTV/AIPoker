"""Atomic schema-v2 season, cash, and tournament statistics."""

import json
import os
from pathlib import Path
import shutil
from threading import RLock
from uuid import uuid4


class MetricsStore:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = RLock()
        self._data, migrated = self._load()
        if migrated:
            self._save()

    @staticmethod
    def _blank():
        return {
            "version": 2,
            "schema_version": 2,
            "session_id": str(uuid4()),
            "hands_played": 0,
            "tournaments_played": 0,
            "players": {},
            "chip_history": [],
            "tournaments": [],
            "notable_hands": [],
        }

    def _load(self):
        if not self.path.exists():
            return self._blank(), False
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict) or not isinstance(data.get("players", {}), dict):
                raise ValueError("invalid metrics document")
            migrated = int(data.get("version", 1)) < 2
            merged = {**self._blank(), **data, "version": 2, "schema_version": 2}
            for name, stats in merged["players"].items():
                merged["players"][name] = {**self._new_player(), **stats}
            if migrated:
                backup = self.path.with_suffix(self.path.suffix + ".v1.bak")
                if not backup.exists():
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(self.path, backup)
            return merged, migrated
        except (OSError, ValueError, json.JSONDecodeError):
            return self._blank(), False

    @staticmethod
    def _new_player():
        return {
            "player_id": "",
            "hands_played": 0,
            "hands_won": 0,
            "hands_tied": 0,
            "win_rate": 0.0,
            "tie_rate": 0.0,
            "chips_won": 0,
            "chips_lost": 0,
            "net_chips": 0,
            "net_big_blinds": 0.0,
            "buy_ins": 0,
            "buy_in_chips": 0,
            "vpip_count": 0,
            "vpip_rate": 0.0,
            "pfr_count": 0,
            "pfr_rate": 0.0,
            "three_bet_count": 0,
            "three_bet_rate": 0.0,
            "calls": 0,
            "bets_raises": 0,
            "aggression_factor": 0.0,
            "showdowns": 0,
            "showdowns_won": 0,
            "showdown_win_rate": 0.0,
            "all_ins": 0,
            "biggest_pot_won": 0,
            "tournaments": 0,
            "tournament_wins": 0,
            "eliminations": 0,
            "finishes": {},
            "current_streak": 0,
            "longest_winning_streak": 0,
            "longest_losing_streak": 0,
        }

    def player(self, name):
        with self._lock:
            return {**self._new_player(), **self._data.get("players", {}).get(name, {})}

    def adopt_player_alias(self, old_name, player):
        """Move legacy seat-name totals to a new stable cast identity once."""
        with self._lock:
            players = self._data["players"]
            if player.name not in players and old_name in players:
                players[player.name] = players.pop(old_name)
                players[player.name]["player_id"] = player.id
                self._save()

    def record_buy_in(self, player, amount):
        with self._lock:
            stats = self._stats_for(player)
            stats["buy_ins"] += 1
            stats["buy_in_chips"] += int(amount)
            self._save()

    def record_hand(self, players, winner_names, opening_chips, summary=None):
        summary = summary or {}
        with self._lock:
            if isinstance(winner_names, str):
                winner_names = [winner_names]
            winners = set(winner_names or [])
            split_pot = len(winners) > 1
            self._data["hands_played"] += 1
            hand_number = self._data["hands_played"]
            history = {"hand": hand_number, "mode": summary.get("mode", "cash"), "players": {}}
            big_blind = max(1, int(summary.get("big_blind", 1)))
            pot_size = int(summary.get("pot", 0))

            for player in players:
                if not getattr(player, "hand", None):
                    continue
                stats = self._stats_for(player)
                delta = player.chips - opening_chips.get(player.name, player.chips)
                stats["hands_played"] += 1
                if player.name in winners and not split_pot:
                    stats["hands_won"] += 1
                    stats["current_streak"] = max(1, stats["current_streak"] + 1)
                    stats["longest_winning_streak"] = max(stats["longest_winning_streak"], stats["current_streak"])
                    stats["biggest_pot_won"] = max(stats["biggest_pot_won"], pot_size)
                elif player.name in winners:
                    stats["hands_tied"] += 1
                    stats["current_streak"] = 0
                else:
                    stats["current_streak"] = min(-1, stats["current_streak"] - 1)
                    stats["longest_losing_streak"] = max(stats["longest_losing_streak"], abs(stats["current_streak"]))
                stats["chips_won"] += max(0, delta)
                stats["chips_lost"] += max(0, -delta)
                stats["net_chips"] += delta
                stats["net_big_blinds"] = round(stats["net_big_blinds"] + delta / big_blind, 2)
                stats["vpip_count"] += int(bool(getattr(player, "voluntarily_put_money", False)))
                stats["pfr_count"] += int(bool(getattr(player, "preflop_raised", False)))
                stats["three_bet_count"] += int(bool(getattr(player, "three_bet", False)))
                stats["calls"] += int(getattr(player, "calls", 0))
                stats["bets_raises"] += int(getattr(player, "bets_raises", 0))
                stats["showdowns"] += int(bool(getattr(player, "went_to_showdown", False)))
                stats["showdowns_won"] += int(bool(getattr(player, "won_at_showdown", False)))
                stats["all_ins"] += int(bool(getattr(player, "all_in_counted", False)))
                hands = stats["hands_played"]
                stats["win_rate"] = round(100 * stats["hands_won"] / hands, 2)
                stats["tie_rate"] = round(100 * stats["hands_tied"] / hands, 2)
                stats["vpip_rate"] = round(100 * stats["vpip_count"] / hands, 1)
                stats["pfr_rate"] = round(100 * stats["pfr_count"] / hands, 1)
                stats["three_bet_rate"] = round(100 * stats["three_bet_count"] / hands, 1)
                stats["aggression_factor"] = round(stats["bets_raises"] / max(1, stats["calls"]), 2)
                stats["showdown_win_rate"] = round(100 * stats["showdowns_won"] / max(1, stats["showdowns"]), 1)
                history["players"][player.name] = player.chips

            self._data["chip_history"].append(history)
            self._data["chip_history"] = self._data["chip_history"][-1000:]
            if pot_size >= 100 * big_blind or any(getattr(player, "all_in_counted", False) for player in players):
                self._data["notable_hands"].append(
                    {"hand": hand_number, "pot": pot_size, "winners": list(winners), "mode": summary.get("mode", "cash")}
                )
                self._data["notable_hands"] = self._data["notable_hands"][-100:]
            self._save()

    def record_tournament(self, winner, eliminations, tournament_number):
        with self._lock:
            self._data["tournaments_played"] += 1
            finishes = {entry["name"]: entry["finish"] for entry in eliminations}
            finishes[winner.name] = 1
            for name, finish in finishes.items():
                stats = self._data["players"].setdefault(name, self._new_player())
                stats["tournaments"] += 1
                stats["tournament_wins"] += int(finish == 1)
                stats["finishes"][str(finish)] = stats["finishes"].get(str(finish), 0) + 1
            for entry in eliminations:
                eliminated_by = entry.get("eliminated_by")
                if eliminated_by:
                    for stats in self._data["players"].values():
                        if stats.get("player_id") == eliminated_by:
                            stats["eliminations"] += 1
                            break
            self._data["tournaments"].append(
                {"number": tournament_number, "winner": winner.name, "finishes": finishes}
            )
            self._data["tournaments"] = self._data["tournaments"][-250:]
            self._save()

    def _stats_for(self, player):
        stats = self._data["players"].setdefault(player.name, self._new_player())
        for key, value in self._new_player().items():
            stats.setdefault(key, value.copy() if isinstance(value, dict) else value)
        stats["player_id"] = getattr(player, "id", player.name)
        return stats

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
