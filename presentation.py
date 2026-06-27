"""Broadcast-director presentation state derived from public table state."""

from __future__ import annotations

import re


PRESENTATION_SCHEMA_VERSION = 1


def build_presentation_snapshot(
    *,
    players,
    stage,
    pot,
    blinds,
    tournament=None,
    action_history=None,
    commentary=None,
    personality_arcs=None,
    program=None,
    variety=None,
    hand_number=0,
    casino_bumpers_enabled=True,
    casino_bumper_duration_ms=6500,
    casino_bumper_responsible_label=True,
    casino_bumper_frequency="selected_hands",
):
    """Return non-authoritative visual direction for the stream overlay.

    The presentation layer is intentionally derived from already-public state.
    It never changes gameplay and never adds private information beyond the
    spectator-visible seat/player fields passed in by ``state_snapshot``.
    """

    players = list(players or [])
    stage = str(stage or "Waiting")
    stage_key = stage.lower()
    pot = int(pot or 0)
    big_blind = max(1, int((blinds or {}).get("big", 1) or 1))
    tournament = tournament or {}
    action_history = list(action_history or [])
    commentary = list(commentary or [])
    personality_arcs = personality_arcs or {}
    program = program or {}
    variety = variety or {}

    actor = next((player for player in players if player.get("next_to_act")), None)
    winners = _winner_players(players)
    all_ins = [player for player in players if player.get("all_in") and not player.get("folded")]
    pot_big_blinds = pot / big_blind
    chip_leader = max(
        (player for player in players if not player.get("eliminated")),
        key=lambda player: int(player.get("chips", 0)),
        default=None,
    )

    if tournament.get("complete"):
        champion = next(
            (player for player in players if player.get("id") == tournament.get("winner")),
            None,
        )
        mode = "recap"
        headline = "Trophy ceremony"
        explainer = f"{(champion or {}).get('name', 'The champion')} has locked up this sit-and-go."
        spotlights = [champion.get("id")] if champion else []
        intensity = 92
    elif winners:
        mode = "recap"
        headline = "Hand recap"
        explainer = _latest_winner_line(commentary) or "The pot has been awarded and the table is resetting."
        spotlights = [player.get("id") for player in winners]
        intensity = 76
    elif stage_key == "showdown":
        mode = "showdown"
        headline = "Showdown desk"
        explainer = "Cards are being compared. Best five-card poker hand wins each eligible pot."
        spotlights = [player.get("id") for player in players if player.get("active") and not player.get("folded")]
        intensity = 70
    elif all_ins:
        mode = "all_in"
        headline = "All-in pressure"
        explainer = "At least one player has every chip committed. No more decisions for that stack."
        spotlights = [player.get("id") for player in all_ins]
        intensity = 88
    elif pot_big_blinds >= 20:
        mode = "big_pot"
        headline = "Monster pot brewing"
        explainer = f"The middle is already worth {pot_big_blinds:.0f} big blinds."
        spotlights = [player.get("id") for player in players if player.get("active") and not player.get("folded")]
        intensity = 78
    elif actor:
        mode = "decision"
        headline, explainer = _decision_copy(actor)
        spotlights = [actor.get("id")]
        intensity = 54
    else:
        mode = "table"
        headline = program.get("segment") or "Live table"
        explainer = program.get("detail") or "The table is preparing the next card or decision."
        spotlights = [chip_leader.get("id")] if chip_leader else []
        intensity = 28

    recap = _recap_payload(players, winners, tournament, commentary, action_history)
    bumper = _bumper_payload(
        players=players,
        winners=winners,
        tournament=tournament,
        variety=variety,
        recap=recap,
        personality_arcs=personality_arcs,
        big_blind=big_blind,
        hand_number=hand_number,
        enabled=casino_bumpers_enabled,
        duration_ms=casino_bumper_duration_ms,
        responsible_label=casino_bumper_responsible_label,
        frequency=casino_bumper_frequency,
    )
    return {
        "schema_version": PRESENTATION_SCHEMA_VERSION,
        "mode": mode,
        "spotlight_seat_ids": [item for item in spotlights if item],
        "headline": headline,
        "explainer": explainer,
        "recap": recap,
        "bumper": bumper,
        "visual_intensity": int(max(0, min(100, intensity))),
        "hand": int(hand_number or 0),
        "chip_leader": chip_leader.get("id") if chip_leader else None,
        "profile_signals": _profile_signals(players, personality_arcs),
    }


