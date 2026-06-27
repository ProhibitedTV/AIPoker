"""Long-running broadcast variety rotation for the 24/7 poker table.

The rotation deliberately stays inside No-Limit Texas Hold'em. It changes
presentation, table tempo, cash stakes/antes, and tournament cadence at safe
hand or tournament boundaries so the stream does not feel like one endless
identical block while the rules engine remains auditable.
"""

from __future__ import annotations


def default_variety_segments():
    """Return safe, deterministic default blocks for unattended streaming."""

    return [
        {
            "id": "championship_sng",
            "title": "Championship Sit & Go",
            "mode": "tournament",
            "duration_hands": 24,
            "style": "balanced championship poker",
            "tempo": "standard",
            "table_skin": "championship",
            "accent": "#e6b94a",
            "viewer_explainer": "A classic four-seat sit-and-go: rising blinds, no rebuys, trophy finish.",
            "strategy_hint": "Use balanced stack-aware tournament poker. Preserve fold equity and avoid careless short-stack calls.",
            "hands_per_level": 8,
        },
        {
            "id": "turbo_sng",
            "title": "Turbo Pressure Sit & Go",
            "mode": "tournament",
            "duration_hands": 18,
            "style": "fast blind pressure",
            "tempo": "turbo",
            "table_skin": "turbo",
            "accent": "#ff7b4a",
            "viewer_explainer": "A shorter-blind sit-and-go where stacks get pressured quickly.",
            "strategy_hint": "Blinds rise quickly in this segment. Favor position, fold equity, and decisive pressure with playable ranges.",
            "hands_per_level": 4,
        },
        {
            "id": "deep_stack_cash",
            "title": "Deep Stack Cash Orbit",
            "mode": "cash",
            "duration_hands": 24,
            "style": "deep-stack cash poker",
            "tempo": "patient",
            "table_skin": "deep",
            "accent": "#61b7ff",
            "viewer_explainer": "A deeper cash-game block that leaves more room for postflop decisions.",
            "strategy_hint": "Stacks are deeper relative to the blinds. Value position, implied odds, and multi-street planning.",
            "small_blind": 10,
            "big_blind": 20,
            "ante": 0,
            "starting_chips": 3000,
        },
        {
            "id": "ante_splash_cash",
            "title": "Ante Splash Cash",
            "mode": "cash",
            "duration_hands": 18,
            "style": "ante-driven action cash",
            "tempo": "splash",
            "table_skin": "splash",
            "accent": "#5ed39a",
            "viewer_explainer": "Everyone antes, so more hands begin with something worth fighting for.",
            "strategy_hint": "Antes improve steal prices and pot odds. Defend wider in good spots, but keep raise sizes legal and stack-aware.",
            "small_blind": 10,
            "big_blind": 20,
            "ante": 5,
            "starting_chips": 2500,
        },
        {
            "id": "high_roller_cash",
            "title": "High Roller Cash Spotlight",
            "mode": "cash",
            "duration_hands": 16,
            "style": "bigger-stakes pressure",
            "tempo": "high pressure",
            "table_skin": "high_roller",
            "accent": "#a98aff",
            "viewer_explainer": "The stakes step up for a short block, making every bet feel heavier.",
            "strategy_hint": "Bigger blinds increase stack pressure. Avoid speculative calls without position or clear price.",
            "small_blind": 25,
            "big_blind": 50,
            "ante": 0,
            "starting_chips": 3000,
        },
    ]


