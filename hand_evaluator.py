"""
hand_evaluator.py

This module contains functions to evaluate a poker hand by combining the player's hand with the community cards.
It supports ranking hands based on standard poker rules, including straight flushes, four-of-a-kinds, full houses,
flushes, straights, and other poker hands. The functions also return tiebreaker information for comparing hands
with the same rank (e.g., kickers for one-pair hands).

Functions:
    - evaluate_hand(hand, community_cards): Evaluates the strength of a player's hand.
    - is_straight_flush(all_cards): Checks if the hand is a straight flush.
    - is_four_of_a_kind(rank_counts): Checks if the hand is four-of-a-kind.
    - is_full_house(rank_counts): Checks if the hand is a full house.
    - is_flush(suit_counts): Checks if the hand is a flush.
    - is_straight(ranks): Checks if the hand is a straight.
    - is_three_of_a_kind(rank_counts): Checks if the hand is three-of-a-kind.
    - is_two_pair(rank_counts): Checks if the hand is two pairs.
    - is_one_pair(rank_counts): Checks if the hand is one pair.
    - get_high_card(ranks): Returns the highest card(s) for high-card hands or kickers.
    - get_best_straight(ranks): Returns the highest straight.
    - get_best_four_of_a_kind(rank_counts): Returns the rank of four-of-a-kind and a kicker.
    - get_best_full_house(rank_counts): Returns the ranks for a full house.
    - get_best_flush(all_cards): Returns the best five cards from a flush.
    - get_best_three_of_a_kind(rank_counts, all_ranks): Returns the rank of the three-of-a-kind and kickers.
    - get_best_two_pair(rank_counts, all_ranks): Returns the two pair and a kicker.
    - get_best_one_pair(rank_counts, all_ranks): Returns the rank of the pair and kickers.
"""

from collections import Counter

def evaluate_hand(hand, community_cards):
    """
    Evaluates a player's hand by combining their hand with the community cards and returning a score and high card(s) for tiebreaking.
    
    Args:
        hand (list): A list of tuples representing the player's hand (e.g., [(10, 'hearts'), (9, 'diamonds')]).
        community_cards (list): A list of tuples representing the community cards (e.g., [(2, 'clubs'), (5, 'spades'), ...]).
        
    Returns:
        tuple: A tuple (hand_rank, best_ranks) where:
               - hand_rank (int): A numerical score representing the value of the player's best hand.
               - best_ranks (list): The ranks of the cards contributing to the hand, for tiebreaking purposes.
    """
    all_cards = hand + community_cards
    all_ranks = [card[0] for card in all_cards]
    all_suits = [card[1] for card in all_cards]
    
    rank_counts = Counter(all_ranks)
    suit_counts = Counter(all_suits)

    # Check for different hands in descending order of strength
    if is_straight_flush(all_cards):
        return (9, get_best_straight(all_ranks))
    elif is_four_of_a_kind(rank_counts):
        return (8, get_best_four_of_a_kind(rank_counts))
    elif is_full_house(rank_counts):
        return (7, get_best_full_house(rank_counts))
    elif is_flush(suit_counts):
        return (6, get_best_flush(all_cards))
    elif is_straight(all_ranks):
        return (5, get_best_straight(all_ranks))
    elif is_three_of_a_kind(rank_counts):
        return (4, get_best_three_of_a_kind(rank_counts, all_ranks))
    elif is_two_pair(rank_counts):
        return (3, get_best_two_pair(rank_counts, all_ranks))
    elif is_one_pair(rank_counts):
        return (2, get_best_one_pair(rank_counts, all_ranks))
    else:
        return (1, get_high_card(all_ranks))  # High card is the lowest hand


def is_straight_flush(all_cards):
    """
    Check if the hand is a straight flush, which is five consecutive cards of the same suit.
    
    Args:
        all_cards (list): A list of tuples representing all available cards (player's hand and community cards).
    
    Returns:
        bool: True if the hand is a straight flush, False otherwise.
    """
    suits = [card[1] for card in all_cards]
    suit_counts = Counter(suits)
    
    # Find if there's a flush (5 cards of the same suit)
    for suit, count in suit_counts.items():
        if count >= 5:
            suited_cards = [card[0] for card in all_cards if card[1] == suit]
            if is_straight(suited_cards):
                return True
    return False

def is_four_of_a_kind(rank_counts):
    """
    Check if the hand contains four cards of the same rank.
    
    Args:
        rank_counts (Counter): A Counter object representing the frequency of each card rank.
    
    Returns:
        bool: True if the hand is four of a kind, False otherwise.
    """
    return 4 in rank_counts.values()

def is_full_house(rank_counts):
    """
    Check if the hand is a full house, which is a combination of three of a kind and a pair.
    
    Args:
        rank_counts (Counter): A Counter object representing the frequency of each card rank.
    
    Returns:
        bool: True if the hand is a full house, False otherwise.
    """
    return 3 in rank_counts.values() and 2 in rank_counts.values()

def is_flush(suit_counts):
    """
    Check if the hand is a flush, which is five cards of the same suit.
    
    Args:
        suit_counts (Counter): A Counter object representing the frequency of each card suit.
    
    Returns:
        bool: True if the hand is a flush, False otherwise.
    """
    return any(count >= 5 for count in suit_counts.values())

