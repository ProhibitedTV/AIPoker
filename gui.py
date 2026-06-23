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
from PyQt5.QtGui import QColor, QKeySequence, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSlider,
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
    PACE_PRESETS = (
        ("Cinematic", 1800, 7500, 10000),
        ("Broadcast", 1250, 4500, 6500),
        ("Brisk", 800, 2800, 4000),
    )

    def __init__(self, game, settings, audio_service=None):
        super().__init__()
        self.game = game
        self.settings = settings
        self.audio_service = audio_service
        self.card_image_path = os.path.join(os.path.dirname(__file__), "images", "cards")
        self.current_stage = 0
        self.running = False
        self.paused = settings.start_paused
        self._remaining_delay = settings.stage_delay_ms
        self._stage_before_pause = "Waiting"
        self._has_started_once = False
        self._shown_player_hands = [None] * game.num_players
        self._shown_wagers = [0] * game.num_players
        self._wager_animations = {}
        self._shown_community = None
        self._stage_in_progress = False
        self._stage_worker = None
        self._last_log_snapshot = ()
        self._leaderboard_signature = None
        self.thread_pool = QThreadPool.globalInstance()
        self.init_ui()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.advance_game_stage)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(250)
        self.refresh_timer.timeout.connect(self.update_visuals)

    def init_ui(self):
        self.setWindowTitle("AI Poker // Live Table")
        self.setMinimumSize(1280, 800)
        self.setStyleSheet(
            """
            QMainWindow, QWidget#root { background: #061812; color: #f4f1e8; font-family: "Segoe UI", Arial; }
            QFrame#topBar, QFrame#boardPanel, QFrame#dataPanel, QFrame#controlBar {
                background: #10271f; border: 1px solid #254b3d; border-radius: 12px;
            }
            QFrame#playerPanel { background: #0c211a; border: 1px solid #285140; border-radius: 12px; }
            QLabel#brand { color: #f0c75e; font-size: 24px; font-weight: 800; letter-spacing: 2px; }
            QLabel#eyebrow { color: #88aa9e; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
            QLabel#metricValue { color: #ffffff; font-size: 18px; font-weight: 700; }
            QLabel#metricCaption { color: #88aa9e; font-size: 10px; font-weight: 700; }
            QLabel#playerName { color: #ffffff; font-size: 16px; font-weight: 700; }
            QLabel#playerStats { color: #9ab5ab; font-size: 11px; }
            QLabel#actionBadge { background: #17382d; color: #d9e7e1; border-radius: 7px; padding: 6px; font-weight: 700; }
            QLabel#commentaryBanner { background: #081c15; color: #f5d77e; border: 1px solid #315747;
                border-radius: 9px; padding: 9px; font-size: 14px; font-weight: 600; }
            QLabel#winnerSpotlight { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #4a3510, stop:0.5 #171208, stop:1 #4a3510);
                color: #ffe38a; border: 1px solid #e2bd56; border-radius: 10px; padding: 9px;
                font-size: 16px; font-weight: 900; letter-spacing: 1px; }
            QLabel#sectionTitle { color: #91b2a5; font-size: 11px; font-weight: 800; letter-spacing: 1px; }
            QPushButton { background: #1c4436; color: #ffffff; border: 1px solid #376a57; border-radius: 8px;
                padding: 8px 14px; font-weight: 700; }
            QPushButton:hover { background: #285b49; }
            QPushButton:disabled { color: #6f8b80; background: #132b23; }
            QPushButton#primaryButton { background: #d8ad43; color: #132018; border-color: #f0ce75; }
            QPushButton#dangerButton { background: #3a2424; color: #e8b5b5; border-color: #65403f; }
            QComboBox { background: #0a1d17; color: #ffffff; border: 1px solid #376a57; border-radius: 7px; padding: 6px 10px; }
            QCheckBox { color: #c7d8d1; spacing: 7px; }
            QTextEdit, QTableWidget { background: #081b15; color: #dbe7e2; border: 0; gridline-color: #254b3d; }
            QHeaderView::section { background: #17372c; color: #b9cec5; border: 0; padding: 6px; font-weight: 700; }
            """
        )
        central = QWidget()
        central.setObjectName("root")
        main = QVBoxLayout(central)
        main.setContentsMargins(16, 16, 16, 14)
        main.setSpacing(12)

        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        header = QHBoxLayout(top_bar)
        header.setContentsMargins(16, 11, 16, 11)
        brand_column = QVBoxLayout()
        brand = QLabel("AI POKER")
        brand.setObjectName("brand")
        subtitle = QLabel("LOCAL MODELS  /  LIVE TABLE")
        subtitle.setObjectName("eyebrow")
        brand_column.addWidget(brand)
        brand_column.addWidget(subtitle)
        header.addLayout(brand_column, 2)
        self.run_status_label = self._status_badge("STANDBY")
        self.hand_status_label = self._metric_label("HAND", "0 · Waiting")
        self.pot_label = self._metric_label("POT", "0")
        self.blinds_label = self._metric_label("BLINDS", "0 / 0")
        self.dealer_label = self._metric_label("DEALER", "-")
        self.mode_label = self._metric_label("FORMAT", self.game.mode.upper())
        header.addWidget(self.run_status_label)
        for widget in (self.hand_status_label, self.pot_label, self.blinds_label, self.dealer_label, self.mode_label):
            header.addWidget(widget, 1)
        main.addWidget(top_bar)

        self.players_layout = QGridLayout()
        self.players_layout.setSpacing(10)
        self.player_frames = []
        self.player_labels = []
        self.player_stats_labels = []
        self.player_dealer_badges = []
        self.player_cards_layouts = []
        self.player_wager_labels = []
        self.player_wager_effects = []
        self.player_action_labels = []
        for player in self.game.players:
            frame = QFrame()
            frame.setObjectName("playerPanel")
            column = QVBoxLayout(frame)
            column.setContentsMargins(10, 10, 10, 10)
            column.setSpacing(6)
            name_row = QHBoxLayout()
            name = QLabel(player.name)
            name.setObjectName("playerName")
            dealer_badge = QLabel("D")
            dealer_badge.setAlignment(Qt.AlignCenter)
            dealer_badge.setFixedSize(22, 22)
            dealer_badge.setStyleSheet("background:#d8ad43;color:#17231c;border-radius:11px;font-weight:800;")
            dealer_badge.hide()
            name_row.addWidget(name)
            name_row.addStretch()
            name_row.addWidget(dealer_badge)
            column.addLayout(name_row)
            stats = QLabel("1,000 chips · 0W 0T")
            stats.setObjectName("playerStats")
            column.addWidget(stats)
            cards = QHBoxLayout()
            cards.setAlignment(Qt.AlignCenter)
            column.addLayout(cards)
            wager = QLabel("● ● ●  0")
            wager.setAlignment(Qt.AlignCenter)
            wager.setStyleSheet(
                f"color:{player.profile.color};background:#071914;border-radius:10px;"
                "padding:3px 8px;font-size:11px;font-weight:800;"
            )
            wager_effect = QGraphicsOpacityEffect(wager)
            wager.setGraphicsEffect(wager_effect)
            wager.hide()
            column.addWidget(wager)
            action = QLabel("Waiting")
            action.setObjectName("actionBadge")
            action.setAlignment(Qt.AlignCenter)
            column.addWidget(action)
            self.player_frames.append(frame)
            self.player_labels.append(name)
            self.player_stats_labels.append(stats)
            self.player_dealer_badges.append(dealer_badge)
            self.player_cards_layouts.append(cards)
            self.player_wager_labels.append(wager)
            self.player_wager_effects.append(wager_effect)
            self.player_action_labels.append(action)
            columns = 3 if self.game.num_players > 4 else self.game.num_players
            frame_index = len(self.player_frames) - 1
            self.players_layout.addWidget(frame, frame_index // columns, frame_index % columns)
        main.addLayout(self.players_layout)

        board = QFrame()
        board.setObjectName("boardPanel")
        board_layout = QVBoxLayout(board)
        board_layout.setContentsMargins(14, 10, 14, 12)
        board_header = QHBoxLayout()
        self.community_cards_label = QLabel("COMMUNITY BOARD")
        self.community_cards_label.setObjectName("sectionTitle")
        self.stage_label = QLabel("WAITING")
        self.stage_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.stage_label.setStyleSheet("color:#f0c75e;font-size:13px;font-weight:800;letter-spacing:1px;")
        board_header.addWidget(self.community_cards_label)
        board_header.addStretch()
        board_header.addWidget(self.stage_label)
        board_layout.addLayout(board_header)
        self.community_cards_layout = QHBoxLayout()
        self.community_cards_layout.setAlignment(Qt.AlignCenter)
        board_layout.addLayout(self.community_cards_layout)
        self.pot_detail_label = QLabel("MAIN POT · Waiting for action")
        self.pot_detail_label.setAlignment(Qt.AlignCenter)
        self.pot_detail_label.setStyleSheet("color:#d7bd72;font-size:11px;font-weight:700;")
        board_layout.addWidget(self.pot_detail_label)
        self.winner_spotlight_label = QLabel("")
        self.winner_spotlight_label.setObjectName("winnerSpotlight")
        self.winner_spotlight_label.setAlignment(Qt.AlignCenter)
        self.winner_spotlight_label.setWordWrap(True)
        self.winner_spotlight_label.hide()
        board_layout.addWidget(self.winner_spotlight_label)
        self.commentary_banner = QLabel("Table ready. Start the broadcast when Ollama is online.")
        self.commentary_banner.setObjectName("commentaryBanner")
        self.commentary_banner.setAlignment(Qt.AlignCenter)
        self.commentary_banner.setWordWrap(True)
        board_layout.addWidget(self.commentary_banner)
        main.addWidget(board, 2)

        lower = QHBoxLayout()
        lower.setSpacing(10)
        feed_panel = self._data_panel("ACTION FEED")
        feed_layout = feed_panel.layout()
        self.game_log = QTextEdit()
        self.game_log.setReadOnly(True)
        self.game_log.setMinimumHeight(170)
        feed_layout.addWidget(self.game_log)
        lower.addWidget(feed_panel, 3)
        season_panel = self._data_panel("SEASON LEADERBOARD")
        season_layout = season_panel.layout()
        self.leaderboard = QTableWidget(self.game.num_players, 6)
        self.leaderboard.setHorizontalHeaderLabels(["Player", "Hands", "Wins", "Ties", "Win %", "Net"])
        self.leaderboard.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.leaderboard.verticalHeader().hide()
        self.leaderboard.setSelectionMode(QTableWidget.NoSelection)
        self.leaderboard.setFocusPolicy(Qt.NoFocus)
        season_layout.addWidget(self.leaderboard)
        lower.addWidget(season_panel, 3)
        chart_panel = self._data_panel("CHIP MOMENTUM")
        chart_layout = chart_panel.layout()
        self.chip_history_chart = ChipHistoryChart(self.game.metrics_store)
        chart_layout.addWidget(self.chip_history_chart)
        lower.addWidget(chart_panel, 2)
        main.addLayout(lower)

        control_bar = QFrame()
        control_bar.setObjectName("controlBar")
        control_stack = QVBoxLayout(control_bar)
        control_stack.setContentsMargins(12, 9, 12, 9)
        control_stack.setSpacing(6)
        controls = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self.start_game)
        self.pause_button = QPushButton("Resume" if self.paused else "Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        pace_label = QLabel("PACE")
        pace_label.setObjectName("eyebrow")
        self.pace_combo = QComboBox()
        for name, action_delay, stage_delay, hand_delay in self.PACE_PRESETS:
            self.pace_combo.addItem(name, (action_delay, stage_delay, hand_delay))
        closest = min(
            range(len(self.PACE_PRESETS)),
            key=lambda index: abs(self.PACE_PRESETS[index][2] - self.settings.stage_delay_ms),
        )
        self.pace_combo.setCurrentIndex(closest)
        self.pace_combo.currentIndexChanged.connect(self.apply_pace_preset)
        self.pace_combo.setToolTip("Change readable action, street, and hand timing without restarting")
        self.continuous_checkbox = QCheckBox("Continuous play")
        self.continuous_checkbox.setChecked(self.settings.continuous_play)
        self.sound_checkbox = QCheckBox("Sound cues")
        self.sound_checkbox.setChecked(bool(self.audio_service and self.audio_service.enabled))
        self.sound_checkbox.setEnabled(bool(self.audio_service and self.audio_service.available))
        self.sound_checkbox.toggled.connect(self.toggle_sound_cues)
        if not self.sound_checkbox.isEnabled():
            self.sound_checkbox.setToolTip("No supported local audio player was detected")
        self.ambience_checkbox = QCheckBox("Ambience")
        self.ambience_checkbox.setChecked(bool(self.audio_service and self.audio_service.ambience_enabled))
        self.ambience_checkbox.setEnabled(bool(self.audio_service and self.audio_service.available))
        self.ambience_checkbox.toggled.connect(self.toggle_ambience)
        self.music_checkbox = QCheckBox("Music")
        self.music_checkbox.setChecked(bool(self.audio_service and self.audio_service.music_enabled and self.audio_service.music_tracks))
        self.music_checkbox.setEnabled(bool(self.audio_service and self.audio_service.available and self.audio_service.music_tracks))
        self.music_checkbox.toggled.connect(self.toggle_music)
        if not self.music_checkbox.isEnabled():
            self.music_checkbox.setToolTip("Drop WAV tracks into the configured music folder to enable the playlist")
        self.fullscreen_button = QPushButton("Fullscreen")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.reset_stats_button = QPushButton("Reset season stats")
        self.reset_stats_button.setObjectName("dangerButton")
        self.reset_stats_button.clicked.connect(self.reset_statistics)
        shortcuts = QLabel("SPACE pause  ·  R resume  ·  F11 fullscreen")
        shortcuts.setStyleSheet("color:#759488;font-size:10px;")
        controls.addWidget(self.start_button)
        controls.addWidget(self.pause_button)
        controls.addSpacing(10)
        controls.addWidget(pace_label)
        controls.addWidget(self.pace_combo)
        controls.addWidget(self.continuous_checkbox)
        controls.addWidget(self.sound_checkbox)
        controls.addWidget(self.ambience_checkbox)
        controls.addWidget(self.music_checkbox)
        controls.addStretch()
        controls.addWidget(shortcuts)
        controls.addWidget(self.fullscreen_button)
        controls.addWidget(self.reset_stats_button)
        control_stack.addLayout(controls)

        mixer = QHBoxLayout()
        mixer.addWidget(QLabel("AUDIO MIX"))
        self.master_slider = self._audio_slider(self.settings.audio_volume, "Master")
        self.ambience_slider = self._audio_slider(self.settings.ambience_volume, "Ambience")
        self.effects_slider = self._audio_slider(self.settings.effects_volume, "Effects")
        self.music_slider = self._audio_slider(self.settings.music_volume, "Music")
        for caption, slider in (
            ("MASTER", self.master_slider),
            ("AMBIENCE", self.ambience_slider),
            ("EFFECTS", self.effects_slider),
            ("MUSIC", self.music_slider),
        ):
            label = QLabel(caption)
            label.setStyleSheet("color:#78968b;font-size:9px;font-weight:700;")
            mixer.addWidget(label)
            mixer.addWidget(slider)
            slider.sliderReleased.connect(self.update_audio_mix)
        mixer.addStretch()
        mixer.addWidget(QLabel("Voice level and device routing are available in config.json"))
        control_stack.addLayout(mixer)
        main.addWidget(control_bar)
        self.setCentralWidget(central)

        QShortcut(QKeySequence("Space"), self, activated=self.toggle_pause)
        QShortcut(QKeySequence("R"), self, activated=self.resume_game)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        self.update_visuals()

    @staticmethod
    def _status_badge(text):
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumWidth(92)
        label.setStyleSheet("background:#273f35;color:#aac0b7;border-radius:8px;padding:8px;font-weight:800;")
        return label

    @staticmethod
    def _audio_slider(value, tooltip):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(round(float(value) * 100))
        slider.setFixedWidth(110)
        slider.setToolTip(f"{tooltip} volume")
        return slider

    @staticmethod
    def _metric_label(caption, value):
        label = QLabel(f'<span style="color:#88aa9e;font-size:10px;font-weight:700">{caption}</span><br>'
                       f'<span style="color:#fff;font-size:17px;font-weight:700">{value}</span>')
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumWidth(105)
        return label

    @staticmethod
    def _data_panel(title):
        panel = QFrame()
        panel.setObjectName("dataPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        return panel

    def start_game(self):
        if self.running:
            return
        self.running = True
        self.paused = self.settings.start_paused and not self._has_started_once
        self._has_started_once = True
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("Resume" if self.paused else "Pause")
        self.update_visuals()
        if not self.paused:
            self.timer.start(0)

    def apply_pace_preset(self, index):
        action_delay, stage_delay, hand_delay = self.pace_combo.itemData(index)
        self.settings.action_delay_ms = action_delay
        self.settings.stage_delay_ms = stage_delay
        self.settings.between_hands_delay_ms = hand_delay
        self.game.action_delay_ms = action_delay
        self.pace_combo.setToolTip(
            f"{action_delay / 1000:g}s per action · {stage_delay / 1000:g}s between streets · "
            f"{hand_delay / 1000:g}s between hands"
        )

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("Fullscreen")
        else:
            self.showFullScreen()
            self.fullscreen_button.setText("Exit fullscreen")

    def toggle_sound_cues(self, enabled):
        if self.audio_service:
            self.audio_service.set_enabled(enabled)
            self.game.audio_state["desktop_enabled"] = self.audio_service.enabled
            self.game.audio_state["enabled"] = self.audio_service.enabled or bool(self.game.audio_state.get("browser_enabled"))

    def toggle_ambience(self, enabled):
        if self.audio_service:
            self.audio_service.set_ambience_enabled(enabled)
            self.game.audio_state["ambience_enabled"] = self.audio_service.ambience_enabled

    def toggle_music(self, enabled):
        if self.audio_service:
            self.audio_service.set_music_enabled(enabled)
            self.game.audio_state["music_enabled"] = self.audio_service.music_enabled and bool(self.audio_service.music_tracks)

    def update_audio_mix(self):
        if self.audio_service:
            master = self.master_slider.value() / 100
            ambience = self.ambience_slider.value() / 100
            effects = self.effects_slider.value() / 100
            music = self.music_slider.value() / 100
            self.audio_service.set_channel_volumes(
                master=master,
                ambience=ambience,
                effects=effects,
                music=music,
            )
            self.game.audio_state.update(
                {"master": master, "ambience": ambience, "effects": effects, "music": music}
            )

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
                delay = (
                    self.settings.between_tournaments_delay_ms
                    if self.game.tournament_complete
                    else self.settings.between_hands_delay_ms
                )
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
        snapshot = self.game.state_snapshot()
        self.update_community_cards(self.game.community_cards)
        dealer = "-" if self.game.dealer_position < 0 else self.game.players[self.game.dealer_position].name
        self._set_metric(self.hand_status_label, "HAND", f"{self.game.hand_number} · {self.game.stage}")
        self._set_metric(self.pot_label, "POT", f"{self.game.pot:,}")
        ante = f" · A{self.game.ante}" if self.game.ante else ""
        self._set_metric(self.blinds_label, "BLINDS", f"{self.game.small_blind} / {self.game.big_blind}{ante}")
        self._set_metric(self.dealer_label, "DEALER", dealer.replace("AI Player ", "P"))
        tournament = snapshot.get("tournament")
        format_value = f"SNG · L{tournament['level']}" if tournament else "CASH · FIXED"
        self._set_metric(self.mode_label, "FORMAT", format_value)
        self.stage_label.setText(self.game.stage.upper())
        pots = snapshot.get("pots") or []
        self.pot_detail_label.setText(
            "  ·  ".join(f"◉ {pot['kind'].upper()} {pot['amount']:,}" for pot in pots)
            or "◉ MAIN POT · Waiting for action"
        )

        if self.paused:
            status_text, status_style = "Ⅱ  PAUSED", "background:#5b4720;color:#f5d77e;"
        elif self._stage_in_progress:
            status_text, status_style = "●  THINKING", "background:#153f5a;color:#8fd2ff;"
        elif self.running:
            if self.game.service_health.get("ollama") in {"fallback", "circuit-open"}:
                status_text, status_style = "●  LIVE · FALLBACK", "background:#5b4720;color:#f5d77e;"
            else:
                status_text, status_style = "●  LIVE", "background:#174732;color:#77e0a1;"
        else:
            status_text, status_style = "○  STANDBY", "background:#273f35;color:#aac0b7;"
        self.run_status_label.setText(status_text)
        self.run_status_label.setStyleSheet(
            status_style + "border-radius:8px;padding:8px;font-weight:800;"
        )

        latest_commentary = list(self.game.commentary)[-1:] or [
            "Table ready. Start the broadcast when Ollama is online."
        ]
        self.commentary_banner.setText(latest_commentary[0])
        winner_lines = []
        for index, player in enumerate(self.game.players):
            if not player.last_action.startswith("Won"):
                continue
            player_state = snapshot["players"][index]
            amount = player.last_action.removeprefix("Won").strip()
            hand_name = player_state.get("hand_label") or "winning hand"
            payout = f" {amount} chips" if amount else ""
            winner_lines.append(f"WINNER  •  {player.name} takes{payout} with {hand_name}")
        if winner_lines:
            self.winner_spotlight_label.setText("   |   ".join(winner_lines))
            self.winner_spotlight_label.show()
        else:
            self.winner_spotlight_label.hide()

        for index, player in enumerate(self.game.players):
            player_state = snapshot["players"][index]
            profile_color = player.profile.color
            if player.eliminated or player.folded:
                frame_style = "background:#101a17;border:1px solid #293a34;border-radius:12px;"
                name_style = "color:#71827b;font-size:16px;font-weight:700;"
            elif player.last_action.startswith("Won"):
                frame_style = "background:#261f0d;border:2px solid #e2bd56;border-radius:12px;"
                name_style = "color:#ffe38a;font-size:16px;font-weight:900;"
            elif player.all_in:
                frame_style = "background:#321e1b;border:2px solid #d45f52;border-radius:12px;"
                name_style = "color:#ffd0c8;font-size:16px;font-weight:800;"
            elif index == self.game.next_to_act:
                frame_style = "background:#18392d;border:2px solid #e0b84f;border-radius:12px;"
                name_style = "color:#f7d875;font-size:16px;font-weight:800;"
            else:
                frame_style = f"background:#0c211a;border:1px solid {profile_color};border-radius:12px;"
                name_style = "color:#ffffff;font-size:16px;font-weight:700;"
            self.player_frames[index].setStyleSheet(f"QFrame#playerPanel {{{frame_style}}}")
            self.player_labels[index].setStyleSheet(name_style)
            self.player_labels[index].setText(player.name)
            equity = "…" if player_state["equity"] is None else f"{player_state['equity']:.1f}%"
            stats = player_state["stats"]
            self.player_stats_labels[index].setText(
                f"{player.chips:,} · EQ {equity} · VPIP {stats['vpip']:.0f} · PFR {stats['pfr']:.0f} · {player_state['hand_label'] or 'Waiting'}"
            )
            role = "D" if index == self.game.dealer_position else "SB" if index == self.game.small_blind_position else "BB" if index == self.game.big_blind_position else ""
            self.player_dealer_badges[index].setText(role)
            self.player_dealer_badges[index].setVisible(bool(role))
            self.update_player_cards(index, player.hand)
            self.update_player_wager(index, player.current_bet)
            self.player_action_labels[index].setText(player.last_action)
            if player.eliminated or player.folded:
                action_style = "background:#252e2a;color:#77847f;"
            elif index == self.game.next_to_act:
                action_style = "background:#d8ad43;color:#162119;"
            elif player.last_action.startswith(("Bet", "Raised", "All-in")):
                action_style = "background:#63352c;color:#ffd0bf;"
            elif player.last_action.startswith("Won"):
                action_style = "background:#d8ad43;color:#162119;"
            else:
                action_style = "background:#17382d;color:#d9e7e1;"
            self.player_action_labels[index].setStyleSheet(
                action_style + "border-radius:7px;padding:6px;font-weight:700;"
            )
        self.update_game_log()
        self.update_leaderboard()

    @staticmethod
    def _set_metric(label, caption, value):
        label.setText(
            f'<span style="color:#88aa9e;font-size:10px;font-weight:700">{caption}</span><br>'
            f'<span style="color:#fff;font-size:17px;font-weight:700">{value}</span>'
        )

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

    def update_player_wager(self, index, amount):
        amount = int(amount)
        label = self.player_wager_labels[index]
        if amount <= 0:
            self._discard_wager_animation(index)
            label.hide()
            self.player_wager_effects[index].setOpacity(1.0)
            self._shown_wagers[index] = 0
            return
        label.setText(f"● ● ●  {amount:,}")
        label.show()
        if amount != self._shown_wagers[index] and not self.settings.reduced_motion:
            self._discard_wager_animation(index)
            effect = self.player_wager_effects[index]
            animation = QPropertyAnimation(effect, b"opacity", self)
            animation.setDuration(480)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            self._wager_animations[index] = animation
            animation.finished.connect(
                lambda seat=index, current=animation: self._finish_wager_animation(seat, current)
            )
            animation.start()
        else:
            self.player_wager_effects[index].setOpacity(1.0)
        self._shown_wagers[index] = amount

    def _discard_wager_animation(self, index):
        animation = self._wager_animations.pop(index, None)
        if animation is not None:
            animation.stop()
            animation.deleteLater()

    def _finish_wager_animation(self, index, animation):
        if self._wager_animations.get(index) is animation:
            self._wager_animations.pop(index, None)
        animation.deleteLater()

    def _add_animated_card(self, layout, card):
        duration = 0 if self.settings.reduced_motion else self.settings.animation_duration_ms
        label = AnimatedCardLabel(self.get_card_image(card), duration)
        layout.addWidget(label)
        if duration:
            QTimer.singleShot(0, label.animate_in)
        else:
            label.set_flip_progress(1.0)

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
        snapshot = tuple(self.game.get_log())
        if snapshot == self._last_log_snapshot:
            return
        self._last_log_snapshot = snapshot
        self.game_log.setPlainText("\n".join(snapshot))
        self.game_log.moveCursor(self.game_log.textCursor().End)

    def update_win_percentages(self):
        for index, player in enumerate(self.game.players):
            self.player_stats_labels[index].setText(
                f"{player.chips:,} chips  ·  {player.wins}W {player.ties}T  ·  {player.get_win_percentage():.1f}%"
            )

    def update_leaderboard(self):
        data = self.game.metrics_store.snapshot() if self.game.metrics_store else {"players": {}}
        signature = tuple(
            (
                player.name,
                data["players"].get(player.name, {}).get("hands_played", player.total_rounds),
                data["players"].get(player.name, {}).get("hands_won", player.wins),
                data["players"].get(player.name, {}).get("hands_tied", player.ties),
                data["players"].get(player.name, {}).get("net_chips", 0),
            )
            for player in self.game.players
        )
        if signature == self._leaderboard_signature:
            return
        self._leaderboard_signature = signature
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


def run_gui(game, settings, audio_service=None, app=None):
    app = app or QApplication.instance() or QApplication(sys.argv)
    gui = PokerGUI(game, settings, audio_service=audio_service)
    if settings.fullscreen:
        gui.showFullScreen()
        gui.fullscreen_button.setText("Exit fullscreen")
    else:
        gui.show()
    return app.exec_()
