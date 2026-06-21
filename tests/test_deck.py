import pytest
from deck import Deck


def test_deck_has_52_unique_cards():
    deck = Deck()
    assert len(deck.cards) == 52
    # ensure all cards are unique
    assert len(set(deck.cards)) == 52


def test_deal_hand_reduces_deck_size():
    deck = Deck()
    original_count = len(deck.cards)
    hand = deck.deal_hand()
    assert len(hand) == 2
    assert len(deck.cards) == original_count - 2
    # ensure no duplicate between hand and remaining deck
    assert len(set(hand + deck.cards)) == original_count


def test_deal_flop_turn_river():
    deck = Deck()
    flop = deck.deal_flop()
    assert len(flop) == 3
    turn = deck.deal_turn()
    assert isinstance(turn, tuple)
    river = deck.deal_river()
    assert isinstance(river, tuple)
    # After dealing 3 (flop), 1 (turn) and 1 (river) cards, deck should have 52 - 5 cards
    assert len(deck.cards) == 52 - 5


def test_reset_deck_restores_cards():
    deck = Deck()
    _ = deck.deal_hand()
    _ = deck.deal_flop()
    deck.reset()
    assert len(deck.cards) == 52
    assert len(set(deck.cards)) == 52
