"""Application configuration for unattended casino/broadcast play."""

from dataclasses import asdict, dataclass, field, fields
import json
from pathlib import Path

from casino_program import default_casino_blocks
from program_rotation import default_variety_segments


def default_profiles():
    return [
        {
            "id": "atlas",
            "name": "Atlas",
            "persona": "disciplined tight-aggressive analyst",
            "model": "auto",
            "color": "#e7bd55",
            "voice": "atlas_rvc",
            "temperature": 0.18,
            "avatar": "chrome_oracle",
            "sigil": "AX",
            "tagline": "Cold solver in a gold visor",
        },
        {
            "id": "vega",
            "name": "Vega",
            "persona": "fearless loose-aggressive pressure player",
            "model": "auto",
            "color": "#ef6b67",
            "voice": "vega_rvc",
            "temperature": 0.38,
            "avatar": "redline_jackal",
            "sigil": "VX",
            "tagline": "Redline pressure dealer",
        },
        {
            "id": "nova",
            "name": "Nova",
            "persona": "balanced adaptive opponent reader",
            "model": "auto",
            "color": "#61b7ff",
            "voice": "nova_rvc",
            "temperature": 0.27,
            "avatar": "blue_nebula",
            "sigil": "NX",
            "tagline": "Balanced signal reader",
        },
        {
            "id": "echo",
            "name": "Echo",
            "persona": "patient deceptive trap-oriented player",
            "model": "auto",
            "color": "#a98aff",
            "voice": "echo_rvc",
            "temperature": 0.3,
            "avatar": "violet_phantom",
            "sigil": "EX",
            "tagline": "Trap-door mirror mask",
        },
        {
            "id": "river",
            "name": "River",
            "persona": "creative position-aware player",
            "model": "auto",
            "color": "#5ed39a",
            "voice": "river_rvc",
            "temperature": 0.32,
            "avatar": "green_syndicate",
            "sigil": "RV",
            "tagline": "Late-street wire runner",
        },
        {
            "id": "onyx",
            "name": "Onyx",
            "persona": "calm exploitative counter-puncher",
            "model": "auto",
            "color": "#d6d8dc",
            "voice": "onyx_rvc",
            "temperature": 0.22,
            "avatar": "silver_warden",
            "sigil": "OX",
            "tagline": "Quiet countermeasure unit",
        },
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
    allow_multiple_instances: bool = False
    headless: bool = False
    single_instance_lock_path: str = "data/aipoker.pid"
    fullscreen: bool = True
    game_mode: str = "tournament"
    table_size: int = 4
    starting_chips: int = 2000
    rng_seed: int | None = None
    player_profiles: list = field(default_factory=default_profiles)
    hands_per_level: int = 8
    tournament_levels: list = field(default_factory=default_tournament_levels)
    variety_rotation_enabled: bool = True
    variety_rotation_interval_hands: int = 24
    variety_segments: list = field(default_factory=default_variety_segments)
    ai_lounge_enabled: bool = True
    ai_lounge_interval_hands: int = 4
    ai_lounge_max_charge: int = 100
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
    overlay_director_enabled: bool = True
    overlay_rotation_enabled: bool = True
    overlay_rotation_interval_ms: int = 9000
    overlay_narration_enabled: bool = False
    overlay_showrunner_enabled: bool = True
    overlay_voice_cues_enabled: bool = True
    overlay_voice_cooldown_ms: int = 9000
    overlay_non_reader_mode: bool = True
    overlay_night_city_intensity: str = "high"
    overlay_venue_theme_enabled: bool = True
    overlay_recap_duration_ms: int = 7500
    overlay_moment_duration_ms: int = 6200
    overlay_visual_debug: bool = False
    overlay_engagement_enabled: bool = True
    overlay_follow_message: str = "Follow for 24/7 autonomous AI poker."
    overlay_chat_prompt: str = "Call out the next winner in chat."
    casino_bumpers_enabled: bool = True
    casino_bumper_frequency: str = "selected_hands"
    casino_bumper_duration_ms: int = 6500
    casino_bumper_responsible_label: bool = True
    casino_bumper_style: str = "night_city_recaps"
    casino_program_enabled: bool = True
    casino_program_starting_bankroll: int = 5000
    casino_program_unit: int = 100
    casino_program_blocks: list = field(default_factory=default_casino_blocks)
    tts_enabled: bool = False
    tts_volume: float = 0.8
    tts_rate: int = 175
    tts_voice: str = ""
    voice_clips_enabled: bool = True
    voice_clip_cache_path: str = "data/voice_cache"
    voice_clip_max_cache: int = 160
    voice_tts_backend: str = "pyttsx3"
    rvc_enabled: bool = False
    rvc_command: list = field(default_factory=list)
    rvc_models_path: str = "voices/rvc"
    rvc_timeout_seconds: int = 45
    rvc_pitch: int = 0
    audio_enabled: bool = False
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
        self.variety_rotation_interval_hands = max(1, int(self.variety_rotation_interval_hands))
        if not isinstance(self.variety_segments, list) or not self.variety_segments:
            self.variety_segments = default_variety_segments()
        self.ai_lounge_interval_hands = max(1, int(self.ai_lounge_interval_hands))
        self.ai_lounge_max_charge = max(0, min(100, int(self.ai_lounge_max_charge)))
        self.overlay_recap_duration_ms = max(1200, int(self.overlay_recap_duration_ms))
        self.overlay_moment_duration_ms = max(1200, int(self.overlay_moment_duration_ms))
        self.overlay_rotation_interval_ms = max(5000, int(self.overlay_rotation_interval_ms))
        self.overlay_voice_cooldown_ms = max(3000, int(self.overlay_voice_cooldown_ms))
        if self.overlay_night_city_intensity not in {"low", "medium", "high"}:
            self.overlay_night_city_intensity = "high"
        self.overlay_follow_message = str(self.overlay_follow_message or "Follow for 24/7 autonomous AI poker.")[:96]
        self.overlay_chat_prompt = str(self.overlay_chat_prompt or "Call out the next winner in chat.")[:96]
        self.voice_clip_max_cache = max(8, int(self.voice_clip_max_cache))
        self.voice_tts_backend = str(self.voice_tts_backend or "pyttsx3").strip().lower()
        if not isinstance(self.rvc_command, list):
            self.rvc_command = []
        self.rvc_timeout_seconds = max(5, int(self.rvc_timeout_seconds or 45))
        self.rvc_pitch = int(self.rvc_pitch or 0)
        self.casino_bumper_duration_ms = max(4000, min(8000, int(self.casino_bumper_duration_ms)))
        if self.casino_bumper_frequency not in {"selected_hands", "every_hand", "off"}:
            self.casino_bumper_frequency = "selected_hands"
        if self.casino_bumper_style not in {"night_city_recaps", "classic"}:
            self.casino_bumper_style = "night_city_recaps"
        self.casino_program_starting_bankroll = max(1, int(self.casino_program_starting_bankroll))
        self.casino_program_unit = max(1, int(self.casino_program_unit))
        if not isinstance(self.casino_program_blocks, list) or not self.casino_program_blocks:
            self.casino_program_blocks = default_casino_blocks()

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
