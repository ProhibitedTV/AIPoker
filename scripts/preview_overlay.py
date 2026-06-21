"""Serve a deterministic table state for overlay design and OBS setup."""

from threading import Event

from game import PokerGame
from overlay_server import OverlayServer


def main():
    game = PokerGame(4, decision_provider=lambda *_: "check")
    game.play_pre_flop()
    game.play_flop()
    server = OverlayServer(game, host="0.0.0.0", port=8765).start()
    print(f"Overlay preview: {server.url}")
    try:
        Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()
