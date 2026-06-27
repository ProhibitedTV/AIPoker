"""Structured, privacy-preserving Ollama poker decisions."""

import json
import os
import re
from threading import RLock
import time


OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/api/chat")
OLLAMA_LIST_URL = os.environ.get("OLLAMA_LIST_URL", "http://localhost:11434/api/tags")
OLLAMA_TIMEOUT_SECONDS = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "30"))


class ModelRegistry:
    def __init__(self, ttl_seconds=60):
        self.ttl_seconds = ttl_seconds
        self._models = []
        self._updated = 0.0
        self._lock = RLock()

    def models(self, force=False):
        with self._lock:
            if not force and self._updated and time.monotonic() - self._updated < self.ttl_seconds:
                return list(self._models)
        import requests

        try:
            response = requests.get(OLLAMA_LIST_URL, timeout=min(5, OLLAMA_TIMEOUT_SECONDS))
            response.raise_for_status()
            models = [str(model["name"]) for model in response.json().get("models", []) if model.get("name")]
        except (requests.RequestException, ValueError, KeyError):
            models = []
        with self._lock:
            self._models = models
            self._updated = time.monotonic()
            return list(models)

    def resolve(self, requested="auto", seat=0):
        models = self.models()
        if requested and requested != "auto":
            return requested
        preferred = [
            model for model in models
            if any(token in model.lower() for token in ("qwen", "llama", "gemma", "mistral", "command-r"))
        ]
        candidates = preferred or models
        return candidates[seat % len(candidates)] if candidates else "llama3:latest"


MODEL_REGISTRY = ModelRegistry()
_CIRCUIT_LOCK = RLock()
_CIRCUIT_OPEN_UNTIL = 0.0


def get_available_models(force=False):
    return MODEL_REGISTRY.models(force=force)


def get_poker_compatible_model():
    return MODEL_REGISTRY.resolve("auto", 0)


def sanitize_decision(decision):
    """Compatibility parser; structured calls use strict JSON validation."""
    match = re.search(r"\b(fold|check|call|bet|raise|all[_ -]?in)\b", str(decision).lower())
    if not match:
        return "check"
    return match.group(1).replace(" ", "_").replace("-", "_")


def get_ai_decision(context, community_cards=None, max_retries=2):
    """Return a validated ``{action, amount, table_talk}`` decision.

    The modern input is the acting player's private context. The legacy
    ``(hand, community_cards)`` form remains accepted for third-party callers.
    """
    if not isinstance(context, dict):
        context = _legacy_context(context, community_cards or [])
    legal = {entry["action"]: entry for entry in context.get("legal_actions", [])}
    if not legal:
        return {"action": "fold", "amount": None, "table_talk": "", "_model_status": "no-legal-actions"}

    profile = context.get("profile", {})
    seat = int(context.get("player", {}).get("seat", 0))
    model = MODEL_REGISTRY.resolve(profile.get("model", "auto"), seat)
    with _CIRCUIT_LOCK:
        circuit_open = time.monotonic() < _CIRCUIT_OPEN_UNTIL
    if circuit_open:
        fallback = _fallback_decision(legal, int(context.get("player", {}).get("stack", 0)))
        fallback.update({"_model_status": "circuit-open", "_model": model})
        return fallback
    safe_context = _json_safe_context(context)
    system = (
        "You are a No-Limit Texas Hold'em player. Play the persona: "
        f"{profile.get('persona', 'balanced')}. Use only the supplied information; never assume hidden cards. "
        "Choose exactly one supplied legal action. For bet or raise, amount is the final total street target. "
        "Return strict JSON only: {\"action\":string,\"amount\":integer|null,\"table_talk\":string}. "
        "Table talk is optional, in character, and at most 12 words."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(safe_context, separators=(",", ":"))},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": max(0.0, min(1.5, float(profile.get("temperature", 0.25))))},
    }

    import requests

    for attempt in range(max(1, int(max_retries))):
        try:
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
            response.raise_for_status()
            raw = response.json().get("message", {}).get("content", "")
            decision = _parse_json_object(raw)
            validated = _validate_decision(decision, legal)
            if validated:
                _close_circuit()
                validated["_model_status"] = "online"
                validated["_model"] = model
                return validated
            messages.append({"role": "assistant", "content": str(raw)[:500]})
            messages.append(
                {
                    "role": "user",
                    "content": "That response was invalid. Return one legal action with a valid target as strict JSON only.",
                }
            )
        except requests.RequestException:
            _open_circuit()
            break
        except (ValueError, TypeError, json.JSONDecodeError):
            break
    fallback = _fallback_decision(legal, int(context.get("player", {}).get("stack", 0)))
    fallback["_model_status"] = "fallback"
    fallback["_model"] = model
    return fallback


