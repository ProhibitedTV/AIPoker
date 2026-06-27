import json
from pathlib import Path

from broadcast_context import build_broadcast_context
from scripts import benchmark_models, broadcast_smoke, replay_hand, visual_smoke


def test_broadcast_context_has_program_league_story_and_personality():
    metrics = {
        "session_id": "season-abc",
        "hands_played": 12,
        "tournaments_played": 1,
        "players": {
            "Atlas": {"net_chips": 300, "tournament_wins": 1, "vpip_rate": 21, "pfr_rate": 15, "aggression_factor": 2.4, "showdown_win_rate": 60, "current_streak": 2},
            "Vega": {"net_chips": -120, "vpip_rate": 48, "pfr_rate": 35, "aggression_factor": 3.1, "showdown_win_rate": 42, "current_streak": -2},
        },
        "notable_hands": [{"hand": 7, "pot": 2600, "winners": ["Atlas"]}],
        "tournaments": [{"number": 1, "winner": "Atlas", "finishes": {"Atlas": 1}}],
    }
    players = [
        {"id": "atlas", "name": "Atlas", "chips": 2300, "win_percentage": 50},
        {"id": "vega", "name": "Vega", "chips": 1700, "win_percentage": 20},
    ]

    context = build_broadcast_context(metrics, players, mode="tournament", tournament={"number": 1, "level": 2}, hand_number=12, stage="Turn")

    assert context["program"]["segment"] == "Live Sit & Go"
    assert context["league"]["records"]["largest_pot"]["amount"] == 2600
    assert len(context["storylines"]) >= 3
    assert context["personality_arcs"]["atlas"]["style"] in {"Pressure Artist", "Balanced Contender", "Disciplined Grinder", "Adaptive Competitor"}


def test_replay_hand_lists_and_exports_html(tmp_path):
    history = tmp_path / "hand_history.jsonl"
    history.write_text(
        json.dumps(
            {
                "summary": {"hand_number": 3, "mode": "tournament", "pot": 480, "winners": ["Nova"], "payouts": {"Nova": 480}, "burned_cards": []},
                "events": [{"id": 1, "type": "action", "message": "Nova moves all-in"}, {"id": 2, "type": "winner", "message": "Nova wins"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    hands = replay_hand.load_hands(history)
    assert replay_hand.recent_table(hands)[0]["hand"] == 3
    html = replay_hand.render_html(replay_hand.select_hand(hands, hand_id=3))
    assert "Nova received 480 chips" in html


def test_benchmark_fixture_prompt_never_contains_opponent_hole_cards():
    payload = benchmark_models.build_payload("fixture-local", 0.2, benchmark_models.FIXTURE_CONTEXTS[0])
    prompt = json.dumps(payload)
    assert "hole_cards" in prompt
    assert "Vega" in prompt
    assert "rank" in prompt
    assert "opponent_hole_cards" not in prompt

    result = benchmark_models.benchmark_model("fixture-local", 0.2, fixture=True)
    assert result["samples"] >= 2
    assert result["malformed_json_rate"] == 0


def test_broadcast_smoke_generates_artifacts(tmp_path):
    summary = broadcast_smoke.generate_artifacts(tmp_path, players=2)
    assert summary["ok"]
    assert (tmp_path / "overlay-full.html").exists()
    assert (tmp_path / "overlay-compact.html").exists()
    assert summary["fixture_modes"]["decision"] == "decision"
    assert summary["fixture_modes"]["all_in"] == "all_in"
    assert summary["fixture_modes"]["bumper"] == "recap"
    assert (tmp_path / "overlay-full-recap.html").exists()
    assert (tmp_path / "overlay-full-bumper.html").exists()
    assert "DEALER STATION" in (tmp_path / "overlay-full.html").read_text(encoding="utf-8")
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert "program" in state
    assert "storylines" in state


def test_visual_smoke_checks_director_fixture_modes(tmp_path):
    result = visual_smoke.run_visual_smoke(tmp_path, players=2)
    assert result["ok"]
    assert (tmp_path / "visual-summary.json").exists()
    assert result["broadcast_summary"]["fixture_modes"]["recap"] == "recap"
    assert result["broadcast_summary"]["fixture_modes"]["bumper"] == "recap"