def _decision_copy(actor):
    legal = list(actor.get("legal_actions") or [])
    call = next((entry for entry in legal if entry.get("action") == "call"), None)
    can_raise = any(entry.get("action") in {"bet", "raise"} for entry in legal)
    name = actor.get("name", "The player")
    if call:
        amount = int(call.get("amount", 0) or 0)
        if can_raise:
            return f"{name} faces a call", f"It costs {amount:,} chips to stay in. They can call, raise, or fold."
        return f"{name} faces a call", f"It costs {amount:,} chips to stay in. They can call or fold."
    if can_raise:
        return f"{name} controls the action", "Checking is free; betting makes opponents pay to continue."
    return f"{name} can check", "Checking costs nothing and passes the decision to the next player."


def _winner_players(players):
    return [
        player
        for player in players
        if str(player.get("action", "")).startswith("Won")
    ]


def _latest_winner_line(commentary):
    for line in reversed(commentary):
        if re.search(r"\b(wins?|share|awarded)\b", str(line), re.IGNORECASE):
            return str(line)
    return ""


def _recap_payload(players, winners, tournament, commentary, action_history):
    amount = sum(_won_amount(player.get("action")) for player in winners)
    hand = ""
    if winners:
        hand = winners[0].get("hand_label") or "Winning hand"
    detail = _latest_winner_line(commentary)
    standings = sorted(
        [
            {
                "id": player.get("id"),
                "name": player.get("name"),
                "chips": int(player.get("chips", 0)),
                "delta": int(player.get("chips", 0)) - int(player.get("hand_commitment", 0)),
            }
            for player in players
            if not player.get("eliminated")
        ],
        key=lambda row: row["chips"],
        reverse=True,
    )[:3]
    next_label = ""
    if tournament:
        if tournament.get("complete"):
            next_label = "Next sit-and-go starts after the trophy beat."
        else:
            next_label = f"Level {tournament.get('level', 1)} · {tournament.get('hands_remaining', 0)} hand(s) until blinds move."
    elif action_history:
        next_label = "Cash table continues at fixed stakes."
    return {
        "visible": bool(winners or tournament.get("complete")),
        "winners": [{"id": player.get("id"), "name": player.get("name")} for player in winners],
        "hand": hand,
        "amount": amount,
        "detail": detail,
        "next": next_label,
        "standings": standings,
    }


