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
    )
    return {
        "schema_version": PRESENTATION_SCHEMA_VERSION,
        "mode": mode,
        "spotlight_seat_ids": [item for item in spotlights if item],
        "headline": headline,
        "explainer": explainer,
        "recap": recap,
        "bumper": bumper,
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
    return {
        "schema_version": 1,
        "mode": display_mode,
        "kicker": kicker,
        "headline": _safe_engagement_text(headline, "Live table", 96),
        "subhead": _safe_engagement_text(explainer, "The next key beat will appear here.", 150),
        "modules": modules,
        "active_module": active_module,
        "ticker_items": _lower_third_ticker_items(players, action_history, commentary),
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


def _lower_third_ticker_items(players, action_history, commentary):
    items = []
    for action in list(action_history or [])[-4:]:
        seat = action.get("seat")
        player = next((item for item in players if item.get("seat") == seat), None)
        name = (player or {}).get("name") or f"Seat {seat}"
        amount = int(action.get("amount", 0) or 0)
        copy = f"{name} {_plain_action(action.get('action'))}"
        if amount:
            copy = f"{copy} {amount:,}"
        items.append(copy)
    for line in list(commentary or [])[-2:]:
        text = _safe_engagement_text(line, "", 110)
        if text and text not in items:
            items.append(text)
    return items[-5:]


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
