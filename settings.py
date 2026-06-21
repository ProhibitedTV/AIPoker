"""Application configuration for unattended and streaming play."""

from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path


@dataclass
class AppSettings:
    stage_delay_ms: int = 5000
    between_hands_delay_ms: int = 5000
    animation_duration_ms: int = 650
    continuous_play: bool = True
    start_paused: bool = False
    fullscreen: bool = True
    overlay_enabled: bool = True
    overlay_host: str = "127.0.0.1"
    overlay_port: int = 8765
    overlay_background: str = "#071c13"
    overlay_accent: str = "#e6b94a"
    overlay_font: str = "Arial, sans-serif"
    overlay_layout: str = "horizontal"
    tts_enabled: bool = False
    tts_volume: float = 0.9
    tts_rate: int = 175
    tts_voice: str = ""
    stats_path: str = "data/leaderboard.json"
    small_blind: int = 10
    big_blind: int = 20

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            return cls()
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in raw.items() if key in allowed})

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(self), handle, indent=2)
