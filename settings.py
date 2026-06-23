"""Application configuration for unattended casino/broadcast play."""

from dataclasses import asdict, dataclass, field, fields
import json
from pathlib import Path


def default_profiles():
    return [
        {"id": "atlas", "name": "Atlas", "persona": "disciplined tight-aggressive analyst", "model": "auto", "color": "#e7bd55", "voice": "", "temperature": 0.18},
        {"id": "vega", "name": "Vega", "persona": "fearless loose-aggressive pressure player", "model": "auto", "color": "#ef6b67", "voice": "", "temperature": 0.38},
        {"id": "nova", "name": "Nova", "persona": "balanced adaptive opponent reader", "model": "auto", "color": "#61b7ff", "voice": "", "temperature": 0.27},
        {"id": "echo", "name": "Echo", "persona": "patient deceptive trap-oriented player", "model": "auto", "color": "#a98aff", "voice": "", "temperature": 0.3},
        {"id": "river", "name": "River", "persona": "creative position-aware player", "model": "auto", "color": "#5ed39a", "voice": "", "temperature": 0.32},
        {"id": "onyx", "name": "Onyx", "persona": "calm exploitative counter-puncher", "model": "auto", "color": "#d6d8dc", "voice": "", "temperature": 0.22},
    ]


def default_tournament_levels():
    return [
        {"small": 10, "big": 20, "ante": 0},
        {"small": 15, "big": 30, "ante": 0},
        {"small": 25, "big": 50, "ante": 0},
        {"small": 40, "big": 80, "ante": 80},
        {"small": 60, "big": 120, "ante": 120},
        {"small": 100, "big": 200, "ante": 200},
        {"small": 150, "big": 300, "ante": 300},
        {"small": 250, "big": 500, "ante": 500},
    ]


@dataclass
class AppSettings:
    action_delay_ms: int = 1250
    deal_delay_ms: int = 320
    stage_delay_ms: int = 4500
    between_hands_delay_ms: int = 6500
    between_tournaments_delay_ms: int = 15000
    animation_duration_ms: int = 720
    continuous_play: bool = True
    start_paused: bool = False
    fullscreen: bool = True
    game_mode: str = "tournament"
    table_size: int = 4
    starting_chips: int = 2000
    rng_seed: int | None = None
    player_profiles: list = field(default_factory=default_profiles)
    hands_per_level: int = 8
    tournament_levels: list = field(default_factory=default_tournament_levels)
    checkpoint_path: str = "data/checkpoint.json"
    hand_history_path: str = "data/hand_history.jsonl"
    equity_samples: int = 1600
    analysis_depth: str = "full"
    reduced_motion: bool = False
    classic_two_color_cards: bool = True
    overlay_enabled: bool = True
    overlay_host: str = "127.0.0.1"
    overlay_port: int = 8765
    overlay_background: str = "#071c13"
    overlay_accent: str = "#e6b94a"
    overlay_font: str = "Inter, Segoe UI, Arial, sans-serif"
    overlay_layout: str = "horizontal"
    overlay_audio_enabled: bool = True
    overlay_disclaimer_enabled: bool = True
    tts_enabled: bool = False
    tts_volume: float = 0.8
    tts_rate: int = 175
    tts_voice: str = ""
    audio_enabled: bool = True
    audio_volume: float = 0.45
    ambience_enabled: bool = True
    ambience_volume: float = 0.16
    effects_volume: float = 0.72
    music_enabled: bool = True
    music_path: str = "music"
    music_volume: float = 0.18
    music_shuffle: bool = True
    sound_effects_path: str = "sound_effects"
    voice_volume: float = 0.8
    audio_cache_path: str = "data/audio_cache"
    stats_path: str = "data/leaderboard.json"
    small_blind: int = 10
    big_blind: int = 20

    def __post_init__(self):
        self.table_size = max(2, min(6, int(self.table_size)))
        self.game_mode = "tournament" if self.game_mode in {"tournament", "sit_and_go", "sng"} else "cash"
        self.starting_chips = max(1, int(self.starting_chips))
        self.hands_per_level = max(1, int(self.hands_per_level))

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            return cls()
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        allowed = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in raw.items() if key in allowed})

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(self), handle, indent=2)
