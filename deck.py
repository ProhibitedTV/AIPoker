"""Deterministic standard-deck handling for Texas Hold'em."""

import random


SUITS = ("hearts", "diamonds", "clubs", "spades")
RANKS = tuple(range(2, 15))


class Deck:
    """A 52-card deck with injectable randomness and explicit burn cards."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.cards = []
        self.burned = []
        self.reset()

    def shuffle(self):
        self.rng.shuffle(self.cards)

    def deal_card(self):
        if not self.cards:
            raise RuntimeError("cannot deal from an empty deck")
        return self.cards.pop()

    def deal_hand(self, num_cards=2):
        return [self.deal_card() for _ in range(num_cards)]

    def burn(self):
        card = self.deal_card()
        self.burned.append(card)
        return card

    def deal_flop(self):
        return [self.deal_card() for _ in range(3)]

    def deal_turn(self):
        return self.deal_card()

    def deal_river(self):
        return self.deal_card()

    def reset(self):
        self.cards = [(rank, suit) for rank in RANKS for suit in SUITS]
        self.burned = []
        self.shuffle()
