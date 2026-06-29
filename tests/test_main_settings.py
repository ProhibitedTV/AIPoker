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


def test_overlay_director_cli_overrides(tmp_path):
    settings = build_settings(
        parse_args(
            [
                "--config", str(tmp_path / "missing.json"),
                "--no-director",
                "--no-overlay-rotation",
                "--overlay-rotation-interval", "12.5",
                "--overlay-narration",
                "--overlay-recap-duration", "8.25",
                "--overlay-moment-duration", "5.5",
                "--overlay-visual-debug",
            ]
        )
    )
    assert not settings.overlay_director_enabled
    assert not settings.overlay_rotation_enabled
    assert settings.overlay_rotation_interval_ms == 12500
    assert settings.overlay_narration_enabled
    assert settings.overlay_recap_duration_ms == 8250
    assert settings.overlay_moment_duration_ms == 5500
    assert settings.overlay_visual_debug


def test_variety_rotation_cli_overrides(tmp_path):
    settings = build_settings(
        parse_args(
            [
                "--config", str(tmp_path / "missing.json"),
                "--no-variety-rotation",
                "--variety-interval-hands", "9",
            ]
        )
    )
    assert not settings.variety_rotation_enabled
    assert settings.variety_rotation_interval_hands == 9


def test_casino_bumper_cli_override(tmp_path):
    settings = build_settings(
        parse_args(["--config", str(tmp_path / "missing.json"), "--no-casino-bumpers"])
    )
    assert not settings.casino_bumpers_enabled
    assert settings.casino_bumper_duration_ms == 6500


def test_overlay_preview_can_exercise_six_seat_layout():
    assert parse_preview_args(["--players", "6"]).players == 6
    args = parse_preview_args(["--no-director", "--no-variety-rotation", "--no-casino-bumpers", "--visual-debug", "--recap-duration", "8"])
    assert args.no_director
    assert args.no_variety_rotation
    assert args.no_casino_bumpers
    assert args.visual_debug
    assert args.recap_duration == 8


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
