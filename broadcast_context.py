"""Deterministic broadcast context for league, story, and character layers."""

from __future__ import annotations

from datetime import datetime, timezone


def build_broadcast_context(metrics=None, players=None, mode="cash", tournament=None, action_history=None, hand_number=0, stage="", variety=None):
    """Return overlay-safe context derived only from public state and persisted metrics."""

    metrics = metrics or {}
    players = players or []
    action_history = list(action_history or [])
    variety = variety or {}
    league = build_league_snapshot(metrics, players, mode, tournament, hand_number, variety=variety)
    storylines = build_storylines(metrics, players, action_history, tournament, variety=variety)
    personalities = build_personality_arcs(metrics, players)
    program = build_program_segment(mode, tournament, stage, hand_number, storylines, variety=variety)
    return {
        "program": program,
        "league": league,
        "storylines": storylines,
        "personality_arcs": personalities,
    }


def build_program_segment(mode, tournament, stage, hand_number, storylines, variety=None):
    stage_key = str(stage or "").lower()
    tournament = tournament or {}
    variety = variety or {}
    if tournament.get("complete"):
        segment = "Trophy Ceremony"
        detail = "Champion confirmed; next sit-and-go is queued."
    elif stage_key == "showdown":
        segment = "Showdown Desk"
        detail = "Cards are being compared and payouts are being audited."
    elif stage_key in {"paused", "recovering"}:
        segment = "Recovery Break"
        detail = "The table is restoring clean broadcast state."
    elif mode == "tournament":
        segment = "Live Sit & Go"
        detail = f"Level {tournament.get('level', 1)} · {tournament.get('hands_remaining', 0)} hands until blinds move."
    else:
        segment = "Cash Table Live"
        detail = "Fixed-stakes exhibition table with simulated chips."
    if variety.get("enabled") and variety.get("title") and stage_key not in {"showdown", "paused", "recovering"} and not tournament.get("complete"):
        segment = variety["title"]
        detail = f"{str(variety.get('tempo', 'standard')).title()} segment · {variety.get('viewer_explainer', detail)}"

    lead = storylines[0]["text"] if storylines else "Season context warming up."
    return {
        "segment": segment,
        "detail": detail,
        "clock": datetime.now(timezone.utc).strftime("%H:%M UTC"),
        "hand": int(hand_number or 0),
        "bumper": lead,
        "variety": {
            "segment_id": variety.get("segment_id"),
            "style": variety.get("style"),
            "tempo": variety.get("tempo"),
            "hands_remaining": variety.get("hands_remaining"),
        } if variety else None,
    }


def build_league_snapshot(metrics, players, mode, tournament, hand_number, variety=None):
    variety = variety or {}
    player_stats = metrics.get("players", {}) if isinstance(metrics, dict) else {}
    standings = []
    for player in players:
        stats = player_stats.get(player.get("name"), {})
        standings.append(
            {
                "id": player.get("id"),
                "name": player.get("name"),
                "chips": int(player.get("chips", 0)),
                "net_chips": int(stats.get("net_chips", 0)),
                "tournament_wins": int(stats.get("tournament_wins", 0)),
                "win_rate": float(stats.get("win_rate", player.get("win_percentage", 0.0) or 0.0)),
                "aggression": float(stats.get("aggression_factor", 0.0)),
            }
        )
    standings.sort(key=lambda row: (row["tournament_wins"], row["net_chips"], row["chips"]), reverse=True)
    records = _records_from_metrics(metrics, standings)
    recent_tournaments = list(metrics.get("tournaments", []))[-5:] if isinstance(metrics, dict) else []
    banners = [
        {
            "label": f"SNG {entry.get('number', '?')}",
            "winner": entry.get("winner", "Unknown"),
        }
        for entry in recent_tournaments
    ][-4:]
    return {
        "season": {
            "id": str(metrics.get("session_id", "local-season"))[:8] if isinstance(metrics, dict) else "local",
            "hand": int(hand_number or metrics.get("hands_played", 0) or 0) if isinstance(metrics, dict) else int(hand_number or 0),
            "hands_played": int(metrics.get("hands_played", 0)) if isinstance(metrics, dict) else 0,
            "tournaments_played": int(metrics.get("tournaments_played", 0)) if isinstance(metrics, dict) else 0,
            "mode": mode,
        },
        "standings": standings[:6],
        "records": records,
        "championship_banners": banners,
        "current_title": variety.get("title") if variety.get("enabled") and variety.get("title") else _current_title(mode, tournament),
    }


