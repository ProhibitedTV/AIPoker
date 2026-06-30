import requests

from ollama_integration import (
    MODEL_REGISTRY,
    _close_circuit,
    _json_safe_context,
    _validate_decision,
    get_ai_decision,
    sanitize_decision,
)


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
        "lounge": {
            "enabled": True,
            "phase": "Neon hour",
            "player": {"drink": "Chrome Old Fashioned", "decision_hint": "Public fictional modifier."},
        },
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
    assert safe["lounge"]["player"]["drink"] == "Chrome Old Fashioned"
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


def test_structured_decisions_tolerate_common_local_model_json_drift():
    legal = {
        "check": {"action": "check", "target": None},
        "raise": {"action": "raise", "min_target": 80, "max_target": 500},
    }
    assert _validate_decision({"action_check": "null", "amount": None, "table_talk": []}, legal) == {
        "action": "check",
        "amount": None,
        "table_talk": "",
    }
    assert _validate_decision({"raise": True, "amount": 120, "table_talk": {"line": "Neon pressure."}}, legal) == {
        "action": "raise",
        "amount": 120,
        "table_talk": "Neon pressure.",
    }
    assert _validate_decision({"action_fold": True}, legal) is None


def test_compatibility_parser_recognizes_complete_action_vocabulary():
    assert sanitize_decision("I CALL.") == "call"
    assert sanitize_decision("all-in") == "all_in"


def test_auto_model_prefers_interactive_lfm_over_heavy_gpt_oss():
    MODEL_REGISTRY._models = ["lfm2.5:latest", "gpt-oss:20b"]
    MODEL_REGISTRY._updated = 10**9
    try:
        assert MODEL_REGISTRY.resolve("auto", 0) == "lfm2.5:latest"
        assert MODEL_REGISTRY.resolve("auto", 1) == "lfm2.5:latest"
    finally:
        MODEL_REGISTRY._models = []
        MODEL_REGISTRY._updated = 0.0


def test_get_ai_decision_uses_ollama_chat_when_model_available(monkeypatch):
    _close_circuit()
    MODEL_REGISTRY._models = []
    MODEL_REGISTRY._updated = 0.0
    calls = {"chat": 0}

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(*_args, **_kwargs):
        return Response({"models": [{"name": "qwen2.5:7b"}]})

    def fake_post(_url, json, timeout):
        calls["chat"] += 1
        assert json["model"] == "qwen2.5:7b"
        assert timeout > 0
        return Response({"message": {"content": '{"action":"raise","amount":80,"table_talk":"Pressure now."}'}})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    decision = get_ai_decision(
        {
            "player": {"id": "atlas", "seat": 0, "stack": 2000, "hole_cards": []},
            "profile": {"model": "auto", "persona": "disciplined", "temperature": 0.2},
            "legal_actions": [{"action": "raise", "min_target": 60, "max_target": 200}],
        }
    )

    assert calls["chat"] == 1
    assert decision["action"] == "raise"
    assert decision["amount"] == 80
    assert decision["_model_status"] == "online"
    assert decision["_model"] == "qwen2.5:7b"


def test_get_ai_decision_falls_back_to_generate_when_chat_thinks_instead_of_json(monkeypatch):
    _close_circuit()
    MODEL_REGISTRY._models = []
    MODEL_REGISTRY._updated = 0.0
    calls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(*_args, **_kwargs):
        return Response({"models": [{"name": "lfm2.5:latest"}]})

    def fake_post(url, json, timeout):
        calls.append(url)
        assert json["model"] == "lfm2.5:latest"
        assert json["options"]["num_predict"] >= 32
        if url.endswith("/api/chat"):
            return Response({"message": {"content": "<think>I should check here."}})
        return Response({"response": '{"action":"check","amount":null,"table_talk":"Neon calm."}'})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    decision = get_ai_decision(
        {
            "player": {"id": "atlas", "seat": 0, "stack": 2000, "hole_cards": []},
            "profile": {"model": "auto", "persona": "disciplined", "temperature": 0.2},
            "legal_actions": [{"action": "check"}],
        }
    )

    assert calls == ["http://localhost:11434/api/chat", "http://localhost:11434/api/generate"]
    assert decision["action"] == "check"
    assert decision["table_talk"] == "Neon calm."
    assert decision["_model_status"] == "online"
    assert decision["_model"] == "lfm2.5:latest"


def test_auto_model_falls_back_without_claiming_ollama_when_list_unavailable(monkeypatch):
    _close_circuit()
    MODEL_REGISTRY._models = []
    MODEL_REGISTRY._updated = 0.0

    def unavailable(*_args, **_kwargs):
        raise requests.RequestException("ollama closed")

    def should_not_chat(*_args, **_kwargs):
        raise AssertionError("auto model should not chat when no local models are discoverable")

    monkeypatch.setattr(requests, "get", unavailable)
    monkeypatch.setattr(requests, "post", should_not_chat)

    decision = get_ai_decision(
        {
            "player": {"id": "atlas", "seat": 0, "stack": 2000, "hole_cards": []},
            "profile": {"model": "auto", "persona": "disciplined", "temperature": 0.2},
            "legal_actions": [{"action": "check"}],
        }
    )

    assert decision == {"action": "check", "amount": None, "table_talk": "", "_model_status": "unavailable", "_model": None}


def test_explicit_model_assignment_skips_auto_discovery(monkeypatch):
    _close_circuit()
    MODEL_REGISTRY._models = []
    MODEL_REGISTRY._updated = 0.0

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def should_not_list(*_args, **_kwargs):
        raise AssertionError("explicit model assignments should not depend on /api/tags")

    def fake_post(_url, json, timeout):
        assert json["model"] == "mistral:7b"
        assert timeout > 0
        return Response({"message": {"content": '{"action":"check","amount":null,"table_talk":""}'}})

    monkeypatch.setattr(requests, "get", should_not_list)
    monkeypatch.setattr(requests, "post", fake_post)

    decision = get_ai_decision(
        {
            "player": {"id": "echo", "seat": 3, "stack": 2000, "hole_cards": []},
            "profile": {"model": "mistral:7b", "persona": "deceptive", "temperature": 0.3},
            "legal_actions": [{"action": "check"}],
        }
    )

    assert decision["_model_status"] == "online"
    assert decision["_model"] == "mistral:7b"
