"""PyQt spectator interface with configurable pacing and card transitions."""

import os
import sys

from PyQt5.QtCore import (
    QObject,
    QPoint,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRunnable,
    QThreadPool,
    QTimer,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class AnimatedCardLabel(QLabel):
    """Card label whose flip and slide are driven by Qt's event loop."""

    def __init__(self, front, duration, parent=None):
        super().__init__(parent)
        self.front = front
        self.back = QPixmap(80, 120)
        self.back.fill(QColor("#183a64"))
        self.duration = duration
        self._flip_progress = 0.0
        self.setFixedSize(80, 120)
        self.setAlignment(Qt.AlignCenter)
        self._animation = None
        self.set_flip_progress(0.0)

    def get_flip_progress(self):
        return self._flip_progress

    def set_flip_progress(self, value):
        self._flip_progress = value
        source = self.back if value < 0.5 else self.front
        width = max(1, int(80 * abs(1 - 2 * value)))
        self.setPixmap(source.scaled(width, 120, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

    flipProgress = pyqtProperty(float, get_flip_progress, set_flip_progress)

    def animate_in(self):
        flip = QPropertyAnimation(self, b"flipProgress")
        flip.setDuration(self.duration)
        flip.setStartValue(0.0)
        flip.setEndValue(1.0)
        slide = QPropertyAnimation(self, b"pos")
        slide.setDuration(self.duration)
        slide.setStartValue(self.pos() - QPoint(60, 80))
        slide.setEndValue(self.pos())
        self._animation = QParallelAnimationGroup(self)
        self._animation.addAnimation(flip)
        self._animation.addAnimation(slide)
        self._animation.start()


class StageSignals(QObject):
    finished = pyqtSignal()
    failed = pyqtSignal(str)


class StageWorker(QRunnable):
    """Run model-backed game work without blocking Qt's event loop."""

    def __init__(self, action):
        super().__init__()
        self.action = action
        self.signals = StageSignals()

    def run(self):
        try:
            self.action()
        except Exception as error:
            self.signals.failed.emit(f"{type(error).__name__}: {error}")
        else:
            self.signals.finished.emit()


class ChipHistoryChart(QWidget):
    """Small season chart drawn directly from persisted chip snapshots."""

    COLORS = ("#e6b94a", "#58b9ff", "#ff6f91", "#73dc8c", "#c792ea", "#ff9f43")

    def __init__(self, metrics_store, parent=None):
        super().__init__(parent)
        self.metrics_store = metrics_store
        self.setMinimumWidth(260)
        self.setFixedHeight(165)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#10251b"))
        painter.setPen(QColor("white"))
        painter.drawText(10, 20, "Chip distribution history")
        if not self.metrics_store:
            return
        history = self.metrics_store.snapshot().get("chip_history", [])[-200:]
        if len(history) < 2:
            painter.setPen(QColor("#aaaaaa"))
            painter.drawText(10, 45, "Complete two hands to chart the season")
            return
        names = list(history[-1]["players"])
        values = [entry["players"].get(name, 0) for entry in history for name in names]
        maximum = max(1, max(values))
        left, top, right, bottom = 10, 30, self.width() - 10, self.height() - 15
        for color_index, name in enumerate(names):
            painter.setPen(QPen(QColor(self.COLORS[color_index % len(self.COLORS)]), 2))
            points = []
            for index, entry in enumerate(history):
                x = left + (right - left) * index / (len(history) - 1)
                y = bottom - (bottom - top) * entry["players"].get(name, 0) / maximum
                points.append(QPoint(int(x), int(y)))
            for start, end in zip(points, points[1:]):
                painter.drawLine(start, end)


class PokerGUI(QMainWindow):
    def __init__(self, game, settings):
        super().__init__()
        self.game = game
        self.settings = settings
        self.card_image_path = os.path.join(os.path.dirname(__file__), "images", "cards")
        self.current_stage = 0
        self.running = False
        self.paused = settings.start_paused
        self._remaining_delay = settings.stage_delay_ms
        self._stage_before_pause = "Waiting"
        self._has_started_once = False
        self._shown_player_hands = [None] * game.num_players
        self._shown_community = None
        self._stage_in_progress = False
        self._stage_worker = None
        self.thread_pool = QThreadPool.globalInstance()
        self.init_ui()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.advance_game_stage)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(250)
        self.refresh_timer.timeout.connect(self.update_visuals)

    def init_ui(self):
        self.setWindowTitle("AI Poker Game")
        if self.settings.fullscreen:
            self.showFullScreen()
        self.setStyleSheet("background-color: #08712f; font-family: Arial; font-size: 16px; color: white;")
        central = QWidget()
        main = QVBoxLayout(central)

        header = QHBoxLayout()
        self.pot_label = self._header_label("Pot: 0", "black")
        self.dealer_label = self._header_label("Dealer: -", "#194ca0")
        header.addWidget(self.pot_label)
        header.addWidget(self.dealer_label)
        self.win_percentage_labels = []
        for player in self.game.players:
            label = self._header_label(f"{player.name} Win %: 0%", "#142b75")
            header.addWidget(label)
            self.win_percentage_labels.append(label)
        main.addLayout(header)

        self.players_layout = QHBoxLayout()
        self.player_labels = []
        self.player_cards_layouts = []
        self.player_action_labels = []
        for player in self.game.players:
            column = QVBoxLayout()
            name = QLabel(player.name)
            name.setFont(QFont("Arial", 14))
            name.setAlignment(Qt.AlignCenter)
            column.addWidget(name)
            cards = QHBoxLayout()
            cards.setAlignment(Qt.AlignCenter)
            column.addLayout(cards)
            action = QLabel("Waiting")
            action.setAlignment(Qt.AlignCenter)
            column.addWidget(action)
            self.player_labels.append(name)
            self.player_cards_layouts.append(cards)
            self.player_action_labels.append(action)
            self.players_layout.addLayout(column)
        main.addLayout(self.players_layout)

        self.community_cards_label = QLabel("Community Cards")
        self.community_cards_label.setFont(QFont("Arial", 16))
        self.community_cards_label.setAlignment(Qt.AlignCenter)
        self.community_cards_label.setStyleSheet("background-color: #000a; padding: 8px; border-radius: 5px;")
        main.addWidget(self.community_cards_label)
        self.community_cards_layout = QHBoxLayout()
        self.community_cards_layout.setAlignment(Qt.AlignCenter)
        main.addLayout(self.community_cards_layout)

        lower = QHBoxLayout()
        self.game_log = QTextEdit()
        self.game_log.setReadOnly(True)
        self.game_log.setFixedHeight(165)
        lower.addWidget(self.game_log, 2)
        self.leaderboard = QTableWidget(self.game.num_players, 6)
        self.leaderboard.setHorizontalHeaderLabels(["Player", "Hands", "Wins", "Ties", "Win %", "Net"])
        self.leaderboard.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.leaderboard.verticalHeader().hide()
        self.leaderboard.setFixedHeight(165)
        lower.addWidget(self.leaderboard, 2)
        self.chip_history_chart = ChipHistoryChart(self.game.metrics_store)
        lower.addWidget(self.chip_history_chart, 2)
        main.addLayout(lower)

        controls = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_game)
        self.pause_button = QPushButton("Resume" if self.paused else "Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        self.continuous_checkbox = QCheckBox("Continuous play")
        self.continuous_checkbox.setChecked(self.settings.continuous_play)
        self.reset_stats_button = QPushButton("Reset season stats")
        self.reset_stats_button.clicked.connect(self.reset_statistics)
        for widget in (self.start_button, self.pause_button, self.continuous_checkbox, self.reset_stats_button):
            controls.addWidget(widget)
        main.addLayout(controls)
        self.setCentralWidget(central)

        QShortcut(QKeySequence("Space"), self, activated=self.toggle_pause)
        QShortcut(QKeySequence("R"), self, activated=self.resume_game)
        self.update_visuals()

    @staticmethod
    def _header_label(text, color):
        label = QLabel(text)
        label.setFont(QFont("Arial", 10))
        label.setFixedHeight(30)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"background-color: {color}; padding: 2px; border-radius: 5px;")
        return label

    def start_game(self):
        if self.running:
            return
        self.running = True
        self.paused = self.settings.start_paused and not self._has_started_once
        self._has_started_once = True
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("Resume" if self.paused else "Pause")
        if not self.paused:
            self.timer.start(0)

    def toggle_pause(self):
        if not self.running:
            return
        if self.paused:
            self.resume_game()
        else:
            self.paused = True
            self._remaining_delay = max(0, self.timer.remainingTime())
            self.timer.stop()
            self.pause_button.setText("Resume")
            self._stage_before_pause = self.game.stage
            self.game.stage = "Paused"
            self.update_visuals()

    def resume_game(self):
        if not self.running or not self.paused:
            return
        self.paused = False
        self.pause_button.setText("Pause")
        self.game.stage = self._stage_before_pause
        if not self._stage_in_progress:
            self.timer.start(self._remaining_delay)

    def advance_game_stage(self):
        if self.paused or self._stage_in_progress:
            return
        actions = (
            self.game.play_pre_flop,
            self.game.play_flop,
            self.game.play_turn,
            self.game.play_river,
            self.game.determine_winner,
        )
        showdown = self.current_stage == 4
        self._stage_in_progress = True
        self._stage_worker = StageWorker(actions[self.current_stage])
        self._stage_worker.signals.finished.connect(lambda: self._stage_finished(showdown))
        self._stage_worker.signals.failed.connect(self._stage_failed)
        self.refresh_timer.start()
        self.thread_pool.start(self._stage_worker)

    def _stage_finished(self, showdown):
        self.refresh_timer.stop()
        self._stage_in_progress = False
        self._stage_worker = None
        self.update_visuals()

        if showdown:
            if self.continuous_checkbox.isChecked():
                self.current_stage = 0
                delay = self.settings.between_hands_delay_ms
            else:
                self.running = False
                self.start_button.setText("Start next hand")
                self.start_button.setEnabled(True)
                self.pause_button.setEnabled(False)
                self.current_stage = 0
                return
        else:
            self.current_stage += 1
            if sum(player.is_active for player in self.game.players) <= 1:
                self.current_stage = 4
            delay = self.settings.stage_delay_ms

        self._remaining_delay = delay
        if not self.paused:
            self.timer.start(delay)

    def _stage_failed(self, error):
        self.refresh_timer.stop()
        self._stage_in_progress = False
        self._stage_worker = None
        self.game.recover_from_error(error)
        self.current_stage = 0
        self._remaining_delay = self.settings.between_hands_delay_ms
        self.update_visuals()
        if not self.paused:
            self.timer.start(self._remaining_delay)

    def reset_statistics(self):
        answer = QMessageBox.question(
            self,
            "Reset season statistics",
            "Reset the persistent leaderboard and streak history?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.game.reset_metrics()
            self.update_win_percentages()
            self.update_leaderboard()

    def update_visuals(self):
        self.update_community_cards(self.game.community_cards)
        self.pot_label.setText(f"Pot: {self.game.pot}")
        dealer = "-" if self.game.dealer_position < 0 else self.game.players[self.game.dealer_position].name
        self.dealer_label.setText(f"Dealer: {dealer}")
        for index, player in enumerate(self.game.players):
            color = "#d8b51f; color: black" if index == self.game.next_to_act else "#7b1818; color: white"
            if not player.is_active:
                color = "#3d3d3d; color: #aaa"
            self.player_labels[index].setStyleSheet(f"background-color: {color}; border-radius: 10px; padding: 6px;")
            self.player_labels[index].setText(f"{player.name} · {player.chips} chips")
            self.update_player_cards(index, player.hand if player.is_active else [])
            self.player_action_labels[index].setText(player.last_action)
        self.update_game_log()
        self.update_win_percentages()
        self.update_leaderboard()

    def update_community_cards(self, cards):
        signature = tuple(cards)
        if signature == self._shown_community:
            return
        self._clear_layout(self.community_cards_layout)
        for card in cards:
            self._add_animated_card(self.community_cards_layout, card)
        self._shown_community = signature

    def update_player_cards(self, index, hand):
        signature = tuple(hand)
        if signature == self._shown_player_hands[index]:
            return
        layout = self.player_cards_layouts[index]
        self._clear_layout(layout)
        for card in hand:
            self._add_animated_card(layout, card)
        self._shown_player_hands[index] = signature

    def _add_animated_card(self, layout, card):
        label = AnimatedCardLabel(self.get_card_image(card), self.settings.animation_duration_ms)
        layout.addWidget(label)
        QTimer.singleShot(0, label.animate_in)

    @staticmethod
    def _clear_layout(layout):
        for index in reversed(range(layout.count())):
            widget = layout.itemAt(index).widget()
            if widget:
                widget.deleteLater()

    def get_card_image(self, card):
        rank, suit = card
        rank_name = {11: "jack", 12: "queen", 13: "king", 14: "ace"}.get(rank, str(rank))
        path = os.path.join(self.card_image_path, f"{rank_name}_of_{suit.lower()}.png")
        return QPixmap(path).scaled(80, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def update_game_log(self):
        self.game_log.setPlainText("\n".join(self.game.get_log()))
        self.game_log.moveCursor(self.game_log.textCursor().End)

    def update_win_percentages(self):
        for index, player in enumerate(self.game.players):
            self.win_percentage_labels[index].setText(
                f"{player.name} Win %: {player.get_win_percentage():.2f}%"
            )

    def update_leaderboard(self):
        data = self.game.metrics_store.snapshot() if self.game.metrics_store else {"players": {}}
        for row, player in enumerate(self.game.players):
            stats = data["players"].get(player.name, {})
            values = [
                player.name,
                stats.get("hands_played", player.total_rounds),
                stats.get("hands_won", player.wins),
                stats.get("hands_tied", player.ties),
                f"{stats.get('win_rate', player.get_win_percentage()):.1f}%",
                stats.get("net_chips", 0),
            ]
            for column, value in enumerate(values):
                self.leaderboard.setItem(row, column, QTableWidgetItem(str(value)))
        self.chip_history_chart.update()


def run_gui(game, settings):
    app = QApplication(sys.argv)
    gui = PokerGUI(game, settings)
    gui.show()
    return app.exec_()
