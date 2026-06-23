from main import build_settings, parse_args
from scripts.preview_overlay import apply_health_fixture, parse_args as parse_preview_args
from game import PokerGame


def test_audio_cli_overrides_are_clamped(tmp_path):
    missing_config = tmp_path / "missing.json"
    settings = build_settings(
        parse_args(["--config", str(missing_config), "--audio-volume", "4", "--mute", "--music-volume", "2"])
    )
    assert settings.audio_volume == 1.0
    assert settings.music_volume == 1.0
    assert not settings.audio_enabled


def test_music_cli_can_disable_and_repoint_playlist(tmp_path):
    music_dir = tmp_path / "casino_music"
    settings = build_settings(
        parse_args(["--config", str(tmp_path / "missing.json"), "--no-music", "--music-path", str(music_dir)])
    )
    assert not settings.music_enabled
    assert settings.music_path == str(music_dir)


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


def test_simulation_disclaimer_can_be_disabled_for_private_preview(tmp_path):
    settings = build_settings(
        parse_args(["--config", str(tmp_path / "missing.json"), "--no-simulation-disclaimer"])
    )
    assert not settings.overlay_disclaimer_enabled
    assert parse_preview_args(["--no-simulation-disclaimer"]).no_simulation_disclaimer


def test_preview_health_fixtures_cover_normal_degraded_and_recovery():
    game = PokerGame(2, auto_restore=False)
    for fixture, expected in (
        ("normal", "normal"),
        ("degraded", "degraded"),
        ("recovered", "recovered"),
        ("persistence-warning", "warning"),
        ("audio-muted", "notice"),
    ):
        game.service_health.update({"ollama": "preview", "persistence": "ready", "checkpoint": "standby"})
        game.audio_state["enabled"] = True
        apply_health_fixture(game, fixture)
        assert game.health_snapshot()["overall"] == expected