def is_straight(ranks):
    """
    Check if the hand is a straight, which is five consecutive ranks.
    
    Args:
        ranks (list): A list of card ranks.
    
    Returns:
        bool: True if the hand is a straight, False otherwise.
    """
    unique_ranks = sorted(set(ranks))
    if len(unique_ranks) < 5:
        return False
    for i in range(len(unique_ranks) - 4):
        if unique_ranks[i:i+5] == list(range(unique_ranks[i], unique_ranks[i]+5)):
            return True
    # Check for A-2-3-4-5 straight (Ace can be low)
    if set([14, 2, 3, 4, 5]).issubset(unique_ranks):
        return True
    return False

def is_three_of_a_kind(rank_counts):
    """
    Check if the hand is three of a kind, which is three cards of the same rank.
    
    Args:
        rank_counts (Counter): A Counter object representing the frequency of each card rank.
    
    Returns:
        bool: True if the hand is three of a kind, False otherwise.
    """
    return 3 in rank_counts.values()

def is_two_pair(rank_counts):
    """
    Check if the hand contains two pairs.
    
    Args:
        rank_counts (Counter): A Counter object representing the frequency of each card rank.
    
    Returns:
        bool: True if the hand contains two pairs, False otherwise.
    """
    return list(rank_counts.values()).count(2) >= 2

def is_one_pair(rank_counts):
    """
    Check if the hand contains one pair.
    
    Args:
        rank_counts (Counter): A Counter object representing the frequency of each card rank.
    
    Returns:
        bool: True if the hand contains one pair, False otherwise.
    """
    return 2 in rank_counts.values()

def get_high_card(ranks):
    """
    Get the highest card(s) for a high card hand or as kickers for tiebreaking.
    
    Args:
        ranks (list): A list of card ranks.
    
    Returns:
        list: The highest card(s) in descending order.
    """
    return sorted(ranks, reverse=True)

def get_best_straight(ranks):
    """
    Get the highest rank in a straight.
    
    Args:
        ranks (list): A list of card ranks.
    
    Returns:
        list: The highest ranks that form a straight.
    """
    unique_ranks = sorted(set(ranks))
    for i in range(len(unique_ranks) - 4):
        if unique_ranks[i:i+5] == list(range(unique_ranks[i], unique_ranks[i]+5)):
            return unique_ranks[i+4:i-1:-1]
    if set([14, 2, 3, 4, 5]).issubset(unique_ranks):
        return [5, 4, 3, 2, 14]
    return []

def get_best_four_of_a_kind(rank_counts):
    """
    Get the rank of the four of a kind and the kicker.
    
    Args:
        rank_counts (Counter): A Counter object representing the frequency of each card rank.
    
    Returns:
        list: A list with the rank of the four of a kind and the kicker.
    """
    four_rank = [rank for rank, count in rank_counts.items() if count == 4][0]
    kicker = max([rank for rank in rank_counts if rank != four_rank])
    return [four_rank, kicker]

def get_best_full_house(rank_counts):
    """
    Get the rank of the full house (three of a kind and a pair).
    
    Args:
        rank_counts (Counter): A Counter object representing the frequency of each card rank.
    
    Returns:
        list: A list with the rank of the three of a kind and the pair.
    """
    three_rank = [rank for rank, count in rank_counts.items() if count == 3][0]
    pair_rank = [rank for rank, count in rank_counts.items() if count == 2][0]
    return [three_rank, pair_rank]

def get_best_flush(all_cards):
    """
    Get the best five cards from a flush.
    
    Args:
        all_cards (list): A list of tuples representing all available cards.
    
    Returns:
        list: The five highest cards of the same suit.
    """
    suits = [card[1] for card in all_cards]
    suit_counts = Counter(suits)
    flush_suit = [suit for suit, count in suit_counts.items() if count >= 5][0]
    flush_cards = [card[0] for card in all_cards if card[1] == flush_suit]
    return sorted(flush_cards, reverse=True)[:5]

def get_best_three_of_a_kind(rank_counts, all_ranks):
    """
    Get the rank of the three of a kind and the two kickers.
    
    Args:
        rank_counts (Counter): A Counter object representing the frequency of each card rank.
        all_ranks (list): A list of all available card ranks.
    
    Returns:
        list: A list containing the rank of the three of a kind and two kicker cards.
    """
    three_rank = [rank for rank, count in rank_counts.items() if count == 3][0]
    kickers = sorted([rank for rank in all_ranks if rank != three_rank], reverse=True)[:2]
    return [three_rank] + kickers

def get_best_two_pair(rank_counts, all_ranks):
    """
    Get the ranks of the two pairs and the kicker.
    
    Args:
        rank_counts (Counter): A Counter object representing the frequency of each card rank.
        all_ranks (list): A list of all available card ranks.
    
    Returns:
        list: A list containing the two pair ranks and a kicker card.
    """
    pairs = sorted([rank for rank, count in rank_counts.items() if count == 2], reverse=True)[:2]
    kicker = max([rank for rank in all_ranks if rank not in pairs])
    return pairs + [kicker]

def get_best_one_pair(rank_counts, all_ranks):
    """
    Get the rank of the pair and the three kickers.
    
    Args:
        rank_counts (Counter): A Counter object representing the frequency of each card rank.
        all_ranks (list): A list of all available card ranks.
    
    Returns:
        list: A list containing the rank of the pair and three kicker cards.
    """
    pair = [rank for rank, count in rank_counts.items() if count == 2][0]
    kickers = sorted([rank for rank in all_ranks if rank != pair], reverse=True)[:3]
    return [pair] + kickers
