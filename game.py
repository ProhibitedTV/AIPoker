"""Core Texas Hold'em game state, events, and persistent metrics integration."""

from collections import deque
from threading import RLock

from deck import Deck
from hand_evaluator import evaluate_hand
from player import AIPlayer


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
    ):
        self.num_players = num_players
        self.starting_chips = starting_chips
        self.players = [
            AIPlayer(f"AI Player {index + 1}", starting_chips, decision_provider)
            for index in range(num_players)
        ]
        self.deck = Deck()
        self.community_cards = []
        self.pot = 0
        self.log = []
        self.commentary = deque(maxlen=30)
        self.dealer_position = -1
        self.next_to_act = None
        self.stage = "Waiting"
        self.hand_number = 0
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.metrics_store = metrics_store
        self._opening_chips = {}
        self._listeners = []
        self._lock = RLock()

        if metrics_store:
            for player in self.players:
                saved = metrics_store.player(player.name)
                player.wins = saved["hands_won"]
                player.total_rounds = saved["hands_played"]

    def subscribe(self, listener):
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener) if listener in self._listeners else None

    def _emit(self, event_type, message, **details):
        event = {"type": event_type, "message": message, **details}
        if message:
            self.log.append(message)
        if event_type in {"action", "community", "winner"} and message:
            self.commentary.append(message)
        for listener in tuple(self._listeners):
            try:
                listener(event)
            except Exception:
                continue

    def play_pre_flop(self):
        with self._lock:
            self._ensure_playable_table()
            self.hand_number += 1
            self.stage = "Pre-Flop"
            self.deck.reset()
            self.community_cards = []
            self.pot = 0
            self.dealer_position = (self.dealer_position + 1) % self.num_players
            for player in self.players:
                player.reset_for_next_round()
            self._opening_chips = {player.name: player.chips for player in self.players}
            self._emit("hand_started", f"\n--- Hand {self.hand_number} ---")

            for player in self.players:
                player.deal_hand(self.deck.deal_hand())
                cards = ", ".join(self.format_card(card) for card in player.hand)
                self._emit("deal", f"{player.name} is dealt {cards}", player=player.name)

            self._post_blinds()
            self.betting_round("Pre-Flop", reset_bets=False)
            self._emit("state", "")

    def _ensure_playable_table(self):
        if sum(player.chips > 0 for player in self.players) > 1:
            return
        for player in self.players:
            player.chips = self.starting_chips
        self._emit(
            "table_reset",
            f"Table re-seated with {self.starting_chips} chips per player for continuous play.",
        )

    def _post_blinds(self):
        if self.num_players < 2:
            return
        small_index = (self.dealer_position + 1) % self.num_players
        big_index = (self.dealer_position + 2) % self.num_players
        for index, amount, label in (
            (small_index, self.small_blind, "Small blind"),
            (big_index, self.big_blind, "Big blind"),
        ):
            player = self.players[index]
            paid = player.post_blind(amount, label)
            self.pot += paid
            self._emit("action", f"{player.name} posts {label.lower()} {paid}.", player=player.name)

    def play_flop(self):
        with self._lock:
            self.stage = "Flop"
            self.community_cards = self.deck.deal_flop()
            cards = ", ".join(self.format_card(card) for card in self.community_cards)
            self._emit("community", f"Flop reveals {cards}.")
            self.betting_round("Flop")

    def play_turn(self):
        with self._lock:
            self.stage = "Turn"
            card = self.deck.deal_turn()
            self.community_cards.append(card)
            self._emit("community", f"Turn reveals {self.format_card(card)}.")
            self.betting_round("Turn")

    def play_river(self):
        with self._lock:
            self.stage = "River"
            card = self.deck.deal_river()
            self.community_cards.append(card)
            self._emit("community", f"River reveals {self.format_card(card)}.")
            self.betting_round("River")

    def betting_round(self, round_name, reset_bets=True):
        self._emit("round", f"\n--- {round_name} Betting Round ---")
        if reset_bets:
            for player in self.players:
                player.current_bet = 0
        current_bet = max((player.current_bet for player in self.players), default=0)
        start = (self.dealer_position + 1) % self.num_players

        for offset in range(self.num_players):
            if sum(player.is_active for player in self.players) <= 1:
                break
            index = (start + offset) % self.num_players
            player = self.players[index]
            if not player.is_active or player.chips <= 0:
                continue
            self.next_to_act = index
            decision = player.make_decision(self.community_cards, current_bet)
            self.pot += player.last_wager
            current_bet = max(current_bet, player.current_bet)
            message = self._action_message(player, decision)
            self._emit("action", message, player=player.name, action=decision, amount=player.last_wager)
        self.next_to_act = None
        self._emit("state", "")

    @staticmethod
    def _action_message(player, decision):
        if decision == "fold":
            return f"{player.name} folds."
        if decision == "check":
            return f"{player.name} checks."
        verb = "bets" if decision == "bet" else "raises"
        return f"{player.name} {verb} {player.last_wager} chips."

    def determine_winner(self):
        with self._lock:
            self.stage = "Showdown"
            active = [player for player in self.players if player.is_active]
            if not active:
                self._finish_hand(None)
                self._emit("winner", "No active players. The hand has no winner.")
                return None, "No winner"

            best_player = None
            best_value = None
            winning_hand = ""
            for player in active:
                hand_value, best_ranks = evaluate_hand(player.hand, self.community_cards)
                value = (hand_value, best_ranks)
                description = self.describe_hand_value(hand_value)
                self._emit("evaluation", f"{player.name}: {description} ({best_ranks})")
                if best_value is None or value > best_value:
                    best_value = value
                    best_player = player
                    winning_hand = description

            best_player.chips += self.pot
            awarded = self.pot
            self.pot = 0
            best_player.wins += 1
            self._finish_hand(best_player.name)
            self._emit(
                "winner",
                f"{best_player.name} wins {awarded} chips with a {winning_hand}!",
                player=best_player.name,
                hand=winning_hand,
                amount=awarded,
            )
            return best_player, winning_hand

    def _finish_hand(self, winner_name):
        for player in self.players:
            player.total_rounds += 1
        if self.metrics_store:
            self.metrics_store.record_hand(self.players, winner_name, self._opening_chips)

    def reset_metrics(self):
        if self.metrics_store:
            self.metrics_store.reset()
        for player in self.players:
            player.wins = 0
            player.total_rounds = 0
        self._emit("metrics_reset", "Season statistics reset.")

    def describe_hand_value(self, hand_value):
        return self.HAND_NAMES.get(hand_value, "High Card")

    def any_active_players(self):
        return any(player.is_active for player in self.players)

    def get_log(self):
        return list(self.log)

    def get_player_win_percentages(self):
        return {player.name: player.get_win_percentage() for player in self.players}

    def state_snapshot(self):
        with self._lock:
            dealer = None if self.dealer_position < 0 else self.players[self.dealer_position].name
            players = []
            for index, player in enumerate(self.players):
                players.append(
                    {
                        "name": player.name,
                        "chips": player.chips,
                        "current_bet": player.current_bet,
                        "action": player.last_action,
                        "active": player.is_active,
                        "win_percentage": round(player.get_win_percentage(), 2),
                        "is_dealer": index == self.dealer_position,
                        "next_to_act": index == self.next_to_act,
                    }
                )
            return {
                "hand_number": self.hand_number,
                "stage": self.stage,
                "pot": self.pot,
                "blinds": {"small": self.small_blind, "big": self.big_blind},
                "dealer": dealer,
                "community_cards": [self.card_to_dict(card) for card in self.community_cards],
                "players": players,
                "commentary": list(self.commentary),
                "leaderboard": self.metrics_store.snapshot() if self.metrics_store else None,
            }

    @staticmethod
    def card_to_dict(card):
        return {"rank": card[0], "suit": card[1]}

    @staticmethod
    def format_card(card):
        ranks = {11: "Jack", 12: "Queen", 13: "King", 14: "Ace"}
        return f"{ranks.get(card[0], card[0])} of {card[1]}"
