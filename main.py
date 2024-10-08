from game import PokerGame
from gui import run_gui  # Import the GUI launcher function

def main():
    """
    Main function to initialize the poker game and launch the GUI.
    """
    num_players = 4  # Number of AI players in the game

    # Initialize the poker game with the specified number of players
    game = PokerGame(num_players=num_players)

    # Launch the GUI and pass the game object
    run_gui(game)

if __name__ == "__main__":
    main()