def build_storylines(metrics, players, action_history, tournament, variety=None):
    variety = variety or {}
    player_stats = metrics.get("players", {}) if isinstance(metrics, dict) else {}
    lines = []
    if variety.get("enabled") and variety.get("title"):
        lines.append(
            {
                "kind": "format",
                "title": "Format Rotation",
                "text": f"{variety.get('title')} is live: {variety.get('viewer_explainer', 'a fresh table style is underway')}",
            }
        )
    chip_leader = max(players, key=lambda player: int(player.get("chips", 0)), default=None)
    if chip_leader:
        lines.append(
            {
                "kind": "leader",
                "title": "Chip Leader",
                "text": f"{chip_leader.get('name')} leads the table with {int(chip_leader.get('chips', 0)):,} chips.",
            }
        )
    notable = list(metrics.get("notable_hands", []))[-1:] if isinstance(metrics, dict) else []
    if notable:
        entry = notable[-1]
        winners = ", ".join(entry.get("winners", []) or ["the table"])
        lines.append(
            {
                "kind": "record",
                "title": "Recent Fireworks",
                "text": f"{winners} dragged a {int(entry.get('pot', 0)):,}-chip notable pot.",
            }
        )
    aggressive = _top_player(player_stats, lambda stats: float(stats.get("aggression_factor", 0.0)))
    if aggressive:
        name, stats = aggressive
        lines.append(
            {
                "kind": "style",
                "title": "Pressure Seat",
                "text": f"{name} is setting the pace with {float(stats.get('aggression_factor', 0.0)):.2f} aggression.",
            }
        )
    hot = _top_player(player_stats, lambda stats: int(stats.get("current_streak", 0)))
    if hot and int(hot[1].get("current_streak", 0)) > 1:
        lines.append(
            {
                "kind": "streak",
                "title": "Hot Streak",
                "text": f"{hot[0]} has won {int(hot[1].get('current_streak', 0))} qualifying hands in a row.",
            }
        )
    recent_tournaments = list(metrics.get("tournaments", []))[-1:] if isinstance(metrics, dict) else []
    if recent_tournaments:
        winner = recent_tournaments[-1].get("winner", "Unknown")
        lines.append(
            {
                "kind": "champion",
                "title": "Last Champion",
                "text": f"{winner} owns the latest sit-and-go banner.",
            }
        )
    if action_history:
        action = action_history[-1]
        lines.append(
            {
                "kind": "action",
                "title": "Latest Action",
                "text": f"Seat {action.get('seat', '?')} {str(action.get('action', 'acts')).replace('_', ' ')}"
                + (f" for {int(action.get('amount', 0)):,}" if action.get("amount") else "."),
            }
        )
    if tournament and tournament.get("complete"):
        lines.insert(
            0,
            {
                "kind": "championship",
                "title": "Champion Crowned",
                "text": "The trophy ceremony is live while the next event loads.",
            },
        )
    while len(lines) < 3:
        fallback_index = len(lines) + 1
        lines.append(
            {
                "kind": "season",
                "title": f"Season Note {fallback_index}",
                "text": [
                    "Every hand updates permanent simulated-chip records.",
                    "Viewer odds are public analysis only; AI players never see opponent hole cards.",
                    "Local fallback policy keeps the table moving when a model is unavailable.",
                ][fallback_index - 1],
            }
        )
    return lines[:6]


