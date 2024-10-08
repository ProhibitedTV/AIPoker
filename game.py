from player import AIPlayer
from deck import Deck
from hand_evaluator import evaluate_hand

class PokerGame:
    def __init__(self, num_players=4, starting_chips=1000):
        """
        Initializes the poker game with a specified number of AI players and starting chips.
        
        Args:
            num_players (int): The number of AI players in the game.
            starting_chips (int): The starting chip count for each player.
        """
        self.num_players = num_players
        self.players = [AIPlayer(f"AI Player {i+1}", chips=starting_chips) for i in range(num_players)]
        self.deck = Deck()
        self.community_cards = []
        self.pot = 0
        self.log = []  # Initialize a log to store game events
        self.dealer_position = 0  # Starting position for the dealer

    def play_pre_flop(self):
        """
        Pre-flop stage where players are dealt their hole cards.
        """
        self.log.append("\n--- New Round ---")
        self.deck.reset()
        self.community_cards = []
        self.pot = 0

        # Rotate the dealer position
        self.dealer_position = (self.dealer_position + 1) % self.num_players

        # Deal hands to all players
        for player in self.players:
            player.deal_hand(self.deck.deal_hand())
            hand_text = ", ".join([f"{card[0]} of {card[1]}" for card in player.hand])
            self.log.append(f"{player.name} is dealt {hand_text}")

        # Pre-flop betting round
        self.betting_round("Pre-Flop")

        # Check if there are still active players left
        if not self.any_active_players():
            return  # If all players fold, end the round early

    def play_flop(self):
        """
        Deals the Flop (3 community cards) and shows them to the players, followed by the Flop betting round.
        """
        self.community_cards = self.deck.deal_flop()
        self.log.append(f"Flop: {self.community_cards}")
        self.betting_round("Flop")

        if not self.any_active_players():
            return  # End round if no active players

    def play_turn(self):
        """
        Deals the Turn (1 additional community card), followed by the Turn betting round.
        """
        turn = self.deck.deal_turn()
        self.community_cards.append(turn)
        self.log.append(f"Turn: {self.community_cards}")
        self.betting_round("Turn")

        if not self.any_active_players():
            return  # End round if no active players

    def play_river(self):
        """
        Deals the River (1 final community card), followed by the River betting round.
        """
        river = self.deck.deal_river()
        self.community_cards.append(river)
        self.log.append(f"River: {self.community_cards}")
        self.betting_round("River")

        if not self.any_active_players():
            return  # End round if no active players

    def betting_round(self, round_name):
        """
        Simulates a betting round where each AI player makes a decision (fold, check, bet, raise).
        
        Args:
            round_name (str): The name of the betting round (e.g., "Pre-Flop", "Flop", "Turn", "River").
        """
        self.log.append(f"\n--- {round_name} Betting Round ---")
        current_bet = 0
        for player in self.players:
            if player.is_active:
                decision = player.make_decision(self.community_cards, current_bet)
                if player.current_bet > current_bet:
                    current_bet = player.current_bet
                self.pot += player.current_bet  # Add to the pot
                self.log.append(f"{player.name} {decision}s {player.current_bet} chips.")
    
    def determine_winner(self):
        """
        Evaluates all active players' hands and determines the winner of the round.
        
        Returns:
            best_player (AIPlayer): The player who won the round.
            winning_hand (str): A description of the winning hand.
        """
        active_players = [player for player in self.players if player.is_active]

        if len(active_players) == 0:
            self.log.append("No active players. The round ends with no winner.")
            return None, "No winner"

        best_hand_value = None
        best_player = None
        winning_hand = ""

        for player in active_players:
            hand_value, best_ranks = evaluate_hand(player.hand, self.community_cards)
            hand_description = self.describe_hand_value(hand_value)
            self.log.append(f"{player.name}'s hand value: {hand_value} with best ranks: {best_ranks} ({hand_description})")

            if best_hand_value is None or hand_value > best_hand_value[0]:
                best_hand_value = (hand_value, best_ranks)
                best_player = player
                winning_hand = hand_description
            elif hand_value == best_hand_value[0] and best_ranks > best_hand_value[1]:
                best_hand_value = (hand_value, best_ranks)
                best_player = player
                winning_hand = hand_description

        if best_player:
            self.log.append(f"\nWinner: {best_player.name} with hand {best_player.hand} and community cards {self.community_cards}")
        else:
            self.log.append("No winner in this round.")

        return best_player, winning_hand

    def describe_hand_value(self, hand_value):
        """
        Converts a hand value to a human-readable description of the hand type.
        
        Args:
            hand_value (int): The numerical value of the hand.
        
        Returns:
            str: A description of the hand (e.g., "Flush", "Two Pair").
        """
        if hand_value >= 8:
            return "Straight Flush"
        elif hand_value == 7:
            return "Four of a Kind"
        elif hand_value == 6:
            return "Full House"
        elif hand_value == 5:
            return "Flush"
        elif hand_value == 4:
            return "Straight"
        elif hand_value == 3:
            return "Three of a Kind"
        elif hand_value == 2:
            return "Two Pair"
        elif hand_value == 1:
            return "One Pair"
        else:
            return "High Card"

    def any_active_players(self):
        """
        Checks if there are any active players left in the round.

        Returns:
            bool: True if there are active players, False otherwise.
        """
        return any(player.is_active for player in self.players)

    def get_log(self):
        """
        Returns the game log as a list of strings.
        
        Returns:
            list: The log of game events.
        """
        return self.log
