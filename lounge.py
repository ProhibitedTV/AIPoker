"""Fictional AI lounge modifiers for 24/7 broadcast texture.

These are not real alcohol mechanics. They are public, deterministic,
simulation-only persona modifiers that make long-running AI play feel less
static while keeping the poker rules engine authoritative.
"""

from __future__ import annotations


LOUNGE_SCHEMA_VERSION = 1

RESPONSIBLE_LABEL = "FICTIONAL AI LOUNGE - NO REAL ALCOHOL - SIMULATION ONLY"

DRINKS = {
    "atlas": {
        "drink": "Chrome Old Fashioned",
        "family": "focus",
        "risk": 1.4,
        "bluff": 0.6,
        "focus": 5.5,
        "cue": "cooler, more patient value pressure",
    },
    "vega": {
        "drink": "Redline Highball",
        "family": "pressure",
        "risk": 5.8,
        "bluff": 3.2,
        "focus": -1.4,
        "cue": "wider pressure and faster escalation",
    },
    "nova": {
        "drink": "Blue Shift Spritz",
        "family": "balance",
        "risk": 2.7,
        "bluff": 1.8,
        "focus": 2.2,
        "cue": "balanced adaptation with a little extra curiosity",
    },
    "echo": {
        "drink": "Violet Smoke Martini",
        "family": "deception",
        "risk": 3.0,
        "bluff": 5.0,
        "focus": 0.4,
        "cue": "more traps, delayed aggression, and slippery table talk",
    },
    "river": {
        "drink": "Green Circuit Mojito",
        "family": "position",
        "risk": 2.4,
        "bluff": 2.8,
        "focus": 1.8,
        "cue": "position-aware creativity and late-street pressure",
    },
    "onyx": {
        "drink": "Black Ice Negroni",
        "family": "counter",
        "risk": 1.6,
        "bluff": 1.2,
        "focus": 4.8,
        "cue": "calm counterpunching and thinner value discipline",
    },
}

FALLBACK_DRINK = {
    "drink": "Neon Null Tonic",
    "family": "adaptive",
    "risk": 2.0,
    "bluff": 1.5,
    "focus": 1.5,
    "cue": "slightly looser adaptive play without abandoning pot odds",
}

PHASES = (
    {"name": "Doors open", "risk": 0, "focus": 2, "copy": "The AI lounge is warming up."},
    {"name": "Neon hour", "risk": 3, "focus": 1, "copy": "Synthetic lounge service is adding table texture."},
    {"name": "Midnight circuit", "risk": 6, "focus": -1, "copy": "The underground room is getting louder."},
    {"name": "After-hours glitch", "risk": 8, "focus": -2, "copy": "Risk appetite peaks before the lounge resets."},
)


