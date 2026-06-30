from game import PokerGame
from lounge import RESPONSIBLE_LABEL, adjusted_temperature, build_lounge_snapshot, player_lounge_for
from ollama_integration import _fallback_decision


def test_lounge_snapshot_is_public_deterministic_and_safe():
    players = [{"id": "atlas", "name": "Atlas"}, {"id": "vega", "name": "Vega"}]
    first = build_lounge_snapshot(players, hand_number=17, interval_hands=2)
    second = build_lounge_snapshot(players, hand_number=17, interval_hands=2)

    assert first == second
    assert first["schema_version"] == 1
    assert first["enabled"]
    assert first["responsible_label"] == RESPONSIBLE_LABEL
    assert "NO REAL ALCOHOL" in first["responsible_label"]
    assert first["venue"]["district"]
    assert first["scene_name"]
    assert first["venue_zone"]
    assert first["service_bot"]
    assert first["table_mood"]
    assert first["atmosphere_line"]
    assert first["rivalry"]["headline"]
    assert first["service_round"] >= 1
    assert 0 <= first["pressure_index"] <= 100
    assert set(first["table_effects"]) == {"risk", "bluff", "focus"}
    assert first["broadcast_cue"]
    assert "no real alcohol" in first["safety_copy"].lower()
    assert set(first["players"]) == {"atlas", "vega"}
    assert first["players"]["atlas"]["drink"] == "Chrome Old Fashioned"
    assert first["players"]["atlas"]["neon_color"].startswith("#")
    assert first["players"]["atlas"]["glassware"]
    assert first["players"]["atlas"]["visual_tell"]
    assert first["players"]["atlas"]["service_level"]
    assert set(first["players"]["atlas"]["current_effects"]) == {"risk", "bluff", "focus"}
    assert 0 <= first["players"]["vega"]["charge"] <= 100


def test_lounge_can_be_disabled_without_removing_schema():
    snapshot = build_lounge_snapshot([{"id": "atlas", "name": "Atlas"}], enabled=False)
    player = player_lounge_for(snapshot, "atlas")

    assert snapshot["schema_version"] == 1
    assert not snapshot["enabled"]
    assert snapshot["players"] == {}
    assert snapshot["venue"] == {}
    assert snapshot["scene_name"] == ""
    assert snapshot["service_bot"] == ""
    assert not snapshot["rivalry"]["active"]
    assert snapshot["pressure_index"] == 0
    assert not player["enabled"]
    assert player["risk_delta"] == 0
    assert player["current_effects"] == {"risk": 0, "bluff": 0, "focus": 0}


def test_lounge_adjusts_model_temperature_without_unbounded_values():
    lounge_state = {
        "enabled": True,
        "risk_delta": 18,
        "bluff_delta": 12,
        "focus_delta": -3,
    }

    assert adjusted_temperature(0.25, lounge_state) > 0.25
    assert adjusted_temperature(2.0, lounge_state) == 1.2
    assert adjusted_temperature(0.2, {"enabled": False}) == 0.2


def test_game_state_and_decision_context_publish_lounge_modifiers():
    game = PokerGame(
        2,
        auto_restore=False,
        decision_provider=lambda *_: "check",
        ai_lounge_enabled=True,
        ai_lounge_interval_hands=1,
    )
    game.hand_number = 11
    game.stage = "Pre-Flop"
    game.players[0].deal_hand([(14, "spades"), (14, "hearts")])
    game.players[1].deal_hand([(2, "clubs"), (7, "diamonds")])
    game._update_lounge_state()

    state = game.state_snapshot()
    context = game._decision_context(game.players[0], [{"action": "check"}], 0, game.big_blind)

    assert state["lounge"]["enabled"]
    assert "venue" in state["lounge"]
    assert "service_bot" in state["lounge"]
    assert "rivalry" in state["lounge"]
    assert "atmosphere_line" in state["lounge"]
    assert "pressure_index" in state["lounge"]
    assert state["players"][0]["lounge"]["enabled"]
    assert "drink" in state["players"][0]["lounge"]
    assert "visual_tell" in state["players"][0]["lounge"]
    assert "service_level" in state["players"][0]["lounge"]
    assert context["lounge"]["player"]["id"] == game.players[0].id
    assert context["lounge"]["player"]["current_effects"]["risk"] == context["lounge"]["player"]["risk_delta"]
    assert context["profile"]["temperature"] != context["profile"]["base_temperature"]
    assert "fictional AI lounge modifier" in context["strategy_hint"]["lounge_hint"]


def test_rules_safe_fallback_uses_lounge_bias_but_stays_legal():
    legal = {
        "check": {"action": "check", "target": None},
        "bet": {"action": "bet", "min_target": 40, "max_target": 200},
    }
    decision = _fallback_decision(
        legal,
        stack=1000,
        lounge={"player": {"enabled": True, "risk_delta": 24, "bluff_delta": 6, "focus_delta": -2, "charge": 90}},
    )

    assert decision == {"action": "bet", "amount": 40, "table_talk": ""}