def _open_circuit(seconds=30):
    global _CIRCUIT_OPEN_UNTIL
    with _CIRCUIT_LOCK:
        _CIRCUIT_OPEN_UNTIL = max(_CIRCUIT_OPEN_UNTIL, time.monotonic() + seconds)


def _close_circuit():
    global _CIRCUIT_OPEN_UNTIL
    with _CIRCUIT_LOCK:
        _CIRCUIT_OPEN_UNTIL = 0.0


def _json_safe_context(context):
    """Remove Python-only fields and explicitly whitelist prompt information."""
    public_players = []
    for player in context.get("players", []):
        public_players.append(
            {
                key: player.get(key)
                for key in (
                    "id", "name", "seat", "stack", "status", "street_commitment",
                    "hand_commitment", "last_action",
                )
                if key in player
            }
        )
    return {
        "player": context.get("player", {}),
        "street": context.get("street"),
        "community_cards": context.get("community_cards", []),
        "pot": context.get("pot", 0),
        "blinds": context.get("blinds", {}),
        "position": context.get("position"),
        "to_call": context.get("to_call", 0),
        "pot_odds_percent": context.get("pot_odds_percent", 0),
        "minimum_full_raise": context.get("minimum_full_raise", 0),
        "legal_actions": context.get("legal_actions", []),
        "players": public_players,
        "action_history": context.get("action_history", []),
        "table_program": context.get("table_program", {}),
        "strategy_hint": context.get("strategy_hint", {}),
    }


def _parse_json_object(raw):
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _validate_decision(decision, legal):
    if not isinstance(decision, dict):
        return None
    action = str(decision.get("action", "")).lower().replace("-", "_").replace(" ", "_")
    if action == "allin":
        action = "all_in"
    if action not in legal:
        return None
    amount = decision.get("amount")
    contract = legal[action]
    if action in {"bet", "raise"}:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            return None
        amount = int(amount)
        if not contract["min_target"] <= amount <= contract["max_target"]:
            return None
    else:
        amount = contract.get("target")
    talk = str(decision.get("table_talk", "")).replace("\n", " ").strip()[:100]
    return {"action": action, "amount": amount, "table_talk": talk}


def _fallback_decision(legal, stack):
    if "check" in legal:
        action = "check"
    elif "call" in legal and legal["call"].get("amount", stack) <= max(1, stack // 10):
        action = "call"
    else:
        action = "fold"
    return {"action": action, "amount": legal[action].get("target"), "table_talk": ""}


def _legacy_context(hand, community_cards):
    return {
        "player": {
            "id": "legacy",
            "name": "AI Player",
            "seat": 0,
            "stack": 1000,
            "hole_cards": [{"rank": card[0], "suit": card[1]} for card in hand],
        },
        "profile": {"persona": "balanced", "model": "auto", "temperature": 0.25},
        "street": "unknown",
        "community_cards": [{"rank": card[0], "suit": card[1]} for card in community_cards],
        "pot": 0,
        "legal_actions": [{"action": "fold"}, {"action": "check"}],
        "players": [],
        "action_history": [],
    }
