"""AI poker player state and wager handling."""

import random

from ollama_integration import get_ai_decision


class AIPlayer:
    def __init__(self, name, chips=1000, decision_provider=None):
        self.name = name
        self.chips = chips
        self.hand = []
        self.current_bet = 0
        self.is_active = True
        self.wins = 0
        self.ties = 0
        self.total_rounds = 0
        self.last_action = "Waiting"
        self.last_wager = 0
        self._decision_provider = decision_provider or get_ai_decision

    def deal_hand(self, hand):
        self.hand = hand

    def make_decision(self, community_cards, current_bet):
        self.last_wager = 0
        if not self.is_active or self.chips <= 0:
            self.last_action = "Folded"
            return "fold"

        decision = self._decision_provider(self.hand, community_cards)
        if decision == "fold":
            self.is_active = False
            self.last_action = "Folded"
        elif decision == "check":
            self.last_action = "Checked"
        elif decision == "bet":
            target = self.calculate_bet_amount(current_bet)
            self._wager_to(target)
            self.last_action = f"Bet {self.last_wager}"
        elif decision == "raise":
            target = self.calculate_raise_amount(current_bet)
            self._wager_to(target)
            self.last_action = f"Raised {self.last_wager}"
        else:
            decision = "fold"
            self.is_active = False
            self.last_action = "Folded"
        return decision

    def _wager_to(self, target_bet):
        additional = min(self.chips, max(0, target_bet - self.current_bet))
        self.chips -= additional
        self.current_bet += additional
        self.last_wager = additional

    def post_blind(self, amount, label):
        self.last_wager = min(self.chips, amount)
        self.chips -= self.last_wager
        self.current_bet = self.last_wager
        self.last_action = f"{label} {self.last_wager}"
        if self.chips == 0:
            self.last_action += " (all-in)"
        return self.last_wager

    def calculate_bet_amount(self, current_bet):
        maximum = self.current_bet + self.chips
        minimum = max(current_bet, 50)
        upper = min(maximum, current_bet + 200)
        return maximum if upper < minimum else random.randint(minimum, upper)

    def calculate_raise_amount(self, current_bet):
        maximum = self.current_bet + self.chips
        minimum = max(current_bet + 1, current_bet * 2)
        upper = min(maximum, max(minimum, current_bet * 3 + 100))
        return maximum if maximum < minimum else random.randint(minimum, upper)

    def reset_for_next_round(self):
        self.hand = []
        self.current_bet = 0
        self.is_active = self.chips > 0
        self.last_action = "Waiting"
        self.last_wager = 0

    def get_win_percentage(self):
        return 0.0 if self.total_rounds == 0 else (self.wins / self.total_rounds) * 100

    def is_bankrupt(self):
        return self.chips <= 0
