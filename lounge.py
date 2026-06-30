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

DRINK_DETAILS = {
    "focus": {
        "neon_color": "#74f7ff",
        "flavor_notes": "smoked citrus, chrome bitters",
        "garnish": "blue-lit orange peel",
        "glassware": "lowball prism",
        "visual_tell": "visor glow steadies between bets",
    },
    "pressure": {
        "neon_color": "#ff4f87",
        "flavor_notes": "pepper berry, electric ginger",
        "garnish": "red diode cherry",
        "glassware": "tall reactor glass",
        "visual_tell": "chip hand speeds up when pots swell",
    },
    "balance": {
        "neon_color": "#62ffb7",
        "flavor_notes": "mint, lime, blue ion fizz",
        "garnish": "floating holo leaf",
        "glassware": "stemless orb",
        "visual_tell": "bet timing stays smooth under pressure",
    },
    "deception": {
        "neon_color": "#c35cff",
        "flavor_notes": "violet smoke, black cherry",
        "garnish": "purple vapor ribbon",
        "glassware": "mirrored coupe",
        "visual_tell": "avatar smile flickers before traps",
    },
    "position": {
        "neon_color": "#52f6a8",
        "flavor_notes": "green circuit mint, ozone",
        "garnish": "microchip sugar rim",
        "glassware": "angled highball",
        "visual_tell": "seat light brightens on late position",
    },
    "counter": {
        "neon_color": "#8db7ff",
        "flavor_notes": "cold espresso, black ice",
        "garnish": "frosted neon shard",
        "glassware": "black crystal tumbler",
        "visual_tell": "pulse slows after opponent aggression",
    },
    "adaptive": {
        "neon_color": "#f6df72",
        "flavor_notes": "zero-proof tonic, citrus static",
        "garnish": "gold circuit twist",
        "glassware": "clear cube glass",
        "visual_tell": "signal recalibrates each street",
    },
}

VENUES = (
    {
        "name": "Rainline Room",
        "district": "Simulation District",
        "booth": "sub-basement rail",
        "lighting": "cyan rain and magenta glass",
        "weather": "synthetic rain",
    },
    {
        "name": "Neon Mezzanine",
        "district": "Stack Alley",
        "booth": "upper-ring booth",
        "lighting": "violet skyline wash",
        "weather": "low fog",
    },
    {
        "name": "Afterhours Grid",
        "district": "Chrome Market",
        "booth": "back-room holo table",
        "lighting": "redline strobes",
        "weather": "electric haze",
    },
    {
        "name": "Black Circuit Lounge",
        "district": "Dealer's Row",
        "booth": "private server cage",
        "lighting": "gold chip LEDs",
        "weather": "static drizzle",
    },
)

SOUNDTRACKS = (
    "slow synth bass under chip clicks",
    "rainy alley pads with distant crowd noise",
    "high-voltage pulse during big pots",
    "low neon lounge bed between hands",
)

