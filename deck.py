import random

class Deck:
    def __init__(self):
        """
        Initializes a new deck of 52 cards (no jokers). Each card is represented as a tuple (rank, suit).
        Ranks range from 2 to 14, where 11 = Jack, 12 = Queen, 13 = King, 14 = Ace.
        Suits are 'hearts', 'diamonds', 'clubs', and 'spades'.
        """
        self.cards = [(rank, suit) for rank in range(2, 15) for suit in ['hearts', 'diamonds', 'clubs', 'spades']]
        self.shuffle()

    def shuffle(self):
        """
        Shuffles the deck of cards.
        """
        random.shuffle(self.cards)

    def deal_hand(self, num_cards=2):
        """
        Deals a hand of 'num_cards' cards from the deck (default is 2 cards for Texas Hold'em).
        
        Returns:
            list: A list of tuples representing the dealt cards (e.g., [(10, 'hearts'), (9, 'diamonds')]).
        """
        return [self.cards.pop() for _ in range(num_cards)]

    def deal_flop(self):
        """
        Deals the 'flop', which consists of 3 community cards.
        
        Returns:
            list: A list of 3 tuples representing the community cards dealt during the flop.
        """
        return [self.cards.pop() for _ in range(3)]

    def deal_turn(self):
        """
        Deals the 'turn', which consists of 1 additional community card.
        
        Returns:
            tuple: A tuple representing the community card dealt during the turn.
        """
        return self.cards.pop()

    def deal_river(self):
        """
        Deals the 'river', which consists of 1 final community card.
        
        Returns:
            tuple: A tuple representing the community card dealt during the river.
        """
        return self.cards.pop()

    def reset(self):
        """
        Resets the deck back to a full 52 cards and shuffles it.
        """
        self.cards = [(rank, suit) for rank in range(2, 15) for suit in ['hearts', 'diamonds', 'clubs', 'spades']]
        self.shuffle()