def _bumper_payload(
    *,
    players,
    winners,
    tournament,
    variety,
    recap,
    personality_arcs,
    big_blind,
    hand_number,
    enabled,
    duration_ms,
    responsible_label,
    frequency,
):
    duration_ms = max(4000, min(8000, int(duration_ms or 6500)))
    disabled = {
        "enabled": False,
        "kind": "",
        "title": "",
        "subtitle": "",
        "duration_ms": duration_ms,
        "seed": int(hand_number or 0),
        "stats": {},
        "responsible_label": bool(responsible_label),
    }
    if not enabled or str(frequency or "selected_hands").lower() in {"off", "disabled", "never"}:
        return disabled
    if not recap.get("visible"):
        return disabled

    amount = int(recap.get("amount", 0) or 0)
    split = len(winners) > 1
    winner = winners[0] if winners else None
    leader = max(
        (player for player in players if not player.get("eliminated")),
        key=lambda player: int(player.get("chips", 0)),
        default=None,
    )
    winner_arc = personality_arcs.get((winner or {}).get("id"), {}) if winner else {}
    next_format = bool(tournament.get("complete")) or (
        bool(variety.get("enabled")) and int(variety.get("hands_remaining", 99) or 99) <= 1
    )
    big_pot = amount >= max(1, big_blind) * 20
    hot_streak = winner and int(winner_arc.get("confidence", 0) or 0) >= 70
    selected = next_format or split or big_pot or hot_streak or int(hand_number or 0) % 3 == 0 or int(hand_number or 0) % 5 == 0
    if str(frequency or "selected_hands").lower() == "selected_hands" and not selected:
        return disabled

    if next_format:
        kind = "next_format"
        title = "Next table block"
        subtitle = variety.get("title") or "The broadcast is rotating to a fresh segment."
    elif split:
        kind = "pot_reels"
        title = "Split pot reel"
        subtitle = f"{' + '.join(player.get('name', 'Player') for player in winners)} share {amount:,} chips."
    elif big_pot:
        kind = "pot_reels"
        title = "Monster pot reel"
        subtitle = f"{amount:,} chips moved across the felt."
    elif hot_streak:
        kind = "hot_streak"
        title = "Hot streak spotlight"
        subtitle = f"{winner.get('name', 'Winner')} is playing with visible momentum."
    elif leader and int(hand_number or 0) % 5 == 0:
        kind = "chip_leader"
        title = "Chip leader board"
        subtitle = f"{leader.get('name', 'The leader')} controls the biggest stack."
    elif winner:
        kind = "winner_jackpot"
        title = "Winner showcase"
        subtitle = f"{winner.get('name', 'Winner')} takes the previous hand."
    else:
        kind = "chip_leader"
        title = "Chip leader board"
        subtitle = f"{(leader or {}).get('name', 'The leader')} controls the biggest stack."

    symbols = _bumper_symbols(kind, winner, leader, recap, variety)
    seed = (int(hand_number or 0) * 131 + amount * 17 + len(winners) * 19 + len(kind) * 23) % 9973
    return {
        "enabled": True,
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "duration_ms": duration_ms,
        "seed": seed,
        "stats": {
            "symbols": symbols,
            "amount": amount,
            "winner_count": len(winners),
            "leader": (leader or {}).get("name", ""),
            "hand": recap.get("hand", ""),
            "format": variety.get("title", ""),
        },
        "responsible_label": bool(responsible_label),
    }


def _bumper_symbols(kind, winner, leader, recap, variety):
    winner_initial = str((winner or {}).get("name") or "AI")[:1].upper()
    leader_initial = str((leader or {}).get("name") or "L")[:1].upper()
    hand = str(recap.get("hand") or "Hand").split(" ")[0][:5].upper()
    format_label = str(variety.get("tempo") or "LIVE")[:5].upper()
    by_kind = {
        "winner_jackpot": ["★", winner_initial, hand],
        "pot_reels": ["♣", "POT", "♦"],
        "hot_streak": ["🔥", winner_initial, "HOT"],
        "chip_leader": ["♠", leader_initial, "LEAD"],
        "next_format": ["▶", format_label, "NEXT"],
    }
    return by_kind.get(kind, ["AI", "POKER", "★"])


def _won_amount(action):
    match = re.search(r"Won\s+([0-9,]+)", str(action or ""))
    return int(match.group(1).replace(",", "")) if match else 0


def _profile_signals(players, personality_arcs):
    signals = {}
    for player in players:
        player_id = player.get("id")
        arc = personality_arcs.get(player_id, {})
        signals[player_id] = {
            "style": arc.get("style", "Adaptive Competitor"),
            "confidence": int(arc.get("confidence", 0) or 0),
            "tilt": int(arc.get("tilt", 0) or 0),
            "risk_appetite": int(arc.get("risk_appetite", 0) or 0),
        }
    return signals
