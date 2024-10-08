import random
from hand_evaluator import evaluate_hand
from ollama_integration import get_ai_decision

class AIPlayer:
    def __init__(self, name, chips=1000):
        """
        Initializes an AI player with a given name and a starting number of chips.
        
        Args:
            name (str): The name of the AI player.
            chips (int): The starting amount of chips for the player (default is 1000).
        """
        self.name = name
        self.chips = chips
        self.hand = []
        self.current_bet = 0
        self.is_active = True  # Whether the player is still in the round

    def deal_hand(self, hand):
        """
        Assigns a hand of cards to the AI player.
        
        Args:
            hand (list): A list of tuples representing the player's hand (e.g., [(10, 'hearts'), (9, 'diamonds')]).
        """
        self.hand = hand

    def make_decision(self, community_cards, current_bet):
        """
        Makes a decision based on the player's hand, community cards, and the current bet on the table.
        
        Args:
            community_cards (list): A list of tuples representing the community cards on the table.
            current_bet (int): The current bet that the player needs to match.

        Returns:
            str: The AI's decision (fold, check, bet, raise).
        """
        if not self.is_active:
            return "fold"  # Inactive players can't make decisions

        # Get decision from the AI model via the Ollama API
        decision = get_ai_decision(self.hand, community_cards)

        # Handle decisions and update the player's state accordingly
        if decision == "fold":
            self.is_active = False
            print(f"{self.name} folds.")
        elif decision == "check":
            print(f"{self.name} checks.")
        elif decision == "bet":
            bet_amount = self.calculate_bet_amount(current_bet)
            self.chips -= bet_amount
            self.current_bet = bet_amount
            print(f"{self.name} bets {bet_amount}.")
        elif decision == "raise":
            raise_amount = self.calculate_raise_amount(current_bet)
            self.chips -= raise_amount
            self.current_bet = raise_amount
            print(f"{self.name} raises by {raise_amount}.")
        else:
            # If the AI returns an invalid decision, default to folding
            print(f"{self.name} folds by default (invalid response).")
            self.is_active = False

        return decision

    def calculate_bet_amount(self, current_bet):
        """
        Calculate a more dynamic bet amount based on the current bet and AI's chips.
        
        Args:
            current_bet (int): The current bet that the player needs to match.
        
        Returns:
            int: The amount the player decides to bet.
        """
        bet_min = max(current_bet, 50)
        bet_max = min(self.chips, current_bet + 200)
        
        if bet_max < bet_min:
            return self.chips  # All-in if chips are too low

        return random.randint(bet_min, bet_max)

    def calculate_raise_amount(self, current_bet):
        """
        Calculate a more dynamic raise amount based on the current bet and AI's chips.
        
        Args:
            current_bet (int): The current bet that the player needs to match.
        
        Returns:
            int: The amount the player decides to raise.
        """
        if self.chips <= current_bet * 2:
            return self.chips  # Go all-in if not enough chips to raise properly
        raise_min = current_bet * 2
        raise_max = min(self.chips, current_bet * 3 + 100)
        
        if raise_max < raise_min:
            return self.chips  # All-in

        return random.randint(raise_min, raise_max)

    def reset_for_next_round(self):
        """
        Resets the player's state for the next round.
        """
        self.hand = []
        self.current_bet = 0
        self.is_active = True