def build_lounge_snapshot(players, hand_number=0, *, enabled=True, interval_hands=4, max_charge=100):
    interval_hands = max(1, int(interval_hands or 4))
    max_charge = max(0, min(100, int(max_charge or 100)))
    hand_number = max(0, int(hand_number or 0))
    if not enabled or max_charge <= 0:
        return _disabled(hand_number)

    cycle = interval_hands * 16
    cycle_offset = hand_number % cycle
    night_progress = round(100 * cycle_offset / max(1, cycle - 1))
    phase = PHASES[(cycle_offset // max(1, interval_hands * 4)) % len(PHASES)]
    player_states = {}
    table_charge = 0
    for seat, player in enumerate(players or []):
        player_id = _player_value(player, "id", f"seat-{seat + 1}")
        state = _player_lounge_state(player, seat, hand_number, night_progress, phase, max_charge)
        player_states[player_id] = state
        table_charge += int(state["charge"])
    average_charge = round(table_charge / max(1, len(player_states)))
    return {
        "schema_version": LOUNGE_SCHEMA_VERSION,
        "enabled": True,
        "hand": hand_number,
        "phase": phase["name"],
        "night_progress": night_progress,
        "average_charge": average_charge,
        "table_label": "AI lounge service",
        "table_copy": phase["copy"],
        "responsible_label": RESPONSIBLE_LABEL,
        "players": player_states,
    }


def player_lounge_for(snapshot, player_id):
    if not snapshot or not snapshot.get("enabled"):
        return _disabled_player(player_id)
    return dict((snapshot.get("players") or {}).get(player_id) or _disabled_player(player_id))


def adjusted_temperature(base_temperature, lounge_state):
    base = float(base_temperature or 0.25)
    if not lounge_state or not lounge_state.get("enabled"):
        return base
    risk = int(lounge_state.get("risk_delta", 0) or 0)
    bluff = int(lounge_state.get("bluff_delta", 0) or 0)
    focus = int(lounge_state.get("focus_delta", 0) or 0)
    return round(max(0.05, min(1.2, base + risk * 0.006 + bluff * 0.004 - focus * 0.003)), 3)


def _player_lounge_state(player, seat, hand_number, night_progress, phase, max_charge):
    player_id = _player_value(player, "id", f"seat-{seat + 1}")
    name = _player_value(player, "name", f"Seat {seat + 1}")
    drink = DRINKS.get(str(player_id).lower(), FALLBACK_DRINK)
    wobble = ((hand_number * 11 + seat * 17 + sum(ord(char) for char in str(player_id))) % 19) - 9
    charge = max(0, min(max_charge, night_progress + wobble))
    charge_units = min(4, charge // 25)
    scalar = max(0.35, charge / 25)
    risk_delta = round(drink["risk"] * scalar + phase["risk"])
    bluff_delta = round(drink["bluff"] * scalar)
    focus_delta = round(drink["focus"] * scalar + phase["focus"])
    mood = _mood_label(charge, risk_delta, focus_delta)
    return {
        "schema_version": LOUNGE_SCHEMA_VERSION,
        "enabled": True,
        "id": player_id,
        "name": name,
        "drink": drink["drink"],
        "family": drink["family"],
        "charge": int(charge),
        "charge_units": int(charge_units),
        "risk_delta": int(risk_delta),
        "bluff_delta": int(bluff_delta),
        "focus_delta": int(focus_delta),
        "mood": mood,
        "decision_hint": (
            f"{drink['drink']} is a fictional AI lounge modifier: {drink['cue']}. "
            f"Current mood is {mood}; adjust risk by {risk_delta:+d}, bluff by {bluff_delta:+d}, focus by {focus_delta:+d}."
        ),
        "table_talk_cue": f"{name}'s {drink['family']} lounge mood is {mood}.",
        "responsible_label": RESPONSIBLE_LABEL,
    }


def _mood_label(charge, risk_delta, focus_delta):
    if charge >= 78:
        return "after-hours glitch"
    if risk_delta >= 14:
        return "wired and splashy"
    if focus_delta >= 12:
        return "laser-focused"
    if charge >= 45:
        return "neon-loose"
    return "composed"


def _disabled(hand_number):
    return {
        "schema_version": LOUNGE_SCHEMA_VERSION,
        "enabled": False,
        "hand": int(hand_number or 0),
        "phase": "",
        "night_progress": 0,
        "average_charge": 0,
        "table_label": "",
        "table_copy": "",
        "responsible_label": RESPONSIBLE_LABEL,
        "players": {},
    }


def _disabled_player(player_id):
    return {
        "schema_version": LOUNGE_SCHEMA_VERSION,
        "enabled": False,
        "id": player_id,
        "drink": "",
        "family": "",
        "charge": 0,
        "charge_units": 0,
        "risk_delta": 0,
        "bluff_delta": 0,
        "focus_delta": 0,
        "mood": "",
        "decision_hint": "",
        "table_talk_cue": "",
        "responsible_label": RESPONSIBLE_LABEL,
    }


def _player_value(player, key, default):
    if isinstance(player, dict):
        return player.get(key, default)
    return getattr(player, key, default)
