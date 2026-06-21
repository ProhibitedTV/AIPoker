"""Render a deterministic desktop-table screenshot for UI review."""

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from game import PokerGame
from gui import PokerGUI
from settings import AppSettings


def main():
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "ui-preview.png")
    app = QApplication([])
    game = PokerGame(4, decision_provider=lambda *_: "check")
    game.play_pre_flop()
    game.play_flop()
    settings = AppSettings(fullscreen=False, overlay_enabled=False)
    window = PokerGUI(game, settings)
    window.resize(1600, 900)
    window.show()
    app.processEvents()
    window.update_visuals()
    app.processEvents()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output)):
        raise RuntimeError(f"Could not save UI preview to {output}")
    window.close()


if __name__ == "__main__":
    main()
