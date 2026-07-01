from pathlib import Path

from game import PokerGame
from overlay_server import OverlayServer
from scripts import production_preflight as preflight
from settings import AppSettings


def statuses(checks):
    return {check.name: check.status for check in checks}


def test_preflight_settings_and_paths_are_production_oriented(tmp_path):
    settings = AppSettings(
        stats_path=str(tmp_path / "leaderboard.json"),
        checkpoint_path=str(tmp_path / "checkpoint.json"),
        hand_history_path=str(tmp_path / "hand_history.jsonl"),
        audio_cache_path=str(tmp_path / "audio"),
        single_instance_lock_path=str(tmp_path / "aipoker.pid"),
        music_path=str(tmp_path / "music"),
        sound_effects_path=str(tmp_path / "sound_effects"),
    )

    checks = preflight.check_settings(settings) + preflight.check_paths(settings)
    by_name = statuses(checks)

    assert by_name["overlay.enabled"] == "pass"
    assert by_name["simulation.disclaimer"] == "pass"
    assert by_name["casino.program"] == "pass"
    assert by_name["single.instance"] == "pass"
    assert by_name["stats.path"] == "pass"
    assert by_name["checkpoint.path"] == "pass"


def test_preflight_ollama_warning_is_not_a_release_failure(monkeypatch):
    monkeypatch.setattr(preflight, "get_available_models", lambda force=True: [])

    checks = preflight.check_ollama(strict=False)
    strict = preflight.check_ollama(strict=True)

    assert checks[0].status == "warn"
    assert strict[0].status == "fail"


def test_static_overlay_has_required_safety_markers_and_no_wager_cta():
    checks = preflight.check_static_overlay_source()
    by_name = statuses(checks)

    assert by_name["overlay.markers"] == "pass"
    assert by_name["overlay.no_wager_cta"] == "pass"


def test_live_preflight_checks_overlay_endpoints():
    game = PokerGame(2, auto_restore=False)
    server = OverlayServer(game, port=0).start()
    try:
        game.service_health["overlay"] = "online"
        checks = preflight.check_live_server(f"http://127.0.0.1:{server.port}")
    finally:
        server.close()

    by_name = statuses(checks)
    assert by_name["live.health"] == "pass"
    assert by_name["live.state_schema"] == "pass"
    assert by_name["live.casino_state"] == "pass"
    assert by_name["live.overlay_html"] == "pass"
    assert by_name["live.no_wager_cta"] == "pass"
