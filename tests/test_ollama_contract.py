from ollama_integration import _json_safe_context, _validate_decision, sanitize_decision


def test_prompt_whitelist_strips_opponent_cards_and_viewer_analysis():
    context = {
        "player": {"id": "atlas", "hole_cards": [{"rank": 14, "suit": "spades"}]},
        "players": [
            {
                "id": "vega",
                "name": "Vega",
                "stack": 2000,
                "hole_cards": [{"rank": 13, "suit": "hearts"}],
                "equity": 91.2,
            }
        ],
        "viewer_equity": {"vega": 91.2},
        "table_program": {"segment_id": "ante_splash_cash", "strategy_hint": "Antes are public."},
        "presentation": {"bumper": {"enabled": True, "kind": "winner_jackpot"}},
        "community_cards_raw": [(2, "clubs")],
        "legal_actions": [{"action": "check"}],
    }
    safe = _json_safe_context(context)
    assert safe["player"]["hole_cards"]
    assert "hole_cards" not in safe["players"][0]
    assert "equity" not in safe["players"][0]
    assert "viewer_equity" not in safe
    assert "presentation" not in safe
    assert safe["table_program"]["segment_id"] == "ante_splash_cash"
    assert "community_cards_raw" not in safe


def test_structured_decisions_require_legal_bounded_targets():
    legal = {
        "fold": {"action": "fold"},
        "call": {"action": "call", "amount": 20, "target": 40},
        "raise": {"action": "raise", "min_target": 80, "max_target": 500},
    }
    assert _validate_decision({"action": "raise", "amount": 120, "table_talk": "Your move."}, legal) == {
        "action": "raise", "amount": 120, "table_talk": "Your move."
    }
    assert _validate_decision({"action": "raise", "amount": 60}, legal) is None
    assert _validate_decision({"action": "check"}, legal) is None
    assert _validate_decision({"action": "call", "amount": 999}, legal)["amount"] == 40


def test_compatibility_parser_recognizes_complete_action_vocabulary():
    assert sanitize_decision("I CALL.") == "call"
    assert sanitize_decision("all-in") == "all_in"
