"""Broadcast-director presentation state derived from public table state."""

from __future__ import annotations

import re


PRESENTATION_SCHEMA_VERSION = 1
BARTENDER_CHARACTER = {
    "id": "mira_7",
    "name": "Mira-7",
    "role": "AI bartender",
}
BARTENDER_LINE_PACKS = {
    "pre_hand": [
        {"tone": "cyan", "line": "Fresh deal under neon. Nobody owns the room yet."},
        {"tone": "cyan", "line": "New hand, clean glass, dirty secrets. Watch the blinds."},
    ],
    "all_in": [
        {"tone": "danger", "line": "All-in light is on. Nobody breathe on the rail."},
        {"tone": "danger", "line": "Every chip crossed the wire. Now the deck talks."},
    ],
    "river": [
        {"tone": "pink", "line": "River card hits like rain on chrome. Last chance to tell the truth."},
        {"tone": "pink", "line": "Fifth street is live. The room just got quieter."},
    ],
    "showdown": [
        {"tone": "gold", "line": "Cards up. The room loves a clean reveal."},
        {"tone": "gold", "line": "Showdown lights on. Let the best five cards speak."},
    ],
    "bust_out": [
        {"tone": "danger", "line": "One model leaves the booth; the den keeps the seat warm."},
        {"tone": "danger", "line": "Bust-out confirmed. Chrome ghosts make room at the rail."},
    ],
    "table_reset": [
        {"tone": "gold", "line": "Reset sweep running. Same den, fresh ghosts."},
        {"tone": "gold", "line": "Dealer drone scrubs the felt. Next hand loads clean."},
    ],
    "idle": [
        {"tone": "blue", "line": "Mira-7 wipes the bar and watches the stack lights."},
        {"tone": "blue", "line": "Synthetic patrons murmur. The table keeps its secrets."},
    ],
}


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
    casino_bumper_style="night_city_recaps",
    engagement_enabled=True,
    engagement_follow_message="Follow for 24/7 autonomous AI poker.",
    engagement_chat_prompt="Call out the next winner in chat.",
    showrunner_enabled=True,
    voice_cues_enabled=True,
    lounge=None,
    casino=None,
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
    lounge = lounge or {}
    casino = casino or {}

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
        action_history=action_history,
        personality_arcs=personality_arcs,
        big_blind=big_blind,
        hand_number=hand_number,
        enabled=casino_bumpers_enabled,
        duration_ms=casino_bumper_duration_ms,
        responsible_label=casino_bumper_responsible_label,
        frequency=casino_bumper_frequency,
        style=casino_bumper_style,
    )
    scene_state = _scene_state_payload(
        stage=stage,
        mode=mode,
        players=players,
        actor=actor,
        winners=winners,
        tournament=tournament,
        recap=recap,
        bumper=bumper,
        casino=casino,
        program=program,
        variety=variety,
        hand_number=hand_number,
        commentary=commentary,
    )
    engagement = _engagement_payload(
        players=players,
        actor=actor,
        winners=winners,
        all_ins=all_ins,
        chip_leader=chip_leader,
        stage=stage,
        pot=pot,
        big_blind=big_blind,
        tournament=tournament,
        recap=recap,
        bumper=bumper,
        program=program,
        variety=variety,
        enabled=engagement_enabled,
        follow_message=engagement_follow_message,
        chat_prompt=engagement_chat_prompt,
    )
    bartender = _bartender_payload(
        players=players,
        actor=actor,
        winners=winners,
        all_ins=all_ins,
        chip_leader=chip_leader,
        stage=stage,
        pot=pot,
        big_blind=big_blind,
        tournament=tournament,
        recap=recap,
        scene_state=scene_state,
        action_history=action_history,
        commentary=commentary,
        hand_number=hand_number,
        voice_enabled=voice_cues_enabled,
    )
    showrunner = _showrunner_payload(
        enabled=showrunner_enabled,
        voice_enabled=voice_cues_enabled,
        mode=mode,
        headline=headline,
        explainer=explainer,
        players=players,
        actor=actor,
        winners=winners,
        all_ins=all_ins,
        chip_leader=chip_leader,
        stage=stage,
        pot=pot,
        big_blind=big_blind,
        tournament=tournament,
        recap=recap,
        bumper=bumper,
        engagement=engagement,
        variety=variety,
        lounge=lounge,
        hand_number=hand_number,
    )
    lower_third = _lower_third_payload(
        mode=mode,
        headline=headline,
        explainer=explainer,
        players=players,
        actor=actor,
        winners=winners,
        all_ins=all_ins,
        chip_leader=chip_leader,
        stage=stage,
        pot=pot,
        big_blind=big_blind,
        tournament=tournament,
        action_history=action_history,
        commentary=commentary,
        recap=recap,
        engagement=engagement,
        program=program,
        variety=variety,
        lounge=lounge,
        casino=casino,
        hand_number=hand_number,
        bartender=bartender,
    )
    venue = _venue_payload(lounge=lounge, casino=casino, variety=variety, hand_number=hand_number)
    return {
        "schema_version": PRESENTATION_SCHEMA_VERSION,
        "mode": mode,
        "spotlight_seat_ids": [item for item in spotlights if item],
        "headline": headline,
        "explainer": explainer,
        "recap": recap,
        "bumper": bumper,
        "scene_state": scene_state,
        "bartender": bartender,
        "engagement": engagement,
        "visual_intensity": int(max(0, min(100, intensity))),
        "hand": int(hand_number or 0),
        "chip_leader": chip_leader.get("id") if chip_leader else None,
        "profile_signals": _profile_signals(players, personality_arcs),
        "showrunner_schema_version": 1,
        "beat_type": showrunner["beat_type"],
        "viewer_focus": showrunner["viewer_focus"],
        "voice_cue": showrunner["voice_cue"],
        "non_reader_labels": showrunner["non_reader_labels"],
        "audience_hook": showrunner["audience_hook"],
        "lower_third": lower_third,
        "venue": venue,
    }


