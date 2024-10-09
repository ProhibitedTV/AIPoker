import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton, QTextEdit
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QTimer

class PokerGUI(QMainWindow):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.card_image_path = os.path.join("images", "cards")  # Directory for card images
        self.init_ui()
        self.current_stage = 0  # Track the game stage

    def init_ui(self):
        self.setWindowTitle('AI Poker Game')
        self.showFullScreen()  # Set the application to fullscreen

        # Set casino-style background color and font
        self.setStyleSheet("background-color: green; font-family: Arial; font-size: 18px; color: white;")
        
        # Main widget and layout
        self.central_widget = QWidget()
        self.main_layout = QVBoxLayout()

        # Header layout for pot, dealer, and win percentages
        self.header_layout = QHBoxLayout()

        # Pot label
        self.pot_label = QLabel(f"Pot: {self.game.pot}")
        self.pot_label.setFont(QFont('Arial', 14))
        self.pot_label.setAlignment(Qt.AlignCenter)
        self.pot_label.setStyleSheet("background-color: black; color: white; padding: 10px; border-radius: 10px;")
        self.header_layout.addWidget(self.pot_label)

        # Dealer label
        self.dealer_label = QLabel("Dealer: AI Player 1")
        self.dealer_label.setFont(QFont('Arial', 14))
        self.dealer_label.setAlignment(Qt.AlignCenter)
        self.dealer_label.setStyleSheet("background-color: blue; color: white; padding: 10px; border-radius: 10px;")
        self.header_layout.addWidget(self.dealer_label)

        # Add player win percentages
        self.win_percentage_labels = []
        for i in range(4):
            win_percentage_label = QLabel(f"AI Player {i + 1} Win %: 0%")
            win_percentage_label.setFont(QFont('Arial', 14))
            win_percentage_label.setAlignment(Qt.AlignCenter)
            win_percentage_label.setStyleSheet("background-color: darkblue; color: white; padding: 5px; border-radius: 5px;")
            self.header_layout.addWidget(win_percentage_label)
            self.win_percentage_labels.append(win_percentage_label)

        # Add the header layout to the main layout
        self.main_layout.addLayout(self.header_layout)

        # Create the poker table (players and community cards)
        self.table_layout = QVBoxLayout()

        # Add player labels and card areas
        self.players_layout = QHBoxLayout()
        self.player_labels = []
        self.player_cards_layouts = []  # Layouts for player cards
        self.player_action_labels = []  # New addition to show player actions (fold, call, etc.)
        for i in range(4):
            player_widget = QVBoxLayout()

            player_label = QLabel(f"AI Player {i + 1}")
            player_label.setFont(QFont('Arial', 16))
            player_label.setAlignment(Qt.AlignCenter)
            player_label.setStyleSheet("background-color: darkred; border-radius: 10px; padding: 10px;")
            player_widget.addWidget(player_label)
            
            # Layout for card images
            card_layout = QHBoxLayout()
            card_layout.setAlignment(Qt.AlignCenter)
            player_widget.addLayout(card_layout)

            player_action = QLabel(f"Action: None")
            player_action.setFont(QFont('Arial', 14))
            player_action.setAlignment(Qt.AlignCenter)
            player_widget.addWidget(player_action)

            self.player_labels.append(player_label)
            self.player_cards_layouts.append(card_layout)
            self.player_action_labels.append(player_action)
            
            self.players_layout.addLayout(player_widget)

        self.table_layout.addLayout(self.players_layout)
        
        # Community cards in the middle
        self.community_cards_layout = QHBoxLayout()  # Layout to hold community card images
        self.community_cards_label = QLabel("Community Cards: ")
        self.community_cards_label.setFont(QFont('Arial', 18))
        self.community_cards_label.setAlignment(Qt.AlignCenter)
        self.community_cards_label.setStyleSheet("background-color: black; color: white; padding: 10px; border-radius: 10px;")
        self.table_layout.addWidget(self.community_cards_label)
        self.table_layout.addLayout(self.community_cards_layout)

        self.main_layout.addLayout(self.table_layout)

        # Game log (for showing decisions and outcomes)
        self.game_log = QTextEdit()
        self.game_log.setFont(QFont('Arial', 12))
        self.game_log.setReadOnly(True)
        self.game_log.setFixedHeight(150)  # Smaller log at the bottom
        self.main_layout.addWidget(self.game_log)
        
        # Button to start the game
        self.start_button = QPushButton("Start Game")
        self.start_button.setFont(QFont('Arial', 16))
        self.start_button.setStyleSheet("background-color: gold; color: black; padding: 10px;")
        self.start_button.clicked.connect(self.start_game)
        self.main_layout.addWidget(self.start_button)

        self.central_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.central_widget)

    def start_game(self):
        self.start_button.hide()  # Hide the start button after the game starts
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance_game_stage)
        self.timer.start(5000)  # 5 seconds for each stage

    def advance_game_stage(self):
        if self.current_stage == 0:
            self.game.play_pre_flop()
        elif self.current_stage == 1:
            self.game.play_flop()
        elif self.current_stage == 2:
            self.game.play_turn()
        elif self.current_stage == 3:
            self.game.play_river()
        elif self.current_stage == 4:
            self.show_winner()
            QTimer.singleShot(5000, self.reset_game_for_next_round)  # Wait 5 seconds, then reset for next round

        self.current_stage += 1
        self.update_visuals()

    def show_winner(self):
        winner, hand_description = self.game.determine_winner()
        if winner:
            winner_text = f"Winner: {winner.name} with a {hand_description}!"
        else:
            winner_text = "No winner this round."
        self.game_log.append(f"\n{winner_text}")
        self.update_win_percentages()

    def reset_game_for_next_round(self):
        """Resets the game for the next round and starts a new one."""
        self.game.log.append("\n--- New Round ---")  # Add to the game log for the new round
        self.current_stage = 0  # Reset the stage tracker
        self.game.deck.reset()  # Reset the deck
        for player in self.game.players:
            player.reset_for_next_round()  # Reset each player for the next round
        self.game.community_cards = []  # Clear the community cards
        self.game.pot = 0  # Reset the pot
        self.update_visuals()  # Update visuals for the reset state
        self.timer.start(5000)  # Restart the round timer

    def update_visuals(self):
        self.update_community_cards(self.game.community_cards)
        self.update_pot(self.game.pot)
        self.update_dealer(self.game.dealer_position)

        # Highlight the current player and update their cards and actions
        for i, player in enumerate(self.game.players):
            if player.is_active:
                self.player_labels[i].setStyleSheet("background-color: yellow; color: black; border-radius: 10px;")
                self.update_player_cards(i, player.hand)
                self.player_action_labels[i].setText(f"Action: {player.current_bet} chips")  # Show current action
            else:
                self.player_labels[i].setStyleSheet("background-color: darkred; color: white; border-radius: 10px;")
                self.clear_player_cards(i)
                self.player_action_labels[i].setText(f"Action: Folded")

        # Update game log and auto-scroll to the latest updates
        self.update_game_log()

    def update_community_cards(self, community_cards):
        # Clear previous community cards
        for i in reversed(range(self.community_cards_layout.count())):
            self.community_cards_layout.itemAt(i).widget().deleteLater()

        # Display community card images
        for card in community_cards:
            card_image = self.get_card_image(card)
            card_label = QLabel()
            card_label.setPixmap(card_image)
            self.community_cards_layout.addWidget(card_label)

    def update_player_cards(self, player_index, hand):
        # Clear previous cards
        for i in reversed(range(self.player_cards_layouts[player_index].count())):
            self.player_cards_layouts[player_index].itemAt(i).widget().deleteLater()

        # Display player card images
        for card in hand:
            card_image = self.get_card_image(card)
            card_label = QLabel()
            card_label.setPixmap(card_image)
            self.player_cards_layouts[player_index].addWidget(card_label)

    def clear_player_cards(self, player_index):
        # Clear card images for folded players
        for i in reversed(range(self.player_cards_layouts[player_index].count())):
            self.player_cards_layouts[player_index].itemAt(i).widget().deleteLater()

    def get_card_image(self, card):
        rank, suit = card
        suit = suit.lower()

        # Map ranks to face cards
        rank_map = {
            11: 'jack',
            12: 'queen',
            13: 'king',
            14: 'ace'
        }
        rank_str = rank_map.get(rank, str(rank))
        card_filename = f"{rank_str}_of_{suit}.png"
        card_path = os.path.join(self.card_image_path, card_filename)

        # Load and scale the card image
        pixmap = QPixmap(card_path)
        scaled_pixmap = pixmap.scaled(80, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 80x120 size limit

        return scaled_pixmap

    def update_pot(self, pot):
        self.pot_label.setText(f"Pot: {pot}")

    def update_dealer(self, dealer_position):
        self.dealer_label.setText(f"Dealer: AI Player {dealer_position + 1}")

    def update_game_log(self):
        # This function updates the log with game details
        log_text = "\n".join(self.game.get_log())  # Fetch log from game
        self.game_log.setText(log_text)
        
        # Automatically scroll to the bottom of the log
        self.game_log.moveCursor(self.game_log.textCursor().End)

    def update_win_percentages(self):
        """
        Updates the win percentage labels for each player.
        """
        for i, player in enumerate(self.game.players):
            win_percentage = player.get_win_percentage()
            self.win_percentage_labels[i].setText(f"AI Player {i + 1} Win %: {win_percentage:.2f}%")

def run_gui(game):
    app = QApplication(sys.argv)
    gui = PokerGUI(game)
    gui.show()
    sys.exit(app.exec_())