def build_personality_arcs(metrics, players):
    player_stats = metrics.get("players", {}) if isinstance(metrics, dict) else {}
    arcs = {}
    for player in players:
        name = player.get("name")
        stats = player_stats.get(name, {})
        hands = max(1, int(stats.get("hands_played", 0)))
        pfr = float(stats.get("pfr_rate", 0.0))
        vpip = float(stats.get("vpip_rate", 0.0))
        aggression = float(stats.get("aggression_factor", 0.0))
        streak = int(stats.get("current_streak", 0))
        showdown = float(stats.get("showdown_win_rate", 0.0))
        risk = _clamp(round(pfr * 0.7 + aggression * 10 + int(stats.get("all_ins", 0)) * 1.5), 0, 100)
        confidence = _clamp(round(45 + streak * 8 + (showdown - 50) * 0.35), 0, 100)
        tilt = _clamp(round(abs(min(0, streak)) * 9 + max(0, 35 - showdown) * 0.45), 0, 100)
        lounge = player.get("lounge") or {}
        if lounge.get("enabled"):
            risk = _clamp(risk + int(lounge.get("risk_delta", 0) or 0), 0, 100)
            confidence = _clamp(confidence + max(0, int(lounge.get("focus_delta", 0) or 0)) // 2, 0, 100)
            tilt = _clamp(tilt + max(0, -int(lounge.get("focus_delta", 0) or 0)) + max(0, int(lounge.get("bluff_delta", 0) or 0)) // 4, 0, 100)
        style = _style_label(vpip, pfr, aggression)
        arc_events = []
        if stats.get("biggest_pot_won"):
            arc_events.append(f"Best pot: {int(stats.get('biggest_pot_won', 0)):,} chips")
        if stats.get("tournament_wins"):
            arc_events.append(f"{int(stats.get('tournament_wins', 0))} tournament banner(s)")
        if stats.get("longest_winning_streak"):
            arc_events.append(f"Longest heater: {int(stats.get('longest_winning_streak', 0))}")
        if lounge.get("enabled"):
            arc_events.append(
                f"Lounge: {lounge.get('drink')} · {lounge.get('service_level') or lounge.get('mood')} · {lounge.get('visual_tell')}"
            )
        arcs[player.get("id") or name] = {
            "name": name,
            "style": style,
            "confidence": confidence,
            "tilt": tilt,
            "risk_appetite": risk,
            "sample_hands": hands,
            "bio": f"{name} profiles as a {style.lower()} competitor in the current season.",
            "summary": _arc_summary(name, style, confidence, tilt, risk),
            "events": arc_events[:4],
        }
    return arcs


def _records_from_metrics(metrics, standings):
    player_stats = metrics.get("players", {}) if isinstance(metrics, dict) else {}
    notable = list(metrics.get("notable_hands", [])) if isinstance(metrics, dict) else []
    largest = max(notable, key=lambda entry: int(entry.get("pot", 0)), default={})
    tournament_wins = _top_player(player_stats, lambda stats: int(stats.get("tournament_wins", 0)))
    streak = _top_player(player_stats, lambda stats: int(stats.get("longest_winning_streak", 0)))
    aggression = _top_player(player_stats, lambda stats: float(stats.get("aggression_factor", 0.0)))
    net = standings[0] if standings else {}
    return {
        "largest_pot": {
            "amount": int(largest.get("pot", 0)),
            "winners": largest.get("winners", []),
            "hand": largest.get("hand"),
        },
        "most_tournament_wins": _record_entry(tournament_wins, "tournament_wins"),
        "longest_winning_streak": _record_entry(streak, "longest_winning_streak"),
        "most_aggressive": _record_entry(aggression, "aggression_factor"),
        "season_net_leader": {"name": net.get("name", "TBD"), "value": int(net.get("net_chips", 0) or 0)},
    }


def _record_entry(item, key):
    if not item:
        return {"name": "TBD", "value": 0}
    name, stats = item
    value = stats.get(key, 0)
    return {"name": name, "value": value}


def _top_player(player_stats, scorer):
    if not player_stats:
        return None
    return max(player_stats.items(), key=lambda item: scorer(item[1]), default=None)


def _current_title(mode, tournament):
    if mode == "tournament":
        tournament = tournament or {}
        return f"Sit & Go {tournament.get('number', 1)} · Level {tournament.get('level', 1)}"
    return "AI Poker League Cash Exhibition"


def _style_label(vpip, pfr, aggression):
    if aggression >= 2.2 or pfr >= 35:
        return "Pressure Artist"
    if vpip <= 22 and pfr <= 16:
        return "Disciplined Grinder"
    if vpip >= 42 and aggression < 1.2:
        return "Curious Caller"
    if 23 <= vpip <= 38 and 14 <= pfr <= 28:
        return "Balanced Contender"
    return "Adaptive Competitor"


def _arc_summary(name, style, confidence, tilt, risk):
    if tilt >= 65:
        mood = "needs a clean hand to reset the narrative"
    elif confidence >= 70:
        mood = "is playing with visible momentum"
    elif risk >= 70:
        mood = "keeps threatening stack-pressure moments"
    else:
        mood = "is holding a steady league posture"
    return f"{name} is a {style.lower()} and {mood}."


def _clamp(value, lower, upper):
    return max(lower, min(upper, int(value)))
