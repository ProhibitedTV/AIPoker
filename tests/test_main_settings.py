from main import build_settings, parse_args


def test_audio_cli_overrides_are_clamped(tmp_path):
    missing_config = tmp_path / "missing.json"
    settings = build_settings(
        parse_args(["--config", str(missing_config), "--audio-volume", "4", "--mute"])
    )
    assert settings.audio_volume == 1.0
    assert not settings.audio_enabled
