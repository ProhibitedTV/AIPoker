from main import build_settings, parse_args
from scripts.preview_overlay import parse_args as parse_preview_args


def test_audio_cli_overrides_are_clamped(tmp_path):
    missing_config = tmp_path / "missing.json"
    settings = build_settings(
        parse_args(["--config", str(missing_config), "--audio-volume", "4", "--mute"])
    )
    assert settings.audio_volume == 1.0
    assert not settings.audio_enabled


def test_broadcast_pacing_cli_overrides_are_milliseconds(tmp_path):
    settings = build_settings(
        parse_args(
            [
                "--config", str(tmp_path / "missing.json"),
                "--action-delay", "1.4",
                "--deal-delay", "0.35",
                "--stage-delay", "4.5",
            ]
        )
    )
    assert settings.action_delay_ms == 1400
    assert settings.deal_delay_ms == 350
    assert settings.stage_delay_ms == 4500


def test_overlay_preview_can_exercise_six_seat_layout():
    assert parse_preview_args(["--players", "6"]).players == 6
