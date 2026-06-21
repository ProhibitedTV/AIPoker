"""Exact best-five-card Texas Hold'em hand evaluation."""

from collections import Counter
from itertools import combinations


def evaluate_hand(hand, community_cards):
    """Return ``(category, tiebreakers)`` for the strongest available hand.

    Categories run from 1 (high card) through 9 (straight flush). Tiebreakers
    are ordered from most to least significant, so the returned tuples can be
    compared directly. When fewer than five cards are available, a partial
    score is returned for early single-player showdowns and diagnostics.
    """
    cards = list(hand) + list(community_cards)
    if not cards:
        return 1, []
    if len(cards) < 5:
        return _score_partial(cards)
    return max(_score_five(list(candidate)) for candidate in combinations(cards, 5))


def _score_five(cards):
    ranks = [card[0] for card in cards]
    counts = Counter(ranks)
    groups = sorted(((count, rank) for rank, count in counts.items()), reverse=True)
    ordered_ranks = sorted(ranks, reverse=True)
    flush = len({card[1] for card in cards}) == 1
    straight_high = _straight_high(ranks)

    if flush and straight_high:
        return 9, [straight_high]
    if groups[0][0] == 4:
        four_rank = groups[0][1]
        kicker = max(rank for rank in ranks if rank != four_rank)
        return 8, [four_rank, kicker]
    if [group[0] for group in groups] == [3, 2]:
        return 7, [groups[0][1], groups[1][1]]
    if flush:
        return 6, ordered_ranks
    if straight_high:
        return 5, [straight_high]
    if groups[0][0] == 3:
        trip_rank = groups[0][1]
        kickers = sorted((rank for rank in ranks if rank != trip_rank), reverse=True)
        return 4, [trip_rank, *kickers]

    pairs = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)
    if len(pairs) == 2:
        kicker = max(rank for rank in ranks if rank not in pairs)
        return 3, [pairs[0], pairs[1], kicker]
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = sorted((rank for rank in ranks if rank != pair), reverse=True)
        return 2, [pair, *kickers]
    return 1, ordered_ranks


def _score_partial(cards):
    ranks = [card[0] for card in cards]
    counts = Counter(ranks)
    groups = sorted(((count, rank) for rank, count in counts.items()), reverse=True)
    if groups[0][0] == 4:
        return 8, [groups[0][1], *sorted((rank for rank in ranks if rank != groups[0][1]), reverse=True)]
    if groups[0][0] == 3:
        return 4, [groups[0][1], *sorted((rank for rank in ranks if rank != groups[0][1]), reverse=True)]
    pairs = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)
    if len(pairs) >= 2:
        kickers = sorted((rank for rank in ranks if rank not in pairs[:2]), reverse=True)
        return 3, [pairs[0], pairs[1], *kickers]
    if pairs:
        kickers = sorted((rank for rank in ranks if rank != pairs[0]), reverse=True)
        return 2, [pairs[0], *kickers]
    return 1, sorted(ranks, reverse=True)


def _straight_high(ranks):
    unique = set(ranks)
    if 14 in unique:
        unique.add(1)
    ordered = sorted(unique, reverse=True)
    for high in ordered:
        if all(high - offset in unique for offset in range(5)):
            return high
    return None