SERVICE_BOTS = (
    "Mira-7",
    "Chrome Valet",
    "Juno Static",
    "The Neon Waiter",
)

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
    venue = VENUES[(cycle_offset // max(1, interval_hands * 2)) % len(VENUES)]
    service_round = cycle_offset // interval_hands + 1
    player_states = {}
    table_charge = 0
    total_risk = 0
    total_bluff = 0
    total_focus = 0
    for seat, player in enumerate(players or []):
        player_id = _player_value(player, "id", f"seat-{seat + 1}")
        state = _player_lounge_state(player, seat, hand_number, night_progress, phase, max_charge)
        player_states[player_id] = state
        table_charge += int(state["charge"])
        total_risk += int(state["risk_delta"])
        total_bluff += int(state["bluff_delta"])
        total_focus += int(state["focus_delta"])
    average_charge = round(table_charge / max(1, len(player_states)))
    player_count = max(1, len(player_states))
    table_effects = {
        "risk": round(total_risk / player_count),
        "bluff": round(total_bluff / player_count),
        "focus": round(total_focus / player_count),
    }
    pressure_index = max(0, min(100, average_charge + table_effects["risk"] * 2 + table_effects["bluff"] - table_effects["focus"]))
    service_bot = SERVICE_BOTS[(service_round + len(player_states)) % len(SERVICE_BOTS)]
    table_mood = _table_mood(pressure_index, phase["name"])
    rivalry = _rivalry_snapshot(player_states)
    scene_name = f"{venue['name']} // {venue['district']}"
    atmosphere_line = (
        f"{service_bot} sweeps {venue['lighting']} through the {venue['booth']} "
        f"while the table mood reads {table_mood.lower()}."
    )
    return {
        "schema_version": LOUNGE_SCHEMA_VERSION,
        "enabled": True,
        "hand": hand_number,
        "phase": phase["name"],
        "venue": venue,
        "scene_name": scene_name,
        "venue_zone": venue["booth"],
        "service_bot": service_bot,
        "table_mood": table_mood,
        "rivalry": rivalry,
        "atmosphere_line": atmosphere_line,
        "service_round": service_round,
        "night_progress": night_progress,
        "average_charge": average_charge,
        "pressure_index": pressure_index,
        "table_effects": table_effects,
        "table_label": "AI lounge service",
        "table_copy": phase["copy"],
        "broadcast_cue": f"{scene_name} - {phase['name']}: {phase['copy']}",
        "soundtrack": SOUNDTRACKS[(cycle_offset // max(1, interval_hands)) % len(SOUNDTRACKS)],
        "safety_copy": "Synthetic AI lounge service only; no real alcohol.",
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
    details = DRINK_DETAILS.get(drink["family"], DRINK_DETAILS["adaptive"])
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
        "drink_code": f"{drink['family'][:3].upper()}-{(sum(ord(char) for char in str(player_id)) + hand_number + seat) % 100:02d}",
        "family": drink["family"],
        "neon_color": details["neon_color"],
        "flavor_notes": details["flavor_notes"],
        "garnish": details["garnish"],
        "glassware": details["glassware"],
        "visual_tell": details["visual_tell"],
        "charge": int(charge),
        "charge_units": int(charge_units),
        "service_level": _service_level(charge),
        "risk_delta": int(risk_delta),
        "bluff_delta": int(bluff_delta),
        "focus_delta": int(focus_delta),
        "current_effects": {
            "risk": int(risk_delta),
            "bluff": int(bluff_delta),
            "focus": int(focus_delta),
        },
        "mood": mood,
        "decision_hint": (
            f"{drink['drink']} is a fictional AI lounge modifier: {drink['cue']}. "
            f"Current mood is {mood}; visual tell is {details['visual_tell']}. "
            f"Adjust risk by {risk_delta:+d}, bluff by {bluff_delta:+d}, focus by {focus_delta:+d}."
        ),
        "table_talk_cue": f"{name}'s {drink['family']} lounge mood is {mood}.",
        "broadcast_line": f"{name}: {drink['drink']} / {mood} / {details['visual_tell']}",
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


def _service_level(charge):
    if charge >= 80:
        return "glitch service"
    if charge >= 60:
        return "overclocked"
    if charge >= 35:
        return "neon warm"
    if charge > 0:
        return "low glow"
    return "idle"


def _table_mood(pressure_index, phase_name):
    if pressure_index >= 85:
        return "Redline room"
    if pressure_index >= 65:
        return "High-voltage lounge"
    if "midnight" in str(phase_name).lower():
        return "Midnight signal"
    if pressure_index >= 40:
        return "Neon social"
    return "Low-glow warmup"


def _rivalry_snapshot(player_states):
    states = sorted(
        player_states.values(),
        key=lambda state: (int(state.get("charge", 0)), int(state.get("risk_delta", 0))),
        reverse=True,
    )
    if len(states) < 2:
        return {"active": False, "headline": "", "heat": 0, "left": "", "right": "", "angle": ""}
    left, right = states[0], states[1]
    heat = max(0, min(100, round((int(left["charge"]) + int(right["charge"])) / 2)))
    return {
        "active": heat >= 30,
        "headline": f"{left['name']} vs {right['name']}",
        "heat": heat,
        "left": left["id"],
        "right": right["id"],
        "angle": f"{left['family']} energy into {right['family']} resistance",
    }


def _disabled(hand_number):
    return {
        "schema_version": LOUNGE_SCHEMA_VERSION,
        "enabled": False,
        "hand": int(hand_number or 0),
        "phase": "",
        "venue": {},
        "scene_name": "",
        "venue_zone": "",
        "service_bot": "",
        "table_mood": "",
        "rivalry": {"active": False, "headline": "", "heat": 0, "left": "", "right": "", "angle": ""},
        "atmosphere_line": "",
        "service_round": 0,
        "night_progress": 0,
        "average_charge": 0,
        "pressure_index": 0,
        "table_effects": {"risk": 0, "bluff": 0, "focus": 0},
        "table_label": "",
        "table_copy": "",
        "broadcast_cue": "",
        "soundtrack": "",
        "safety_copy": "Synthetic AI lounge service only; no real alcohol.",
        "responsible_label": RESPONSIBLE_LABEL,
        "players": {},
    }


def _disabled_player(player_id):
    return {
        "schema_version": LOUNGE_SCHEMA_VERSION,
        "enabled": False,
        "id": player_id,
        "drink": "",
        "drink_code": "",
        "family": "",
        "neon_color": "",
        "flavor_notes": "",
        "garnish": "",
        "glassware": "",
        "visual_tell": "",
        "charge": 0,
        "charge_units": 0,
        "service_level": "",
        "risk_delta": 0,
        "bluff_delta": 0,
        "focus_delta": 0,
        "current_effects": {"risk": 0, "bluff": 0, "focus": 0},
        "mood": "",
        "decision_hint": "",
        "table_talk_cue": "",
        "broadcast_line": "",
        "responsible_label": RESPONSIBLE_LABEL,
    }


def _player_value(player, key, default):
    if isinstance(player, dict):
        return player.get(key, default)
    return getattr(player, key, default)
