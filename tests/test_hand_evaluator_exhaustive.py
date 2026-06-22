"""Canonical five-card distribution proof (marked slow: 2,598,960 hands)."""

from collections import Counter
from itertools import combinations

import pytest

from deck import RANKS, SUITS
from hand_evaluator import _score_five


@pytest.mark.slow
def test_all_five_card_category_frequencies_match_canonical_counts():
    deck = [(rank, suit) for rank in RANKS for suit in SUITS]
    frequencies = Counter(_score_five(list(cards))[0] for cards in combinations(deck, 5))
    assert frequencies == {
        9: 40,
        8: 624,
        7: 3744,
        6: 5108,
        5: 10200,
        4: 54912,
        3: 123552,
        2: 1098240,
        1: 1302540,
    }
