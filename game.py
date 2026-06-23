"""Auditable No-Limit Texas Hold'em rules engine and broadcast state."""

from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import time
from threading import Condition, RLock

from analysis import EquityCalculator
from deck import Deck
from hand_evaluator import evaluate_hand
from player import AIPlayer, PlayerProfile


DEFAULT_TOURNAMENT_LEVELS = (
    (10, 20, 0),
    (15, 30, 0),
    (25, 50, 0),
    (40, 80, 80),
    (60, 120, 120),
    (100, 200, 200),
    (150, 300, 300),
    (250, 500, 500),
    (400, 800, 800),
    (600, 1200, 1200),
    (1000, 2000, 2000),
)


class PokerGame:
    HAND_NAMES = {
        9: "Straight Flush",
        8: "Four of a Kind",
        7: "Full House",
        6: "Flush",
        5: "Straight",
        4: "Three of a Kind",
        3: "Two Pair",
        2: "One Pair",
        1: "High Card",
    }

    def __init__(
        self,
        num_players=4,
        starting_chips=1000,
        small_blind=10,
        big_blind=20,
        metrics_store=None,
        decision_provider=None,
        mode="cash",
        profiles=None,
        rng_seed=None,
        hands_per_level=8,
        tournament_levels=None,
        history_path=None,
        checkpoint_path=None,
        auto_restore=True,
        equity_samples=1600,
        analysis_depth="full",
        action_delay_ms=0,
        deal_delay_ms=0,
        sleep_provider=None,
    ):
        if not 2 <= int(num_players) <= 6:
            raise ValueError("table size must be between 2 and 6")
        if int(starting_chips) <= 0:
            raise ValueError("starting chips must be positive")
        if int(small_blind) <= 0 or int(big_blind) <= int(small_blind):
            raise ValueError("blinds must be positive and the big blind must exceed the small blind")
        self.num_players = int(num_players)
        self.starting_chips = int(starting_chips)
        self.base_small_blind = int(small_blind)
        self.base_big_blind = int(big_blind)
        self.small_blind = self.base_small_blind
        self.big_blind = self.base_big_blind
        self.ante = 0
        self.mode = "tournament" if mode in {"tournament", "sit_and_go", "sng"} else "cash"
        self.rng_seed = rng_seed
        self.rng = random.Random(rng_seed)
        profile_values = list(profiles or [])
        self.players = []
        profile_ids = set()
        profile_names = set()
        for seat in range(self.num_players):
            profile = PlayerProfile.from_value(
                profile_values[seat] if seat < len(profile_values) else None,
                seat,
            )
            if profile.id in profile_ids or profile.name in profile_names:
                raise ValueError("player profile IDs and names must be unique")
            profile_ids.add(profile.id)
            profile_names.add(profile.name)
            self.players.append(
                AIPlayer(
                    profile.name,
                    self.starting_chips,
                    decision_provider,
                    seat=seat,
                    profile=profile,
                )
            )

        self.deck = Deck(self.rng)
        self.community_cards = []
        self.pot = 0
        self.pots = []
        self.log = deque(maxlen=2000)
        self.commentary = deque(maxlen=30)
        self.action_history = deque(maxlen=80)
        self.dealer_position = -1
        self.small_blind_position = None
        self.big_blind_position = None
        self.next_to_act = None
        self.current_bet_to_match = 0
        self.last_full_raise = self.big_blind
        self.last_full_bet_level = 0
        self.stage = "Waiting"
        self.hand_number = 0
        self.tournament_number = 1
        self.tournament_hand_number = 0
        self.tournament_complete = False
        self.tournament_winner = None
        self.eliminations = []
        self.hands_per_level = max(1, int(hands_per_level))
        self.tournament_levels = self._normalize_levels(tournament_levels)
        self.metrics_store = metrics_store
        self.history_path = Path(history_path) if history_path else None
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else None
        self._opening_chips = {}
        self._hand_events = []
        self._preflop_raise_count = 0
        self._last_talk_hand = {}
        self.hand_in_progress = False
        self._listeners = []
        self._lock = RLock()
        self._event_condition = Condition()
        self._events = deque(maxlen=512)
        self._event_sequence = 0
        self._equity = EquityCalculator(samples=equity_samples)
        self.analysis_depth = analysis_depth if analysis_depth in {"full", "essential", "off"} else "full"
        self.action_delay_ms = max(0, int(action_delay_ms))
        self.deal_delay_ms = max(0, int(deal_delay_ms))
        self._sleep = sleep_provider or time.sleep
        self.service_health = {
            "ollama": "unknown",
            "overlay": "unknown",
            "persistence": "ready" if self.history_path or self.checkpoint_path else "disabled",
            "checkpoint": "standby" if self.checkpoint_path else "disabled",
        }
        self.audio_state = {
            "enabled": True,
            "master": 0.35,
            "ambience_enabled": True,
            "ambience": 0.16,
            "effects": 0.72,
            "music_enabled": True,
            "music": 0.18,
            "music_tracks": 0,
        }

        if metrics_store:
            for player in self.players:
                metrics_store.adopt_player_alias(f"AI Player {player.seat + 1}", player)
                saved = metrics_store.player(player.name)
                player.wins = saved["hands_won"]
                player.ties = saved.get("hands_tied", 0)
                player.total_rounds = saved["hands_played"]
        if auto_restore:
            self.restore_checkpoint()

    @staticmethod
    def _normalize_levels(levels):
        if not levels:
            return list(DEFAULT_TOURNAMENT_LEVELS)
        normalized = []
        for level in levels:
            if isinstance(level, dict):
                normalized.append((int(level["small"]), int(level["big"]), int(level.get("ante", 0))))
            else:
                small, big, *ante = level
                normalized.append((int(small), int(big), int(ante[0]) if ante else 0))
        if not normalized or any(small <= 0 or big <= small or ante < 0 for small, big, ante in normalized):
            raise ValueError("tournament levels require positive increasing blinds and a nonnegative ante")
        return normalized

    def subscribe(self, listener):
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener) if listener in self._listeners else None

    def _emit(self, event_type, message="", **details):
        with self._event_condition:
            self._event_sequence += 1
            event = {
                "id": self._event_sequence,
                "type": event_type,
                "message": message,
                "hand_number": self.hand_number,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **details,
            }
            self._events.append(event)
            if self.hand_in_progress or event_type in {"hand_started", "winner", "pot_awarded"}:
                self._hand_events.append(event)
            self._event_condition.notify_all()
        if message:
            self.log.append(message)
        if event_type in {"action", "community", "winner", "table_talk"} and message:
            self.commentary.append(message)
        for listener in tuple(self._listeners):
            try:
                listener(event)
            except Exception:
                continue
        return event

    def events_since(self, sequence=0):
        with self._event_condition:
            return [dict(event) for event in self._events if event["id"] > int(sequence or 0)]

    def wait_for_events(self, sequence=0, timeout=10):
        with self._event_condition:
            events = [event for event in self._events if event["id"] > int(sequence or 0)]
            if not events:
                self._event_condition.wait(timeout=timeout)
                events = [event for event in self._events if event["id"] > int(sequence or 0)]
            return [dict(event) for event in events]

    # ----- hand lifecycle -------------------------------------------------

    def play_pre_flop(self):
        self._ensure_playable_table()
        self.hand_number += 1
        if self.mode == "tournament":
            self.tournament_hand_number += 1
            self._apply_tournament_level()
        self.stage = "Pre-Flop"
        self.deck.reset()
        self.community_cards = []
        self.pot = 0
        self.pots = []
        self.action_history.clear()
        self._hand_events = []
        self._preflop_raise_count = 0
        self._rotate_button()
        for player in self.players:
            player.reset_for_next_round()
        self._opening_chips = {player.name: player.chips for player in self.players}
        self.hand_in_progress = True
        self._emit(
            "hand_started",
            f"Hand {self.hand_number} begins.",
            mode=self.mode,
            dealer=self.dealer_position,
        )
        self._deal_hole_cards()
        self._post_antes_and_blinds()
        self.betting_round("Pre-Flop", reset_bets=False)
        self._emit("state")

    def _ensure_playable_table(self):
        if self.mode == "cash":
            reloaded = []
            for player in self.players:
                if player.chips <= 0:
                    player.chips = self.starting_chips
                    player.eliminated = False
                    reloaded.append(player)
                    if self.metrics_store:
                        self.metrics_store.record_buy_in(player, self.starting_chips)
            if reloaded:
                self._emit(
                    "table_reload",
                    f"{', '.join(player.name for player in reloaded)} reload for {self.starting_chips}.",
                )
            return
        funded = [player for player in self.players if player.chips > 0 and not player.eliminated]
        if self.tournament_complete or len(funded) <= 1:
            self._start_new_tournament()

    def _start_new_tournament(self):
        self.tournament_number += 1 if self.hand_number else 0
        self.tournament_hand_number = 0
        self.tournament_complete = False
        self.tournament_winner = None
        self.eliminations = []
        self.dealer_position = -1
        for player in self.players:
            player.chips = self.starting_chips
            player.eliminated = False
            player.is_active = True
        self._apply_tournament_level()
        self._emit("tournament_started", f"Sit-and-go {self.tournament_number} begins.")

    def _apply_tournament_level(self):
        level_index = max(0, (max(1, self.tournament_hand_number) - 1) // self.hands_per_level)
        if level_index < len(self.tournament_levels):
            small, big, ante = self.tournament_levels[level_index]
        else:
            extra = level_index - len(self.tournament_levels) + 1
            small, big, ante = self.tournament_levels[-1]
            multiplier = 2 ** extra
            small, big, ante = small * multiplier, big * multiplier, ante * multiplier
        self.small_blind, self.big_blind, self.ante = small, big, ante

    def _funded_seats(self):
        return [player.seat for player in self.players if player.chips > 0 and not player.eliminated]

    def _next_seat(self, seat, predicate=None):
        predicate = predicate or (lambda player: player.chips > 0 and not player.eliminated)
        for offset in range(1, self.num_players + 1):
            candidate = (seat + offset) % self.num_players
            if predicate(self.players[candidate]):
                return candidate
        return None

    def _rotate_button(self):
        funded = self._funded_seats()
        if len(funded) == 2:
            if self.dealer_position not in funded:
                self.dealer_position = funded[0]
            else:
                self.dealer_position = self._next_seat(self.dealer_position)
        elif self.mode == "tournament":
            self.dealer_position = (self.dealer_position + 1) % self.num_players
        else:
            self.dealer_position = self._next_seat(self.dealer_position)

    def _deal_hole_cards(self):
        participants = self._funded_seats()
        dealt = {seat: [] for seat in participants}
        first = self._next_seat(self.dealer_position)
        order = self._ordered_from(first, lambda player: player.seat in participants)
        for _round in range(2):
            for seat in order:
                dealt[seat].append(self.deck.deal_card())
        for seat in order:
            player = self.players[seat]
            player.deal_hand(dealt[seat])
            cards = ", ".join(self.format_card(card) for card in player.hand)
            self._emit(
                "deal",
                f"{player.name} is dealt {cards}.",
                player=player.name,
                player_id=player.id,
                seat=seat,
                cards=[self.card_to_dict(card) for card in player.hand],
            )
            self._presentation_pause(self.deal_delay_ms)

    def _post_antes_and_blinds(self):
        funded = self._funded_seats()
        if len(funded) == 2:
            self.small_blind_position = self.dealer_position
            self.big_blind_position = self._next_seat(self.dealer_position)
        else:
            self.small_blind_position = self._next_seat(self.dealer_position)
            self.big_blind_position = self._next_seat(self.small_blind_position)
        if self.ante:
            player = self.players[self.big_blind_position]
            paid = player.commit(self.ante, street=False)
            self.pot += paid
            self._emit_wager(player, "Big blind ante", paid, "ante")
        for seat, amount, label, action in (
            (self.small_blind_position, self.small_blind, "Small blind", "small_blind"),
            (self.big_blind_position, self.big_blind, "Big blind", "big_blind"),
        ):
            player = self.players[seat]
            paid = player.post_blind(amount, label)
            self.pot += paid
            self._emit_wager(player, label, paid, action)

    def _emit_wager(self, player, label, paid, action):
        suffix = " and is all-in" if player.all_in else ""
        message = f"{player.name} posts {label.lower()} {paid}{suffix}."
        self.action_history.append({"seat": player.seat, "action": action, "amount": paid})
        self._emit(
            "action",
            message,
            player=player.name,
            player_id=player.id,
            seat=player.seat,
            action=action,
            amount=paid,
            target=player.current_bet,
        )
        self._presentation_pause(self.deal_delay_ms)

    def play_flop(self):
        if not self.hand_in_progress or self._only_one_remaining():
            return
        self.stage = "Flop"
        self._start_new_street()
        self._burn("flop")
        self.community_cards.extend(self.deck.deal_flop())
        self._emit_community("Flop", self.community_cards[-3:])
        self.betting_round("Flop", reset_bets=False)

    def play_turn(self):
        if not self.hand_in_progress or self._only_one_remaining():
            return
        self.stage = "Turn"
        self._start_new_street()
        self._burn("turn")
        card = self.deck.deal_turn()
        self.community_cards.append(card)
        self._emit_community("Turn", [card])
        self.betting_round("Turn", reset_bets=False)

    def play_river(self):
        if not self.hand_in_progress or self._only_one_remaining():
            return
        self.stage = "River"
        self._start_new_street()
        self._burn("river")
        card = self.deck.deal_river()
        self.community_cards.append(card)
        self._emit_community("River", [card])
        self.betting_round("River", reset_bets=False)

    def _start_new_street(self):
        self.current_bet_to_match = 0
        self.last_full_raise = self.big_blind
        self.last_full_bet_level = 0
        for player in self.players:
            player.current_bet = 0
            player.acted_since_full_raise = False

    def _burn(self, street):
        self.deck.burn()
        self._emit("burn", "", street=street, count=len(self.deck.burned))

    def _emit_community(self, label, cards):
        names = ", ".join(self.format_card(card) for card in cards)
        self._emit(
            "community",
            f"{label} reveals {names}.",
            street=label.lower(),
            cards=[self.card_to_dict(card) for card in cards],
        )

    def play_hand(self):
        self.play_pre_flop()
        if not self._only_one_remaining():
            self.play_flop()
        if not self._only_one_remaining():
            self.play_turn()
        if not self._only_one_remaining():
            self.play_river()
        return self.determine_winner()

    # ----- betting --------------------------------------------------------

    def betting_round(self, round_name, reset_bets=True):
        self._emit("round", f"{round_name} betting round.", street=round_name.lower())
        if reset_bets:
            self._start_new_street()
        current_bet = max((player.current_bet for player in self.players if player.is_active), default=0)
        if round_name == "Pre-Flop":
            # A short all-in big blind does not reduce the bring-in owed by
            # the remaining players.
            current_bet = max(current_bet, self.big_blind)
        last_full_raise = self.big_blind
        last_full_bet_level = current_bet
        self.current_bet_to_match = current_bet
        self.last_full_raise = last_full_raise
        self.last_full_bet_level = last_full_bet_level
        for player in self.players:
            player.acted_since_full_raise = False

        if round_name == "Pre-Flop":
            first = self.dealer_position if len(self._funded_seats()) == 2 else self._next_seat(self.big_blind_position)
        else:
            first = self._next_seat(self.dealer_position)
        cursor = first
        actions = 0
        while not self._only_one_remaining():
            candidates = [
                player.seat
                for player in self.players
                if player.can_act
                and (not player.acted_since_full_raise or player.current_bet < current_bet)
            ]
            if not candidates:
                break
            seat = self._first_candidate_from(cursor, set(candidates))
            if seat is None:
                break
            player = self.players[seat]
            self.next_to_act = seat
            legal = self.legal_actions(
                seat,
                current_bet=current_bet,
                last_full_raise=last_full_raise,
                last_full_bet_level=last_full_bet_level,
            )
            context = self._decision_context(player, legal, current_bet, last_full_raise)
            raw = player.request_decision(context)
            if isinstance(raw, dict) and raw.get("_model_status"):
                self.service_health["ollama"] = raw["_model_status"]
            action, target, table_talk = self._normalize_decision(raw, legal, player)
            old_bet = current_bet
            result = self._apply_action(player, action, target, current_bet)
            current_bet = max(current_bet, player.current_bet)
            increase = current_bet - old_bet
            full_reopen = False
            if increase > 0:
                if old_bet == 0 and increase >= self.big_blind:
                    last_full_raise = increase
                    full_reopen = True
                elif increase >= last_full_raise:
                    last_full_raise = increase
                    full_reopen = True
                elif current_bet - last_full_bet_level >= last_full_raise:
                    full_reopen = True
                if full_reopen:
                    last_full_bet_level = current_bet
                    for other in self.players:
                        if other.seat != seat and other.can_act:
                            other.acted_since_full_raise = False
            self.current_bet_to_match = current_bet
            self.last_full_raise = last_full_raise
            self.last_full_bet_level = last_full_bet_level
            player.acted_since_full_raise = True
            self._record_action(player, result, table_talk)
            self._presentation_pause(self.action_delay_ms)
            cursor = (seat + 1) % self.num_players
            actions += 1
            if actions > self.num_players * 30:
                raise RuntimeError("betting round exceeded safety action limit")
        self.next_to_act = None
        self._refund_uncalled_excess()
        self.pots = self.build_side_pots()
        self._emit("pot_updated", "", pot=self.pot, pots=self.pots)
        self._emit("state")

    def legal_actions(self, seat, current_bet=None, last_full_raise=None, last_full_bet_level=None):
        player = self.players[seat]
        if not player.can_act:
            return []
        current_bet = max(
            (candidate.current_bet for candidate in self.players if candidate.is_active),
            default=0,
        ) if current_bet is None else current_bet
        last_full_raise = self.big_blind if last_full_raise is None else max(1, last_full_raise)
        last_full_bet_level = current_bet if last_full_bet_level is None else last_full_bet_level
        to_call = max(0, current_bet - player.current_bet)
        maximum_target = player.current_bet + player.chips
        actions = []
        if to_call:
            actions.append({"action": "fold"})
            actions.append(
                {
                    "action": "call",
                    "amount": min(to_call, player.chips),
                    "target": min(current_bet, maximum_target),
                }
            )
        else:
            actions.append({"action": "check"})

        if maximum_target > current_bet and not player.acted_since_full_raise:
            if current_bet == 0:
                minimum_target = min(maximum_target, self.big_blind)
                if maximum_target >= self.big_blind:
                    actions.append(
                        {
                            "action": "bet",
                            "min_target": self.big_blind,
                            "max_target": maximum_target,
                        }
                    )
            else:
                minimum_target = (
                    self.big_blind
                    if last_full_bet_level == 0 and current_bet < self.big_blind
                    else current_bet + last_full_raise
                )
                if maximum_target >= minimum_target:
                    actions.append(
                        {
                            "action": "raise",
                            "min_target": minimum_target,
                            "max_target": maximum_target,
                        }
                    )
        if player.chips > 0 and (maximum_target <= current_bet or not player.acted_since_full_raise):
            actions.append({"action": "all_in", "target": maximum_target})
        return actions

    def _decision_context(self, player, legal, current_bet, last_full_raise):
        to_call = max(0, current_bet - player.current_bet)
        call_amount = min(player.chips, to_call)
        pot_odds = 0.0 if call_amount <= 0 else round(100 * call_amount / (self.pot + call_amount), 1)
        category, ranks = evaluate_hand(player.hand, self.community_cards)
        public_players = []
        for other in self.players:
            public_players.append(
                {
                    "id": other.id,
                    "name": other.name,
                    "seat": other.seat,
                    "stack": other.chips,
                    "status": other.status,
                    "street_commitment": other.current_bet,
                    "hand_commitment": other.total_committed,
                    "last_action": other.last_action,
                }
            )
        return {
            "schema_version": 1,
            "player": {
                "id": player.id,
                "name": player.name,
                "seat": player.seat,
                "stack": player.chips,
                "hole_cards": [self.card_to_dict(card) for card in player.hand],
            },
            "profile": {
                "persona": player.profile.persona,
                "model": player.profile.model,
                "temperature": player.profile.temperature,
            },
            "street": self.stage.lower(),
            "community_cards": [self.card_to_dict(card) for card in self.community_cards],
            "community_cards_raw": list(self.community_cards),
            "pot": self.pot,
            "blinds": {"small": self.small_blind, "big": self.big_blind, "ante": self.ante},
            "position": self._position_name(player.seat),
            "to_call": to_call,
            "pot_odds_percent": pot_odds,
            "minimum_full_raise": last_full_raise,
            "legal_actions": legal,
            "players": public_players,
            "action_history": list(self.action_history),
            "strategy_hint": {
                "made_hand": self.describe_evaluation(category, ranks),
                "tiebreak_ranks": ranks,
                "pot_odds_percent": pot_odds,
            },
        }

    @staticmethod
    def _normalize_decision(raw, legal, player):
        if isinstance(raw, dict):
            action = str(raw.get("action", "")).lower().replace("-", "_")
            target = raw.get("amount", raw.get("target"))
            table_talk = str(raw.get("table_talk", ""))[:100].replace("\n", " ").strip()
        else:
            action = str(raw or "").lower().strip().replace("-", "_")
            target = None
            table_talk = ""
        aliases = {"allin": "all_in", "all in": "all_in"}
        action = aliases.get(action, action)
        legal_by_name = {item["action"]: item for item in legal}
        if action == "check" and "check" not in legal_by_name and "call" in legal_by_name:
            action = "call"
        if action == "bet" and "bet" not in legal_by_name and "raise" in legal_by_name:
            action = "raise"
        if action == "raise" and "raise" not in legal_by_name and "all_in" in legal_by_name:
            action = "all_in"
        if action not in legal_by_name:
            if "check" in legal_by_name:
                action = "check"
            elif "call" in legal_by_name and legal_by_name["call"]["amount"] <= max(1, player.chips // 10):
                action = "call"
            else:
                action = "fold"
        contract = legal_by_name[action]
        if action in {"bet", "raise"}:
            minimum = contract["min_target"]
            maximum = contract["max_target"]
            try:
                target = int(target)
            except (TypeError, ValueError):
                target = minimum
            target = max(minimum, min(maximum, target))
        else:
            target = contract.get("target")
        return action, target, table_talk

    def _apply_action(self, player, action, target, current_bet):
        player.last_wager = 0
        if action == "fold":
            player.folded = True
            player.is_active = False
            player.last_action = "Folded"
            return {"action": action, "amount": 0, "target": player.current_bet}
        if action == "check":
            player.last_action = "Checked"
            return {"action": action, "amount": 0, "target": player.current_bet}
        if action == "call":
            paid = player.commit(max(0, min(player.chips, current_bet - player.current_bet)))
            player.calls += 1
            if self.stage == "Pre-Flop":
                player.voluntarily_put_money = True
            player.last_action = f"Called {paid}" + (" (all-in)" if player.all_in else "")
            return {"action": action, "amount": paid, "target": player.current_bet}

        if action == "all_in":
            target = player.current_bet + player.chips
        old_bet = player.current_bet
        paid = player.wager_to(target)
        self.pot += paid
        aggressive = player.current_bet > current_bet
        actual_action = action
        if action == "all_in":
            if player.current_bet <= current_bet:
                actual_action = "call"
                player.calls += 1
            else:
                actual_action = "bet" if current_bet == 0 else "raise"
        if aggressive:
            player.bets_raises += 1
            if self.stage == "Pre-Flop":
                player.voluntarily_put_money = True
                player.preflop_raised = True
                if self._preflop_raise_count >= 1:
                    player.three_bet = True
                self._preflop_raise_count += 1
        elif self.stage == "Pre-Flop" and paid:
            player.voluntarily_put_money = True
        if player.all_in:
            player.all_in_counted = True
        if action == "all_in":
            player.last_action = f"All-in {player.current_bet}"
        elif actual_action == "bet":
            player.last_action = f"Bet {player.current_bet}"
        else:
            player.last_action = f"Raised to {player.current_bet}"
        return {"action": action, "amount": paid, "target": player.current_bet, "old_target": old_bet}

    def _record_action(self, player, result, table_talk):
        self.pot += player.last_wager if result["action"] in {"call"} else 0
        action = result["action"]
        amount = result["amount"]
        target = result["target"]
        if action == "fold":
            message = f"{player.name} folds."
        elif action == "check":
            message = f"{player.name} checks."
        elif action == "call":
            message = f"{player.name} calls {amount}" + (" and is all-in." if player.all_in else ".")
        elif action == "all_in":
            message = f"{player.name} moves all-in to {target}."
        elif action == "bet":
            message = f"{player.name} bets {amount}."
        else:
            message = f"{player.name} raises to {target}."
        record = {"seat": player.seat, "player_id": player.id, "action": action, "amount": amount, "target": target}
        self.action_history.append(record)
        self._emit("action", message, player=player.name, **record)
        if table_talk and self.hand_number - self._last_talk_hand.get(player.id, -3) >= 3:
            self._last_talk_hand[player.id] = self.hand_number
            self._emit("table_talk", f"{player.name}: {table_talk}", player=player.name, player_id=player.id)

    def _only_one_remaining(self):
        return sum(player.is_active and not player.folded for player in self.players) <= 1

    def _presentation_pause(self, milliseconds):
        """Pace broadcast events off the UI thread without affecting tests/soaks by default."""
        if milliseconds > 0:
            self._sleep(milliseconds / 1000)

    def _first_candidate_from(self, start, candidates):
        for offset in range(self.num_players):
            seat = (start + offset) % self.num_players
            if seat in candidates:
                return seat
        return None

    def _ordered_from(self, start, predicate):
        if start is None:
            return []
        return [
            seat
            for offset in range(self.num_players)
            for seat in [(start + offset) % self.num_players]
            if predicate(self.players[seat])
        ]

    def _position_name(self, seat):
        if seat == self.dealer_position:
            return "button"
        if seat == self.small_blind_position:
            return "small blind"
        if seat == self.big_blind_position:
            return "big blind"
        return "early" if self.num_players <= 4 else "middle"

    # ----- pots and showdown ---------------------------------------------

    def _refund_uncalled_excess(self):
        contributions = sorted(
            ((player.total_committed, player) for player in self.players if player.total_committed > 0),
            reverse=True,
            key=lambda item: item[0],
        )
        if len(contributions) < 2 or contributions[0][0] == contributions[1][0]:
            return 0
        highest, player = contributions[0]
        excess = highest - contributions[1][0]
        player.total_committed -= excess
        street_return = min(player.current_bet, excess)
        player.current_bet -= street_return
        player.chips += excess
        self.pot -= excess
        self._emit(
            "uncalled_return",
            f"Uncalled {excess} is returned to {player.name}.",
            player=player.name,
            player_id=player.id,
            amount=excess,
        )
        return excess

    def build_side_pots(self):
        contributions = {player.seat: player.total_committed for player in self.players if player.total_committed > 0}
        if not contributions:
            eligible = [player.id for player in self.players if player.is_active and not player.folded]
            return [{"index": 0, "kind": "main", "amount": self.pot, "eligible": eligible}] if self.pot else []
        levels = sorted(set(contributions.values()))
        previous = 0
        pots = []
        carry = 0
        for level in levels:
            contributors = [seat for seat, amount in contributions.items() if amount >= level]
            amount = (level - previous) * len(contributors) + carry
            eligible = [
                self.players[seat].id
                for seat in contributors
                if self.players[seat].is_active and not self.players[seat].folded
            ]
            if eligible:
                pots.append(
                    {
                        "index": len(pots),
                        "kind": "main" if not pots else "side",
                        "amount": amount,
                        "eligible": eligible,
                        "contributors": [self.players[seat].id for seat in contributors],
                    }
                )
                carry = 0
            else:
                carry = amount
            previous = level
        if carry and pots:
            pots[-1]["amount"] += carry
        return pots

    def determine_winner(self):
        with self._lock:
            if not self.hand_in_progress:
                return None, "No winner"
            self.stage = "Showdown"
            self.next_to_act = None
            self.current_bet_to_match = 0
            self._refund_uncalled_excess()
            self.pots = self.build_side_pots()
            active = [player for player in self.players if player.is_active and not player.folded]
            if not active:
                self._finish_hand([])
                self._emit("winner", "No active players. The hand has no winner.")
                return None, "No winner"

            values = {}
            descriptions = {}
            if len(active) > 1:
                for player in active:
                    player.went_to_showdown = True
                    hand_value, best_ranks = evaluate_hand(player.hand, self.community_cards)
                    values[player.id] = (hand_value, best_ranks)
                    descriptions[player.id] = self.describe_evaluation(hand_value, best_ranks)
                    self._emit(
                        "evaluation",
                        f"{player.name}: {descriptions[player.id]}.",
                        player_id=player.id,
                        category=hand_value,
                        tiebreakers=best_ranks,
                    )

            payouts = {player.id: 0 for player in self.players}
            winner_ids = []
            winning_hand = "Uncontested"
            winning_detail = "Uncontested"
            for pot in self.pots or [{"index": 0, "kind": "main", "amount": self.pot, "eligible": [active[0].id]}]:
                eligible = [player for player in active if player.id in pot["eligible"]]
                if not eligible:
                    continue
                if len(active) == 1:
                    winners = eligible
                else:
                    best = max(values[player.id] for player in eligible)
                    winners = [player for player in eligible if values[player.id] == best]
                    if pot["index"] == 0:
                        winning_hand = self.describe_hand_value(best[0])
                        winning_detail = self.describe_evaluation(best[0], best[1])
                share, odd = divmod(pot["amount"], len(winners))
                ordered = sorted(
                    winners,
                    key=lambda player: (player.seat - self.dealer_position - 1) % self.num_players,
                )
                for index, player in enumerate(ordered):
                    award = share + (1 if index < odd else 0)
                    player.chips += award
                    payouts[player.id] += award
                    if player.id not in winner_ids:
                        winner_ids.append(player.id)
                self._emit(
                    "pot_awarded",
                    f"{pot['kind'].title()} pot {pot['amount']} awarded to {', '.join(player.name for player in winners)}.",
                    pot_index=pot["index"],
                    amount=pot["amount"],
                    players=[player.id for player in winners],
                )

            self.pot = 0
            winner_players = [player for player in self.players if player.id in winner_ids]
            for player in winner_players:
                player.last_action = f"Won {payouts[player.id]}"
                if len(winner_players) == 1:
                    player.wins += 1
                else:
                    player.ties += 1
                if player.went_to_showdown:
                    player.won_at_showdown = True
            winner_names = [player.name for player in winner_players]
            total_awarded = sum(payouts.values())
            if len(winner_players) == 1:
                message = f"{winner_players[0].name} wins {total_awarded} with {winning_detail}."
            else:
                message = f"{' and '.join(winner_names)} share the pots with {winning_detail}."
            self._update_tournament_status(winner_ids)
            self._emit(
                "winner",
                message,
                players=winner_names,
                player_ids=winner_ids,
                hand=winning_hand,
                hand_detail=winning_detail,
                amount=total_awarded,
                split=len(winner_players) > 1,
                payouts=payouts,
            )
            self._finish_hand(winner_names, payouts)
            return winner_players[0], winning_hand

    def _update_tournament_status(self, winner_ids=None):
        if self.mode != "tournament":
            return
        newly_busted = [
            player
            for player in self.players
            if player.chips <= 0 and not player.eliminated
        ]
        newly_busted.sort(key=lambda player: (self._opening_chips.get(player.name, 0), player.seat))
        for player in newly_busted:
            player.eliminated = True
            player.is_active = False
            remaining = sum(not candidate.eliminated for candidate in self.players)
            finish = remaining + 1
            eliminator = winner_ids[0] if winner_ids and len(winner_ids) == 1 else None
            entry = {
                "player_id": player.id,
                "name": player.name,
                "finish": finish,
                "hand": self.tournament_hand_number,
                "eliminated_by": eliminator,
            }
            self.eliminations.append(entry)
            self._emit("elimination", f"{player.name} is eliminated in {finish}{_ordinal_suffix(finish)} place.", **entry)
        remaining = [player for player in self.players if not player.eliminated and player.chips > 0]
        if len(remaining) == 1:
            winner = remaining[0]
            self.tournament_complete = True
            self.tournament_winner = winner.id
            self._emit("tournament_winner", f"{winner.name} wins sit-and-go {self.tournament_number}.", player_id=winner.id)
            if self.metrics_store:
                self.metrics_store.record_tournament(winner, self.eliminations, self.tournament_number)

    def _finish_hand(self, winner_names, payouts=None):
        self.hand_in_progress = False
        participants = [player for player in self.players if player.hand]
        for player in participants:
            player.total_rounds += 1
        summary = {
            "hand_number": self.hand_number,
            "mode": self.mode,
            "big_blind": self.big_blind,
            "pot": sum((payouts or {}).values()),
            "payouts": payouts or {},
            "showdown": len([player for player in participants if player.went_to_showdown]) > 1,
            "burned_cards": [self.card_to_dict(card) for card in self.deck.burned],
            "rng_seed": self.rng_seed,
        }
        if self.metrics_store:
            self.metrics_store.record_hand(self.players, winner_names, self._opening_chips, summary=summary)
        self._persist_hand_history(summary)
        self.save_checkpoint()

    # ----- persistence and recovery --------------------------------------

    def _persist_hand_history(self, summary):
        if not self.history_path:
            return
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            if self.history_path.exists() and self.history_path.stat().st_size > 5_000_000:
                for index in range(2, 0, -1):
                    source = self.history_path.with_suffix(self.history_path.suffix + f".{index}")
                    target = self.history_path.with_suffix(self.history_path.suffix + f".{index + 1}")
                    if source.exists():
                        os.replace(source, target)
                os.replace(self.history_path, self.history_path.with_suffix(self.history_path.suffix + ".1"))
            document = {"summary": summary, "events": self._hand_events}
            with self.history_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(document, separators=(",", ":")) + "\n")
            self.service_health["persistence"] = "ready"
        except OSError:
            self.service_health["persistence"] = "warning"

    def save_checkpoint(self):
        if not self.checkpoint_path:
            return
        document = {
            "version": 1,
            "mode": self.mode,
            "hand_number": self.hand_number,
            "tournament_number": self.tournament_number,
            "tournament_hand_number": self.tournament_hand_number,
            "dealer_position": self.dealer_position,
            "tournament_complete": self.tournament_complete,
            "tournament_winner": self.tournament_winner,
            "eliminations": self.eliminations,
            "players": [{"id": player.id, "chips": player.chips, "eliminated": player.eliminated} for player in self.players],
        }
        try:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.checkpoint_path.with_suffix(self.checkpoint_path.suffix + ".tmp")
            temporary.write_text(json.dumps(document, indent=2), encoding="utf-8")
            os.replace(temporary, self.checkpoint_path)
            self.service_health["checkpoint"] = "ready"
        except OSError:
            self.service_health["checkpoint"] = "warning"
            self.service_health["persistence"] = "warning"

    def restore_checkpoint(self):
        if not self.checkpoint_path or not self.checkpoint_path.exists():
            return False
        try:
            document = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            if document.get("mode") != self.mode:
                return False
            saved = {player["id"]: player for player in document.get("players", [])}
            if not all(player.id in saved for player in self.players):
                return False
            self.hand_number = int(document.get("hand_number", 0))
            self.tournament_number = int(document.get("tournament_number", 1))
            self.tournament_hand_number = int(document.get("tournament_hand_number", 0))
            self.dealer_position = int(document.get("dealer_position", -1))
            self.tournament_complete = bool(document.get("tournament_complete", False))
            self.tournament_winner = document.get("tournament_winner")
            self.eliminations = list(document.get("eliminations", []))
            for player in self.players:
                player.chips = int(saved[player.id]["chips"])
                player.eliminated = bool(saved[player.id].get("eliminated", False))
                player.is_active = player.chips > 0 and not player.eliminated
            self._apply_tournament_level() if self.mode == "tournament" else None
            self.stage = "Restored"
            self.service_health["checkpoint"] = "restored"
            return True
        except (OSError, ValueError, TypeError, json.JSONDecodeError, KeyError):
            self.service_health["checkpoint"] = "warning"
            return False

    def health_snapshot(self):
        """Return short, viewer-safe service states without errors or local details."""
        ollama = self.service_health.get("ollama", "unknown")
        persistence = self.service_health.get("persistence", "disabled")
        checkpoint = self.service_health.get("checkpoint", "disabled")
        audio_enabled = bool(self.audio_state.get("enabled", True))
        if persistence == "warning" or checkpoint == "warning":
            overall, label, detail = "warning", "SAVE WARNING", "Operator check recommended"
        elif ollama in {"fallback", "circuit-open", "offline", "unavailable"}:
            overall, label, detail = "degraded", "SAFE FALLBACK", "Play continues without local AI"
        elif checkpoint == "restored":
            overall, label, detail = "recovered", "RECOVERED", "Checkpoint restored"
        elif not audio_enabled:
            overall, label, detail = "notice", "AUDIO MUTED", "Game remains live"
        else:
            overall, label, detail = "normal", "TABLE HEALTHY", "Local broadcast systems ready"
        return {
            "overall": overall,
            "label": label,
            "detail": detail,
            "components": {
                "model": "online" if ollama in {"online", "preview"} else ("fallback" if ollama in {"fallback", "circuit-open", "offline", "unavailable"} else "warming"),
                "overlay": self.service_health.get("overlay", "unknown"),
                "audio": "ready" if audio_enabled else "muted",
                "persistence": persistence,
                "checkpoint": checkpoint,
            },
        }

    def recover_from_error(self, error):
        with self._lock:
            if self.hand_in_progress:
                for player in self.players:
                    if player.name in self._opening_chips:
                        player.chips = self._opening_chips[player.name]
            for player in self.players:
                player.reset_for_next_round()
            self.community_cards = []
            self.pot = 0
            self.pots = []
            self.next_to_act = None
            self.hand_in_progress = False
            self.stage = "Recovering"
            self._emit("error", f"Hand interrupted and refunded: {error}")

    # ----- public state ---------------------------------------------------

    def reset_metrics(self):
        if self.metrics_store:
            self.metrics_store.reset()
        for player in self.players:
            player.wins = 0
            player.ties = 0
            player.total_rounds = 0
        self._emit("metrics_reset", "Season statistics reset.")

    def describe_hand_value(self, hand_value):
        return self.HAND_NAMES.get(hand_value, "High Card")

    def describe_evaluation(self, hand_value, ranks):
        """Return a compact broadcast-friendly best-five description."""
        rank_name = lambda rank, plural=False: self._rank_name(rank, plural)
        if not ranks:
            return self.describe_hand_value(hand_value)
        if hand_value == 9:
            return f"{rank_name(ranks[0])}-high straight flush"
        if hand_value == 8:
            return f"four {rank_name(ranks[0], True)}"
        if hand_value == 7:
            return f"{rank_name(ranks[0], True)} full of {rank_name(ranks[1], True)}"
        if hand_value == 6:
            return f"{rank_name(ranks[0])}-high flush"
        if hand_value == 5:
            return f"{rank_name(ranks[0])}-high straight"
        if hand_value == 4:
            return f"three {rank_name(ranks[0], True)}"
        if hand_value == 3:
            return f"{rank_name(ranks[0], True)} and {rank_name(ranks[1], True)}"
        if hand_value == 2:
            return f"pair of {rank_name(ranks[0], True)}"
        return f"{rank_name(ranks[0])} high"

    @staticmethod
    def _rank_name(rank, plural=False):
        singular = {
            14: "ace", 13: "king", 12: "queen", 11: "jack", 10: "ten",
            9: "nine", 8: "eight", 7: "seven", 6: "six", 5: "five",
            4: "four", 3: "three", 2: "two",
        }.get(rank, str(rank))
        if not plural:
            return singular
        special = {
            14: "aces", 13: "kings", 12: "queens", 11: "jacks", 10: "tens",
            9: "nines", 8: "eights", 7: "sevens", 6: "sixes", 5: "fives",
            4: "fours", 3: "threes", 2: "twos",
        }
        return special.get(rank, singular + "s")

    def any_active_players(self):
        return any(player.is_active for player in self.players)

    def get_log(self):
        return list(self.log)

    def get_player_win_percentages(self):
        return {player.name: player.get_win_percentage() for player in self.players}

    def state_snapshot(self):
        with self._lock:
            dealer = None if self.dealer_position < 0 else self.players[self.dealer_position].name
            if self.analysis_depth == "off":
                equities, analysis_pending = {}, False
            else:
                equities, analysis_pending = self._equity.get_or_schedule(self.players, self.community_cards, self.hand_number)
            current_bet = (
                self.current_bet_to_match
                if self.next_to_act is not None
                else max((player.current_bet for player in self.players if player.is_active), default=0)
            )
            players = []
            leaderboard = self.metrics_store.snapshot() if self.metrics_store else None
            stats_by_name = (leaderboard or {}).get("players", {})
            for index, player in enumerate(self.players):
                legal = self.legal_actions(
                    index,
                    current_bet=current_bet,
                    last_full_raise=self.last_full_raise,
                    last_full_bet_level=self.last_full_bet_level,
                ) if index == self.next_to_act else []
                hand_name = None
                if player.hand:
                    value, ranks = evaluate_hand(player.hand, self.community_cards)
                    hand_name = self.describe_evaluation(value, ranks)
                stats = stats_by_name.get(player.name, {})
                players.append(
                    {
                        "id": player.id,
                        "seat": player.seat,
                        "name": player.name,
                        "profile": {
                            "persona": player.profile.persona,
                            "model": player.profile.model,
                            "color": player.profile.color,
                        },
                        "chips": player.chips,
                        "current_bet": player.current_bet,
                        "street_commitment": player.current_bet,
                        "hand_commitment": player.total_committed,
                        "action": player.last_action,
                        "active": player.is_active,
                        "status": player.status,
                        "all_in": player.all_in,
                        "folded": player.folded,
                        "eliminated": player.eliminated,
                        "win_percentage": round(player.get_win_percentage(), 2),
                        "ties": player.ties,
                        "is_dealer": index == self.dealer_position,
                        "is_small_blind": index == self.small_blind_position,
                        "is_big_blind": index == self.big_blind_position,
                        "next_to_act": index == self.next_to_act,
                        "hole_cards": [self.card_to_dict(card) for card in player.hand],
                        "hand_label": hand_name,
                        "equity": equities.get(player.id),
                        "legal_actions": legal,
                        "stats": {
                            "vpip": stats.get("vpip_rate", 0.0),
                            "pfr": stats.get("pfr_rate", 0.0),
                            "aggression": stats.get("aggression_factor", 0.0),
                        },
                    }
                )
            level = max(1, (max(1, self.tournament_hand_number) - 1) // self.hands_per_level + 1)
            hands_into_level = (max(1, self.tournament_hand_number) - 1) % self.hands_per_level
            return {
                "schema_version": 2,
                "event_sequence": self._event_sequence,
                "hand_number": self.hand_number,
                "mode": self.mode,
                "stage": self.stage,
                "pot": self.pot,
                "pots": list(self.pots),
                "blinds": {"small": self.small_blind, "big": self.big_blind, "ante": self.ante},
                "dealer": dealer,
                "dealer_seat": self.dealer_position,
                "next_to_act": self.next_to_act,
                "community_cards": [self.card_to_dict(card) for card in self.community_cards],
                "burn_count": len(self.deck.burned),
                "players": players,
                "action_history": list(self.action_history)[-20:],
                "commentary": list(self.commentary),
                "leaderboard": leaderboard,
                "analysis": {"pending": analysis_pending, "method": "exact-postflop/bounded-monte-carlo-preflop"},
                "tournament": {
                    "number": self.tournament_number,
                    "hand": self.tournament_hand_number,
                    "level": level,
                    "hands_remaining": self.hands_per_level - hands_into_level,
                    "complete": self.tournament_complete,
                    "winner": self.tournament_winner,
                    "eliminations": list(self.eliminations),
                } if self.mode == "tournament" else None,
                "services": dict(self.service_health),
                "health": self.health_snapshot(),
                "audio": dict(self.audio_state),
            }

    def close(self):
        self._equity.close()

    @staticmethod
    def card_to_dict(card):
        return {"rank": card[0], "suit": card[1]}

    @staticmethod
    def format_card(card):
        ranks = {11: "Jack", 12: "Queen", 13: "King", 14: "Ace"}
        return f"{ranks.get(card[0], card[0])} of {card[1]}"


def _ordinal_suffix(number):
    if 10 <= number % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