def normalize_variety_segments(segments=None, fallback_interval=24, base_small=10, base_big=20, base_stack=2000):
    """Normalize user-provided rotation blocks without trusting their shape."""

    raw_segments = list(segments or default_variety_segments())
    if not raw_segments:
        raw_segments = default_variety_segments()
    normalized = []
    used_ids = set()
    for index, raw in enumerate(raw_segments):
        raw = raw if isinstance(raw, dict) else {}
        mode = str(raw.get("mode", "tournament")).lower()
        mode = "tournament" if mode in {"tournament", "sit_and_go", "sng"} else "cash"
        duration = _positive_int(raw.get("duration_hands", fallback_interval), fallback_interval)
        small = _positive_int(raw.get("small_blind", base_small), base_small)
        big = _positive_int(raw.get("big_blind", base_big), base_big)
        if big <= small:
            big = max(small + 1, base_big)
        segment_id = _slug(raw.get("id") or raw.get("title") or f"segment_{index + 1}")
        while segment_id in used_ids:
            segment_id = f"{segment_id}_{index + 1}"
        used_ids.add(segment_id)
        normalized.append(
            {
                "id": segment_id,
                "title": str(raw.get("title") or segment_id.replace("_", " ").title())[:80],
                "mode": mode,
                "duration_hands": duration,
                "style": str(raw.get("style") or ("tournament pressure" if mode == "tournament" else "cash-game flow"))[:120],
                "tempo": str(raw.get("tempo") or "standard")[:40],
                "table_skin": _slug(raw.get("table_skin") or raw.get("skin") or segment_id)[:40],
                "accent": _hex_color(raw.get("accent"), "#e6b94a"),
                "viewer_explainer": str(raw.get("viewer_explainer") or raw.get("explainer") or "The stream has rotated to a fresh table segment.")[:220],
                "strategy_hint": str(raw.get("strategy_hint") or "Play legal no-limit hold'em with the current stacks, blinds, and public action.")[:260],
                "small_blind": small,
                "big_blind": big,
                "ante": max(0, int(raw.get("ante", 0) or 0)),
                "starting_chips": _positive_int(raw.get("starting_chips", base_stack), base_stack),
                "hands_per_level": _positive_int(raw.get("hands_per_level", 8), 8),
                "levels": raw.get("tournament_levels") or raw.get("levels"),
            }
        )
    return normalized


def segment_for_completed_hand(segments, completed_hands):
    """Return ``(index, segment, hand_offset, hands_remaining)`` for a cycle."""

    segments = list(segments or [])
    if not segments:
        return 0, None, 0, 0
    cycle = sum(max(1, int(segment.get("duration_hands", 1))) for segment in segments)
    position = int(completed_hands or 0) % max(1, cycle)
    cursor = 0
    for index, segment in enumerate(segments):
        duration = max(1, int(segment.get("duration_hands", 1)))
        if cursor <= position < cursor + duration:
            return index, segment, position - cursor, duration - (position - cursor)
        cursor += duration
    final = segments[-1]
    return len(segments) - 1, final, 0, max(1, int(final.get("duration_hands", 1)))


def segment_public_snapshot(segment, enabled=True, index=0, offset=0, hands_remaining=0, delayed=False):
    segment = segment or {}
    return {
        "schema_version": 1,
        "enabled": bool(enabled),
        "segment_index": int(index or 0),
        "segment_id": segment.get("id", "standard"),
        "title": segment.get("title", "Standard Table"),
        "mode": segment.get("mode", "tournament"),
        "style": segment.get("style", "standard no-limit hold'em"),
        "tempo": segment.get("tempo", "standard"),
        "table_skin": segment.get("table_skin", "championship"),
        "accent": segment.get("accent", "#e6b94a"),
        "viewer_explainer": segment.get("viewer_explainer", "The table is in a standard broadcast segment."),
        "strategy_hint": segment.get("strategy_hint", "Play legal no-limit hold'em with the current public state."),
        "duration_hands": int(segment.get("duration_hands", 0) or 0),
        "hand_offset": int(offset or 0),
        "hands_remaining": int(hands_remaining or 0),
        "rotation_delayed": bool(delayed),
    }


def _positive_int(value, fallback):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = int(fallback)
    return max(1, value)


def _slug(value):
    clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "segment"))
    clean = "_".join(part for part in clean.split("_") if part)
    return clean or "segment"


def _hex_color(value, fallback):
    value = str(value or "").strip()
    if len(value) == 7 and value.startswith("#"):
        try:
            int(value[1:], 16)
            return value
        except ValueError:
            return fallback
    return fallback