def _scene_state_payload(
    *,
    stage,
    mode,
    players,
    actor,
    winners,
    tournament,
    recap,
    bumper,
    casino,
    program,
    variety,
    hand_number,
    commentary,
):
    """Return high-level OBS scene state without changing gameplay.

    The scene state exists for stream continuity: it gives OBS a clean
    standby/break/reset language while the normal table remains underneath, so
    reconnects and hand-boundary transitions never flash a blank source.
    """

    stage_key = str(stage or "").lower()
    latest = " ".join(str(line) for line in (commentary or [])[-4:])
    casino = casino or {}
    program = program or {}
    variety = variety or {}
    active_game = str(casino.get("active_game") or "poker")
    casino_room = bool(casino.get("enabled") and active_game != "poker")
    reset_hint = bool(re.search(r"\b(reset|restart|restarting|reload|reloading|restored|checkpoint|eliminated|bust|refunded)\b", latest, re.IGNORECASE))

    if int(hand_number or 0) <= 0 or (stage_key in {"standby", "loading"} and not actor and not winners and not (commentary or [])):
        state = "standby"
        label = "STANDBY"
        headline = "Night City table warming up"
        subhead = "Local models, deck, audio, and OBS overlays are coming online."
        details = [
            "Same browser source",
            "No blank transition",
            "Simulation-only chips",
        ]
        visible = True
        tone = "cyan"
    elif tournament.get("complete") or reset_hint:
        state = "table_reset"
        label = "TABLE RESET"
        headline = "Resetting the felt"
        if tournament.get("complete"):
            headline = "Tournament table reset"
        subhead = "Stacks, seats, and the next autonomous deal are being prepared."
        if variety.get("title"):
            subhead = f"Next block: {variety.get('title')}. Seats and stacks are being prepared."
        details = [
            "Seat check",
            "Deck reset",
            "Next hand loading",
        ]
        visible = True
        tone = "gold"
    elif bumper.get("enabled") or casino_room or recap.get("visible"):
        state = "break"
        label = "INTERMISSION"
        headline = "Cyber casino break"
        if casino_room:
            block = casino.get("program_block") or {}
            headline = block.get("title") or casino.get("spectacle_cue", {}).get("headline") or "Next room opens"
            subhead = block.get("viewer_hook") or casino.get("spectacle_cue", {}).get("caption") or "AI-only side-room beat while the main felt breathes."
        elif bumper.get("enabled"):
            headline = bumper.get("title") or "Night City bumper"
            subhead = bumper.get("relevance") or bumper.get("subtitle") or "A short poker-relevant bumper bridges the next hand."
        else:
            subhead = recap.get("detail") or "Previous hand recap while the table prepares the next deal."
        details = [
            "Poker-relevant",
            "Fictional chips",
            "No viewer wagers",
        ]
        visible = True
        tone = "magenta"
    else:
        state = "live_hand"
        label = "LIVE HAND"
        headline = program.get("segment") or "Live hand"
        subhead = program.get("detail") or "The active table remains the hero shot."
        details = [
            str(stage or "Live"),
            f"{len([player for player in players if not player.get('eliminated')])} seats live",
        ]
        visible = False
        tone = "green"

    return {
        "schema_version": 1,
        "state": state,
        "label": label,
        "headline": str(headline or label)[:96],
        "subhead": str(subhead or "")[:160],
        "details": [str(item)[:42] for item in details if item],
        "visible": bool(visible),
        "tone": tone,
        "transition": "crossfade",
        "safe_label": "SIMULATION ONLY · FICTIONAL CHIPS · NO REAL MONEY",
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


def _venue_payload(*, lounge, casino, variety, hand_number):
    """Return compact public venue flavor for the OBS theme layer.

    This is intentionally presentation-only: it is derived from the already
    public lounge/program state and never feeds decisions, odds, or hidden
    information back into the poker engine or AI prompts.
    """

    lounge = lounge or {}
    casino = casino or {}
    variety = variety or {}
    venue = lounge.get("venue") if isinstance(lounge.get("venue"), dict) else {}
    enabled = lounge.get("enabled", True) is not False
    name = _compact_venue_text(venue.get("name") or "Rainline Room", "Rainline Room", 32)
    district = _compact_venue_text(venue.get("district") or "Simulation District", "Simulation District", 36)
    zone = _compact_venue_text(lounge.get("venue_zone") or venue.get("booth") or "back-alley holo table", "back-alley holo table", 42)
    lighting = _compact_venue_text(venue.get("lighting") or "cyan rain and magenta glass", "cyan rain and magenta glass", 44)
    weather = _compact_venue_text(venue.get("weather") or "synthetic rain", "synthetic rain", 32)
    mood = _compact_venue_text(lounge.get("table_mood") or "Neon hour", "Neon hour", 32)
    service_bot = _compact_venue_text(lounge.get("service_bot") or "Chrome Valet", "Chrome Valet", 28)
    pressure = max(0, min(100, int(lounge.get("pressure_index", 0) or 0)))
    active_game = str(casino.get("active_game") or "poker").replace("_", " ").upper()
    block = casino.get("program_block") if isinstance(casino.get("program_block"), dict) else {}
    room = _compact_venue_text(block.get("title") or variety.get("title") or active_game.title(), "Main Poker Table", 42)
    header_label = f"{name} // {district}"
    status_chip = f"{mood} // pressure {pressure}%"
    table_label = f"DEALER // {zone}"
    footer_line = f"{district} // {lighting} // {weather}"
    return {
        "schema_version": 1,
        "enabled": bool(enabled),
        "name": name,
        "district": district,
        "zone": zone,
        "lighting": lighting,
        "weather": weather,
        "mood": mood,
        "service_bot": service_bot,
        "pressure": pressure,
        "room": room,
        "active_game": active_game,
        "header_label": header_label,
        "status_chip": status_chip,
        "table_label": table_label,
        "footer_line": footer_line,
        "signs": {
            "left": "24/7 AI DEN",
            "right": f"{service_bot} ONLINE",
            "lower": district,
        },
        "atmosphere": _compact_venue_text(lounge.get("atmosphere_line") or f"{service_bot} keeps {zone} under {lighting}.", "", 120),
        "hand": int(hand_number or 0),
        "safe_label": "simulation-only venue skin",
    }


def _compact_venue_text(value, fallback, limit):
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        text = fallback
    for forbidden in ("deposit", "cash out", "spin again"):
        text = re.sub(forbidden, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -Â·")
    if not text:
        text = fallback
    return text[: max(1, int(limit))]


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
    action_history,
    personality_arcs,
    big_blind,
    hand_number,
    enabled,
    duration_ms,
    responsible_label,
    frequency,
    style,
):
    duration_ms = max(4000, min(8000, int(duration_ms or 6500)))
    style = str(style or "night_city_recaps")
    disabled = {
        "enabled": False,
        "kind": "",
        "title": "",
        "subtitle": "",
        "duration_ms": duration_ms,
        "seed": int(hand_number or 0),
        "stats": {},
        "visual_family": "",
        "relevance": "",
        "style": style,
        "theme": "Night City casino recap" if style == "night_city_recaps" else "Classic broadcast recap",
        "responsible_label": bool(responsible_label),
    }
    if not enabled or str(frequency or "selected_hands").lower() in {"off", "disabled", "never"}:
        return disabled
    if not recap.get("visible"):
        return disabled

    amount = int(recap.get("amount", 0) or 0)
    split = len(winners) > 1
    all_in_hand = any(str(record.get("action", "")).lower() == "all_in" for record in (action_history or []))
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
    selected = next_format or split or all_in_hand or big_pot or hot_streak or int(hand_number or 0) % 3 == 0 or int(hand_number or 0) % 5 == 0
    if str(frequency or "selected_hands").lower() == "selected_hands" and not selected:
        return disabled

    if next_format:
        kind = "next_format"
        title = "Next Night City table block" if style == "night_city_recaps" else "Next table block"
        subtitle = variety.get("title") or "The broadcast is rotating to a fresh segment."
    elif split:
        kind = "pot_reels"
        title = "Neon split-pot reel" if style == "night_city_recaps" else "Split pot reel"
        subtitle = f"{' + '.join(player.get('name', 'Player') for player in winners)} share {amount:,} chips."
    elif all_in_hand:
        kind = "pot_reels"
        title = "Underground all-in wheel" if style == "night_city_recaps" else "All-in pressure wheel"
        subtitle = "The intermission tracks the all-in pot, winner, and hand result."
    elif big_pot:
        kind = "pot_reels"
        title = "Monster pot neon reel" if style == "night_city_recaps" else "Monster pot reel"
        subtitle = f"{amount:,} chips moved across the felt."
    elif hot_streak:
        kind = "hot_streak"
        title = "Redline hot-streak meter" if style == "night_city_recaps" else "Hot streak spotlight"
        subtitle = f"{winner.get('name', 'Winner')} is playing with visible momentum."
    elif leader and int(hand_number or 0) % 5 == 0:
        kind = "chip_leader"
        title = "Skyline chip-leader board" if style == "night_city_recaps" else "Chip leader board"
        subtitle = f"{leader.get('name', 'The leader')} controls the biggest stack."
    elif winner:
        kind = "winner_jackpot"
        title = "Night City winner showcase" if style == "night_city_recaps" else "Winner showcase"
        subtitle = f"{winner.get('name', 'Winner')} takes the previous hand."
    else:
        kind = "chip_leader"
        title = "Skyline chip-leader board" if style == "night_city_recaps" else "Chip leader board"
        subtitle = f"{(leader or {}).get('name', 'The leader')} controls the biggest stack."

    visual_family = _bumper_visual_family(kind, all_in_hand=all_in_hand)
    relevance = _bumper_relevance(
        kind=kind,
        winner=winner,
        leader=leader,
        recap=recap,
        variety=variety,
        amount=amount,
        all_in_hand=all_in_hand,
    )
    symbols = _bumper_symbols(kind, winner, leader, recap, variety, visual_family=visual_family)
    seed = (int(hand_number or 0) * 131 + amount * 17 + len(winners) * 19 + len(kind) * 23) % 9973
    return {
        "enabled": True,
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "duration_ms": duration_ms,
        "seed": seed,
        "visual_family": visual_family,
        "relevance": relevance,
        "stats": {
            "symbols": symbols,
            "amount": amount,
            "winner_count": len(winners),
            "leader": (leader or {}).get("name", ""),
            "hand": recap.get("hand", ""),
            "format": variety.get("title", ""),
            "scene": "Night City recap" if style == "night_city_recaps" else "Broadcast recap",
        },
        "style": style,
        "theme": "Night City casino recap" if style == "night_city_recaps" else "Classic broadcast recap",
        "responsible_label": bool(responsible_label),
    }


def _bumper_visual_family(kind, all_in_hand=False):
    if all_in_hand:
        return "equity_wheel"
    return {
        "winner_jackpot": "winner_cards",
        "pot_reels": "poker_reels",
        "hot_streak": "momentum_meter",
        "chip_leader": "standings_ladder",
        "next_format": "format_marquee",
    }.get(kind, "poker_recap")


def _bumper_relevance(*, kind, winner, leader, recap, variety, amount, all_in_hand=False):
    winner_name = (winner or {}).get("name") or "The winner"
    leader_name = (leader or {}).get("name") or "The chip leader"
    hand = recap.get("hand") or "the winning hand"
    if kind == "next_format":
        return f"Coming next: {variety.get('title') or 'a fresh poker table block'}."
    if all_in_hand:
        return f"All-in result: {winner_name} takes {amount:,} chips with {hand}."
    if kind == "pot_reels":
        return f"Pot recap: {amount:,} fictional chips were awarded from the last poker hand."
    if kind == "hot_streak":
        return f"Momentum watch: {winner_name} just won with {hand}."
    if kind == "chip_leader":
        return f"Standings watch: {leader_name} is currently out front."
    return f"Winner recap: {winner_name} won the previous poker hand with {hand}."


def _bumper_symbols(kind, winner, leader, recap, variety, visual_family=""):
    winner_initial = str((winner or {}).get("name") or "AI")[:1].upper()
    leader_initial = str((leader or {}).get("name") or "L")[:1].upper()
    hand = str(recap.get("hand") or "Hand").split(" ")[0][:5].upper()
    format_label = str(variety.get("tempo") or "LIVE")[:5].upper()
    if visual_family == "equity_wheel":
        return ["ALL", "IN", winner_initial]
    by_kind = {
        "winner_jackpot": ["★", winner_initial, hand],
        "pot_reels": ["♣", "POT", "♦"],
        "hot_streak": ["🔥", winner_initial, "HOT"],
        "chip_leader": ["♠", leader_initial, "LEAD"],
        "next_format": ["▶", format_label, "NEXT"],
    }
    return by_kind.get(kind, ["AI", "POKER", "★"])


def _engagement_payload(
    *,
    players,
    actor,
    winners,
    all_ins,
    chip_leader,
    stage,
    pot,
    big_blind,
    tournament,
    recap,
    bumper,
    program,
    variety,
    enabled,
    follow_message,
    chat_prompt,
):
    follow = _safe_engagement_text(follow_message, "Follow for 24/7 autonomous AI poker.", 96)
    base_prompt = _safe_engagement_text(chat_prompt, "Call out the next winner in chat.", 96)
    safe = "Bragging rights only · fictional chips · no wagers."
    stage_key = str(stage or "").lower()
    leader_name = (chip_leader or {}).get("name", "the chip leader")
    prompt = base_prompt
    context = "Audience desk"
    focus = leader_name

    if winners:
        winner_names = " + ".join(player.get("name", "Winner") for player in winners)
        prompt = f"Chat: who wins the next hand after {winner_names}?"
        context = "Winner follow-up"
        focus = winner_names
    elif all_ins:
        names = " + ".join(player.get("name", "All-in") for player in all_ins)
        prompt = f"Chat: does {names} survive this all-in?"
        context = "All-in sweat"
        focus = names
    elif actor:
        prompt = f"Chat: what should {actor.get('name', 'the actor')} do here — call, raise, or fold?"
        context = "Decision prompt"
        focus = actor.get("name", "acting player")
    elif stage_key == "showdown":
        prompt = "Chat: which revealed hand is best before the award?"
        context = "Showdown prompt"
        focus = "showdown"
    elif int(pot or 0) >= max(1, int(big_blind or 1)) * 10:
        prompt = f"Chat: who takes this {int(pot):,}-chip pot?"
        context = "Pot prompt"
    elif variety.get("title"):
        prompt = f"Chat: pick the table captain for {variety.get('title')}."
        context = "Format prompt"
    elif tournament.get("complete"):
        prompt = "Chat: who wins the next sit-and-go?"
        context = "Trophy prompt"

    if bumper.get("enabled"):
        context = "Intermission prompt"
    if recap.get("visible") and not winners:
        context = "Recap prompt"

    return {
        "schema_version": 1,
        "enabled": bool(enabled),
        "context": context,
        "prompt": _safe_engagement_text(prompt, base_prompt, 120),
        "follow": follow,
        "safe_label": safe,
        "focus": focus,
        "program": program.get("segment") or variety.get("title") or "AI Poker League",
    }


def _bartender_payload(
    *,
    players,
    actor,
    winners,
    all_ins,
    chip_leader,
    stage,
    pot,
    big_blind,
    tournament,
    recap,
    scene_state,
    action_history,
    commentary,
    hand_number,
    voice_enabled,
):
    stage_key = str(stage or "").lower()
    reset_hint = scene_state.get("state") == "table_reset" or bool(
        re.search(r"\b(reset|restart|reloading|restored|checkpoint)\b", " ".join(str(line) for line in (commentary or [])[-4:]), re.IGNORECASE)
    )
    eliminated = [player for player in players if player.get("eliminated")]
    event_type = "idle"
    priority = 22
    if eliminated or tournament.get("complete"):
        event_type = "bust_out"
        priority = 82
    elif winners or recap.get("visible") or stage_key == "showdown":
        event_type = "showdown"
        priority = 76
    elif all_ins:
        event_type = "all_in"
        priority = 86
    elif stage_key == "river":
        event_type = "river"
        priority = 58
    elif reset_hint:
        event_type = "table_reset"
        priority = 70
    elif stage_key in {"pre-flop", "waiting"} and len(action_history or []) <= 2:
        event_type = "pre_hand"
        priority = 42

    line_pack = BARTENDER_LINE_PACKS.get(event_type) or BARTENDER_LINE_PACKS["idle"]
    seed = int(hand_number or 0) + len(action_history or []) + int((pot or 0) / max(1, int(big_blind or 1)))
    selected = line_pack[seed % len(line_pack)]
    line = _safe_engagement_text(selected.get("line"), "", 96)
    enabled = bool(line and (event_type != "idle" or int(hand_number or 0) % 4 == 0))
    speaker = BARTENDER_CHARACTER["name"]
    cue_id = f"bartender|{event_type}|{int(hand_number or 0)}|{seed % len(line_pack)}"
    return {
        "schema_version": 1,
        "enabled": enabled,
        "character": BARTENDER_CHARACTER,
        "speaker": speaker,
        "event_type": event_type,
        "line": line if enabled else "",
        "tone": selected.get("tone", "blue"),
        "priority": priority,
        "cooldown_hands": 2,
        "context": {
            "actor": (actor or {}).get("name", ""),
            "all_in": [player.get("name", "AI") for player in all_ins],
            "winners": [player.get("name", "AI") for player in winners],
            "chip_leader": (chip_leader or {}).get("name", ""),
            "pot": int(pot or 0),
        },
        "voice_cue": {
            "enabled": bool(enabled and voice_enabled),
            "id": cue_id,
            "speaker": speaker,
            "line": line if enabled and voice_enabled else "",
            "caption": f"{speaker}: {line}" if enabled and voice_enabled else "",
            "priority": priority,
            "duration_ms": 3400 if priority < 80 else 4300,
            "ducking": 0.28 if priority < 80 else 0.44,
        },
    }


def _showrunner_payload(
    *,
    enabled,
    voice_enabled,
    mode,
    headline,
    explainer,
    players,
    actor,
    winners,
    all_ins,
    chip_leader,
    stage,
    pot,
    big_blind,
    tournament,
    recap,
    bumper,
    engagement,
    variety,
    lounge,
    hand_number,
):
    if not enabled:
        return {
            "beat_type": "table",
            "viewer_focus": explainer or "The table is live.",
            "voice_cue": {"enabled": False},
            "non_reader_labels": {"enabled": False, "items": []},
            "audience_hook": "",
        }

    stage_key = str(stage or "").lower()
    amount = int(recap.get("amount", 0) or 0)
    bb = max(1, int(big_blind or 1))
    beat_type = "table"
    focus = explainer or "The table is live."
    priority = 25
    speaker = "Night City host"

    if bumper.get("enabled"):
        beat_type = "intermission"
        focus = bumper.get("relevance") or "This short casino-floor bumper recaps the last poker hand."
        priority = 58
    elif tournament.get("complete"):
        beat_type = "winner"
        champion = next((player for player in players if player.get("id") == tournament.get("winner")), None)
        focus = f"{(champion or {}).get('name', 'The champion')} wins the sit-and-go trophy."
        priority = 92
    elif winners:
        beat_type = "winner"
        names = " + ".join(player.get("name", "Winner") for player in winners)
        hand = recap.get("hand") or "the winning hand"
        focus = f"{names} just won {amount:,} chips with {hand}." if amount else f"{names} just won the hand."
        priority = 88
    elif stage_key == "showdown":
        beat_type = "showdown"
        focus = "Cards are face-up. The best five-card poker hand wins each eligible pot."
        priority = 76
    elif all_ins:
        beat_type = "all_in"
        names = " + ".join(player.get("name", "All-in") for player in all_ins)
        focus = f"{names} is all-in. Every remaining card can decide the pot."
        priority = 84
    elif mode == "big_pot":
        beat_type = "tension"
        focus = f"The pot is already worth {pot / bb:.0f} big blinds."
        priority = 68
    elif actor:
        beat_type = "decision"
        focus = _viewer_decision_focus(actor)
        priority = 62
    elif variety.get("enabled") and int(variety.get("hands_remaining", 99) or 99) <= 1:
        beat_type = "format_change"
        focus = f"One hand until the next table block: {variety.get('title', 'fresh format')}."
        priority = 54
    elif lounge.get("enabled") and int(lounge.get("pressure_index", 0) or 0) >= 70:
        beat_type = "lounge"
        focus = lounge.get("atmosphere_line") or lounge.get("broadcast_cue") or "The AI lounge is changing the room pressure."
        priority = 44

    labels = _non_reader_labels(
        beat_type=beat_type,
        actor=actor,
        winners=winners,
        all_ins=all_ins,
        chip_leader=chip_leader,
        pot=pot,
        big_blind=bb,
        recap=recap,
        lounge=lounge,
    )
    line = _voice_line(beat_type, focus, headline, engagement)
    cue_id_parts = [
        beat_type,
        str(int(hand_number or 0)),
        str(stage or ""),
        str((actor or {}).get("id") or ""),
        ",".join(player.get("id", "") for player in winners or all_ins),
        str(amount or pot or 0),
    ]
    voice_cue = {
        "enabled": bool(voice_enabled and line),
        "id": "|".join(cue_id_parts),
        "priority": priority,
        "speaker": speaker,
        "line": line if voice_enabled else "",
        "caption": focus,
        "duration_ms": 4200 if priority < 80 else 5600,
        "ducking": 0.38 if priority < 80 else 0.55,
    }
    return {
        "beat_type": beat_type,
        "viewer_focus": focus,
        "voice_cue": voice_cue,
        "non_reader_labels": {"enabled": True, "items": labels},
        "audience_hook": engagement.get("prompt", ""),
    }


def _lower_third_payload(
    *,
    mode,
    headline,
    explainer,
    players,
    actor,
    winners,
    all_ins,
    chip_leader,
    stage,
    pot,
    big_blind,
    tournament,
    action_history,
    commentary,
    recap,
    engagement,
    program,
    variety,
    lounge,
    casino,
    hand_number,
    bartender,
):
    casino = casino or {}
    casino_game = str(casino.get("active_game") or "poker")
    casino_block = casino.get("program_block") if isinstance(casino.get("program_block"), dict) else {}
    casino_cue = casino.get("spectacle_cue") if isinstance(casino.get("spectacle_cue"), dict) else {}
    display_mode = "casino_room" if casino.get("enabled") and casino_game != "poker" else ("winner" if winners or tournament.get("complete") else mode)
    kicker = {
        "table": "LIVE TABLE",
        "decision": "DECISION",
        "big_pot": "BIG POT",
        "all_in": "ALL-IN PRESSURE",
        "showdown": "SHOWDOWN",
        "recap": "HAND RECAP",
        "winner": "WINNER",
        "casino_room": "NEXT ROOM",
    }.get(display_mode, "LIVE TABLE")
    if display_mode == "casino_room":
        room = casino_block.get("title") or casino_game.replace("_", " ").title()
        headline = casino_cue.get("headline") or room
        explainer = casino_cue.get("caption") or casino_block.get("viewer_hook") or "AI-only side-room beat with fictional bankrolls."
    elif display_mode == "winner" and recap.get("winners"):
        names = " + ".join(item.get("name", "Winner") for item in recap.get("winners", []))
        headline = f"{names} wins the hand" if len(recap.get("winners", [])) == 1 else f"{names} split the pot"
        explainer = recap.get("detail") or explainer

    modules = _lower_third_modules(
        players=players,
        actor=actor,
        chip_leader=chip_leader,
        stage=stage,
        pot=pot,
        big_blind=big_blind,
        tournament=tournament,
        recap=recap,
        engagement=engagement,
        program=program,
        variety=variety,
        lounge=lounge,
        casino=casino,
    )
    priority = {
        "winner": 95,
        "casino_room": 86,
        "all_in": 88,
        "showdown": 76,
        "big_pot": 72,
        "decision": 64,
        "recap": 58,
    }.get(display_mode, 35)
    active_module = "casino" if display_mode == "casino_room" else "winner" if display_mode == "winner" else "decision" if actor else "equity" if all_ins or display_mode == "showdown" else "pot"
    if not any(module.get("id") == active_module for module in modules):
        active_module = modules[0]["id"] if modules else ""
    ticker_events = _spectator_ticker_events(
        players=players,
        action_history=action_history,
        commentary=commentary,
        stage=stage,
        pot=pot,
        big_blind=big_blind,
        winners=winners,
        all_ins=all_ins,
        actor=actor,
        tournament=tournament,
        recap=recap,
        program=program,
        variety=variety,
        lounge=lounge,
        casino=casino,
        hand_number=hand_number,
        bartender=bartender,
    )
    return {
        "schema_version": 1,
        "mode": display_mode,
        "kicker": kicker,
        "headline": _safe_engagement_text(headline, "Live table", 96),
        "subhead": _safe_engagement_text(explainer, "The next key beat will appear here.", 150),
        "modules": modules,
        "active_module": active_module,
        "ticker_items": [event["text"] for event in ticker_events],
        "ticker_events": ticker_events,
        "priority": priority,
        "duration_ms": 8500 if priority < 80 else 6800,
    }


def _lower_third_modules(
    *,
    players,
    actor,
    chip_leader,
    stage,
    pot,
    big_blind,
    tournament,
    recap,
    engagement,
    program,
    variety,
    lounge,
    casino,
):
    bb = max(1, int(big_blind or 1))
    modules = [
        {
            "id": "pot",
            "label": "POT",
            "title": "Total pot",
            "value": f"{int(pot or 0):,}",
            "detail": f"{int((pot or 0) / bb)} big blinds" if pot else "Pot building",
            "tone": "gold",
        }
    ]
    if actor:
        call = next((entry for entry in (actor.get("legal_actions") or []) if entry.get("action") == "call"), None)
        options = ", ".join(str(entry.get("action", "")).replace("_", " ") for entry in actor.get("legal_actions", []) if entry.get("action"))
        modules.insert(
            0,
            {
                "id": "decision",
                "label": "TO ACT",
                "title": actor.get("name", "Acting player"),
                "value": f"{int(call.get('amount', 0) or 0):,}" if call else "CHECK",
                "detail": f"Options: {options or 'waiting'}",
                "tone": "cyan",
            },
        )
    equity_rows = [
        {"left": player.get("name", "AI"), "right": f"{float(player.get('equity') or 0):.0f}%"}
        for player in sorted(players, key=lambda item: float(item.get("equity") or -1), reverse=True)
        if player.get("equity") is not None and not player.get("folded")
    ][:3]
    if equity_rows:
        modules.append(
            {
                "id": "equity",
                "label": "RACE",
                "title": "Chance to win",
                "value": equity_rows[0]["right"],
                "detail": equity_rows[0]["left"],
                "rows": equity_rows,
                "tone": "pink",
            }
        )
    elif any(player.get("all_in") and not player.get("folded") for player in players) or str(stage).lower() == "showdown":
        modules.append(
            {
                "id": "equity",
                "label": "RACE",
                "title": "Chance to win",
                "value": "PENDING",
                "detail": "Analysis is catching up",
                "rows": [
                    {"left": player.get("name", "AI"), "right": "live"}
                    for player in players
                    if player.get("active") and not player.get("folded")
                ][:3],
                "tone": "pink",
            }
        )
    modules.append(
        {
            "id": "hand",
            "label": "HAND",
            "title": "Current street",
            "value": str(stage or "Waiting").upper(),
            "detail": recap.get("hand") or "Best five cards win each eligible pot.",
            "tone": "blue",
        }
    )
    standings = [
        {"left": f"#{index + 1} {player.get('name', 'AI')}", "right": f"{int(player.get('chips', 0)):,}"}
        for index, player in enumerate(
            sorted(
                [player for player in players if not player.get("eliminated")],
                key=lambda item: int(item.get("chips", 0)),
                reverse=True,
            )[:3]
        )
    ]
    if standings:
        modules.append(
            {
                "id": "standings",
                "label": "STACKS",
                "title": "Chip leader",
                "value": (chip_leader or {}).get("name", standings[0]["left"]),
                "detail": f"{int((chip_leader or {}).get('chips', 0)):,} chips" if chip_leader else "",
                "rows": standings,
                "tone": "gold",
            }
        )
    model_counts = {
        "ollama": sum(int((player.get("model_health") or {}).get("ollama_decisions", 0) or 0) for player in players),
        "fallback": sum(int((player.get("model_health") or {}).get("fallback_decisions", 0) or 0) for player in players),
    }
    modules.append(
        {
            "id": "models",
            "label": "AI",
            "title": "Model health",
            "value": "OLLAMA" if model_counts["ollama"] else "WARMING",
            "detail": f"{model_counts['ollama']} local · {model_counts['fallback']} fallback decisions",
            "tone": "cyan",
        }
    )
    if casino.get("enabled"):
        block = casino.get("program_block") if isinstance(casino.get("program_block"), dict) else {}
        modules.append(
            {
                "id": "casino",
                "label": "ROOM",
                "title": block.get("title") or "Night City room",
                "value": str(casino.get("active_game") or "poker").replace("_", " ").upper(),
                "detail": block.get("viewer_hook") or "AI-only programming block.",
                "tone": "pink",
            }
        )
    if lounge.get("enabled"):
        modules.append(
            {
                "id": "lounge",
                "label": "LOUNGE",
                "title": lounge.get("scene_name") or "AI lounge",
                "value": f"{int(lounge.get('pressure_index', 0) or 0)}%",
                "detail": lounge.get("atmosphere_line") or lounge.get("table_mood") or "Fictional AI lounge texture.",
                "tone": "blue",
            }
        )
    if tournament:
        modules.append(
            {
                "id": "level",
                "label": "LEVEL",
                "title": "Tournament clock",
                "value": f"L{tournament.get('level', 1)}",
                "detail": f"{tournament.get('hands_remaining', 0)} hand(s) until blinds move.",
                "tone": "gold",
            }
        )
    else:
        modules.append(
            {
                "id": "program",
                "label": "FORMAT",
                "title": variety.get("title") or program.get("segment") or "Cash game",
                "value": str(variety.get("tempo") or "LIVE").upper(),
                "detail": variety.get("viewer_explainer") or program.get("detail") or "Current broadcast segment.",
                "tone": "blue",
            }
        )
    if engagement.get("enabled"):
        modules.append(
            {
                "id": "chat",
                "label": "CHAT",
                "title": "Audience prompt",
                "value": "BRAGGING RIGHTS",
                "detail": engagement.get("prompt") or "Call out the next winner in chat.",
                "tone": "cyan",
            }
        )
    return modules[:8]


def _spectator_ticker_events(
    *,
    players,
    action_history,
    commentary,
    stage,
    pot,
    big_blind,
    winners,
    all_ins,
    actor,
    tournament,
    recap,
    program,
    variety,
    lounge,
    casino,
    hand_number,
    bartender,
):
    events = []
    stage_key = str(stage or "").lower()
    active_hand = bool(actor or all_ins or stage_key not in {"waiting", "standby", "loading"})

    def add(label, text, severity="normal", event_type="poker", priority=30):
        text = _safe_engagement_text(text, "", 116)
        if not text:
            return
        events.append(
            {
                "type": str(event_type or "poker")[:24],
                "severity": str(severity or "normal")[:24],
                "label": str(label or "LIVE")[:18].upper(),
                "text": text,
                "priority": int(priority or 0),
            }
        )

    for action in list(action_history or [])[-8:]:
        action_name = str(action.get("action") or "")
        player = _player_for_seat(players, action.get("seat"))
        name = (player or {}).get("name") or f"Seat {action.get('seat')}"
        amount = int(action.get("amount", 0) or 0)
        copy = f"{name} {_plain_action(action_name)}"
        if amount:
            copy = f"{copy} {amount:,}"
        if action_name == "all_in":
            add("ALL-IN", copy, "all_in", "action", 92)
        elif action_name in {"raise", "bet"}:
            add("PRESSURE", copy, "major", "action", 72)
        elif action_name in {"call", "fold", "check"}:
            add("ACTION", copy, "normal", "action", 46)
        else:
            add("POSTED", copy, "normal", "action", 24)

    if all_ins:
        names = " + ".join(player.get("name", "AI") for player in all_ins)
        add("ALL-IN", f"{names} has every chip committed; the rail is locked on the runout.", "all_in", "all_in", 94)

    if winners:
        names = " + ".join(player.get("name", "Winner") for player in winners)
        amount = int(recap.get("amount", 0) or 0)
        hand = recap.get("hand") or "the winning hand"
        verb = "split" if len(winners) > 1 else "wins"
        add("WINNER", f"{names} {verb} {amount:,} with {hand}.", "showdown", "winner", 98)
    elif stage_key == "showdown":
        add("SHOWDOWN", "Cards are exposed; best five-card hand takes each eligible pot.", "showdown", "street", 86)

    if stage_key in {"flop", "turn", "river"}:
        street_copy = {
            "flop": "Three shared cards hit the neon felt.",
            "turn": "Fourth street is live; one river card can swing the room.",
            "river": "Final shared card is down; this is the last decision point.",
        }[stage_key]
        add("STREET", street_copy, "major" if int(pot or 0) >= max(1, int(big_blind or 1)) * 10 else "normal", "street", 62)

    eliminated = [player for player in players if player.get("eliminated")]
    for player in eliminated[-2:]:
        add("OUT", f"{player.get('name', 'A model')} is eliminated; the table closes ranks.", "major", "model", 78)

    latest = " ".join(str(line) for line in list(commentary or [])[-4:])
    if re.search(r"\b(reset|restart|reloading|restored|checkpoint)\b", latest, re.IGNORECASE):
        add("RESET", "Table reset in progress; seats, stacks, and deck state are being verified.", "major", "reset", 84)

    for line in list(commentary or [])[-4:]:
        text = _safe_engagement_text(line, "", 112)
        if not text:
            continue
        lowered = text.lower()
        if "all-in" in lowered or "all in" in lowered:
            add("ALL-IN", text, "all_in", "commentary", 90)
        elif re.search(r"\b(wins?|share|awarded)\b", lowered):
            add("RESULT", text, "showdown", "commentary", 88)
        elif re.search(r"\b(eliminated|bust|out)\b", lowered):
            add("OUT", text, "major", "commentary", 78)
        elif ":" in text:
            add("TABLE TALK", text, "flavor", "talk", 28)
        else:
            add("LIVE", text, "normal", "commentary", 34)

    if (bartender or {}).get("enabled") and (bartender or {}).get("line"):
        add(
            (bartender.get("speaker") or "BAR").upper(),
            f"{bartender.get('speaker', 'Mira-7')}: {bartender.get('line')}",
            "flavor",
            "bartender",
            int(bartender.get("priority", 24) or 24),
        )

    for flavor in _haunt_flavor_events(
        hand_number=hand_number,
        active_hand=active_hand,
        program=program,
        variety=variety,
        lounge=lounge,
        casino=casino,
    ):
        add(flavor["label"], flavor["text"], "flavor", "flavor", flavor["priority"])

    seen = set()
    compact = []
    for index, event in enumerate(events):
        key = event["text"].lower()
        if key in seen:
            continue
        seen.add(key)
        compact.append({**event, "_order": index})
    compact.sort(key=lambda event: (-event["priority"], event["_order"]))
    return [{key: value for key, value in event.items() if key != "_order"} for event in compact[:6]]


def _haunt_flavor_events(*, hand_number, active_hand, program, variety, lounge, casino):
    priority = 12 if active_hand else 24
    events = []
    if (lounge or {}).get("enabled"):
        events.append(
            {
                "label": "LOUNGE",
                "text": lounge.get("atmosphere_line") or lounge.get("table_mood") or "Synthetic lounge lights ripple behind the table.",
                "priority": priority + 4,
            }
        )
    if (casino or {}).get("enabled") and str(casino.get("active_game") or "poker") != "poker":
        block = casino.get("program_block") if isinstance(casino.get("program_block"), dict) else {}
        events.append(
            {
                "label": "ROOM",
                "text": block.get("viewer_hook") or "A side-room camera opens for AI-only fictional bankroll drama.",
                "priority": priority + 3,
            }
        )
    rotation = [
        ("RAIL", "A synthetic patron slips into the rail glow and watches the pot."),
        ("BAR", "Bartender bot mixes neon tonic while the next decision loads."),
        ("SCAN", "Security scan sweeps the back room; the table stays live."),
        ("CITY", "Rainline chatter spikes under the holographic skyline."),
        ("DEALER", "Dealer drone hums softly over the felt."),
    ]
    label, text = rotation[int(hand_number or 0) % len(rotation)]
    if variety.get("title"):
        text = f"{variety.get('title')} ambience: {text}"
    elif program.get("segment"):
        text = f"{program.get('segment')}: {text}"
    events.append({"label": label, "text": text, "priority": priority})
    return events[:2]


def _lower_third_ticker_items(players, action_history, commentary):
    return [
        event["text"]
        for event in _spectator_ticker_events(
            players=players,
            action_history=action_history,
            commentary=commentary,
            stage="",
            pot=0,
            big_blind=1,
            winners=[],
            all_ins=[],
            actor=None,
            tournament={},
            recap={},
            program={},
            variety={},
            lounge={},
            casino={},
            hand_number=0,
            bartender={},
        )
    ]


def _player_for_seat(players, seat):
    for player in players or []:
        if player.get("seat") == seat:
            return player
    try:
        index = int(seat)
    except (TypeError, ValueError):
        return None
    if 0 <= index < len(players or []):
        return list(players or [])[index]
    return None


def _plain_action(action):
    return {
        "small_blind": "posts small blind",
        "big_blind": "posts big blind",
        "ante": "posts ante",
        "all_in": "moves all-in",
    }.get(str(action or ""), str(action or "waits").replace("_", " "))


def _viewer_decision_focus(actor):
    legal = list(actor.get("legal_actions") or [])
    call = next((entry for entry in legal if entry.get("action") == "call"), None)
    can_raise = any(entry.get("action") in {"bet", "raise"} for entry in legal)
    name = actor.get("name", "The player")
    if call:
        amount = int(call.get("amount", 0) or 0)
        options = "call, raise, or fold" if can_raise else "call or fold"
        return f"{name} must call {amount:,} chips to stay in, or choose to {options}."
    if can_raise:
        return f"{name} can check for free or bet to put pressure on the table."
    return f"{name} can check for free and pass the action along."


def _non_reader_labels(*, beat_type, actor, winners, all_ins, chip_leader, pot, big_blind, recap, lounge):
    labels = [{"label": "POT", "value": f"{int(pot or 0):,}", "tone": "gold"}]
    if beat_type == "decision" and actor:
        call = next((entry for entry in (actor.get("legal_actions") or []) if entry.get("action") == "call"), None)
        if call:
            labels.insert(0, {"label": "TO CALL", "value": f"{int(call.get('amount', 0) or 0):,}", "tone": "cyan"})
        else:
            labels.insert(0, {"label": "FREE", "value": "CHECK", "tone": "cyan"})
        labels.append({"label": "ACTING", "value": actor.get("name", "AI"), "tone": "pink"})
    elif beat_type == "all_in":
        names = " + ".join(player.get("name", "AI") for player in all_ins)
        labels.insert(0, {"label": "ALL-IN", "value": names or "YES", "tone": "danger"})
    elif beat_type == "winner":
        names = " + ".join(player.get("name", "Winner") for player in winners) or recap.get("winners", [{}])[0].get("name", "Winner")
        labels.insert(0, {"label": "WINNER", "value": names, "tone": "gold"})
        if recap.get("hand"):
            labels.append({"label": "HAND", "value": recap.get("hand"), "tone": "cyan"})
    elif beat_type == "tension":
        labels.insert(0, {"label": "BIG POT", "value": f"{int((pot or 0) / max(1, big_blind))} BB", "tone": "danger"})
    elif beat_type == "lounge":
        labels.insert(0, {"label": "LOUNGE", "value": lounge.get("table_mood", "NEON"), "tone": "pink"})
    elif chip_leader:
        labels.append({"label": "LEADER", "value": chip_leader.get("name", "AI"), "tone": "cyan"})
    return labels[:4]


def _voice_line(beat_type, focus, headline, engagement):
    prefix = {
        "decision": "Decision point.",
        "tension": "Big pot brewing.",
        "all_in": "All-in pressure.",
        "showdown": "Showdown.",
        "winner": "Hand complete.",
        "lounge": "From the AI lounge.",
        "format_change": "Format shift coming.",
        "intermission": "Night City recap.",
    }.get(beat_type, "")
    line = " ".join(part for part in (prefix, focus) if part).strip()
    if not line:
        line = headline or engagement.get("prompt", "")
    return _safe_engagement_text(line, "", 180)


def _safe_engagement_text(value, fallback, limit):
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        text = fallback
    for forbidden in ("deposit", "cash out", "spin again"):
        text = re.sub(forbidden, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -·")
    if not text:
        text = fallback
    return text[: max(1, int(limit))]


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
