from presentation import build_presentation_snapshot


def base_players():
    return [
        {
            "id": "atlas",
            "name": "Atlas",
            "chips": 2200,
            "active": True,
            "folded": False,
            "eliminated": False,
            "all_in": False,
            "action": "Waiting",
            "legal_actions": [],
            "hand_label": "Pair of aces",
            "hand_commitment": 0,
        },
        {
            "id": "vega",
            "name": "Vega",
            "chips": 1800,
            "active": True,
            "folded": False,
            "eliminated": False,
            "all_in": False,
            "action": "Waiting",
            "legal_actions": [],
            "hand_label": "King high",
            "hand_commitment": 0,
        },
    ]


def snapshot(players=None, **overrides):
    payload = {
        "players": players or base_players(),
        "stage": "Pre-Flop",
        "pot": 40,
        "blinds": {"small": 10, "big": 20, "ante": 0},
        "tournament": {"number": 1, "level": 1, "hands_remaining": 8, "complete": False},
        "action_history": [],
        "commentary": [],
        "personality_arcs": {
            "atlas": {"style": "Disciplined Grinder", "confidence": 61, "tilt": 4, "risk_appetite": 28},
            "vega": {"style": "Pressure Artist", "confidence": 47, "tilt": 18, "risk_appetite": 78},
        },
        "program": {"segment": "Live Sit & Go", "detail": "Level 1 · 8 hands until blinds move."},
        "hand_number": 1,
    }
    payload.update(overrides)
    return build_presentation_snapshot(**payload)


def test_presentation_table_mode_when_no_one_is_acting():
    result = snapshot()
    assert result["schema_version"] == 1
    assert result["mode"] == "table"
    assert result["showrunner_schema_version"] == 1
    assert result["beat_type"] == "table"
    assert result["viewer_focus"]
    assert result["voice_cue"]["enabled"]
    assert result["non_reader_labels"]["enabled"]
    assert result["audience_hook"]
    assert result["chip_leader"] == "atlas"
    assert result["lower_third"]["schema_version"] == 1
    assert result["lower_third"]["mode"] == "table"
    assert result["lower_third"]["kicker"] == "LIVE TABLE"
    assert result["lower_third"]["active_module"] == "pot"
    assert any(module["id"] == "standings" for module in result["lower_third"]["modules"])
    assert result["profile_signals"]["vega"]["risk_appetite"] == 78
    assert result["engagement"]["enabled"]
    assert "Call out the next winner" in result["engagement"]["prompt"]
    assert "no wagers" in result["engagement"]["safe_label"]
    assert result["venue"]["schema_version"] == 1
    assert result["venue"]["enabled"]
    assert "Simulation District" in result["venue"]["header_label"]
    assert result["venue"]["safe_label"] == "simulation-only venue skin"
    assert result["scene_state"]["schema_version"] == 1
    assert result["scene_state"]["state"] == "live_hand"
    assert result["scene_state"]["visible"] is False


def test_stream_scene_states_cover_standby_break_and_table_reset():
    standby = snapshot(stage="Waiting", hand_number=0, pot=0, commentary=[])
    assert standby["scene_state"]["state"] == "standby"
    assert standby["scene_state"]["visible"] is True
    assert "warming up" in standby["scene_state"]["headline"].lower()

    hand_boundary = snapshot(stage="Waiting", hand_number=4, pot=0, commentary=[])
    assert hand_boundary["scene_state"]["state"] == "live_hand"
    assert hand_boundary["scene_state"]["visible"] is False

    players = base_players()
    players[0]["action"] = "Won 120"
    break_state = snapshot(players, stage="Showdown", hand_number=3, pot=0, commentary=["Atlas wins 120."])
    assert break_state["scene_state"]["state"] == "break"
    assert break_state["scene_state"]["visible"] is True
    assert "FICTIONAL" in break_state["scene_state"]["safe_label"]

    reset = snapshot(stage="Waiting", hand_number=9, pot=0, commentary=["Tournament table reset begins."])
    assert reset["scene_state"]["state"] == "table_reset"
    assert reset["scene_state"]["visible"] is True


def test_presentation_venue_theme_uses_public_lounge_location():
    result = snapshot(
        lounge={
            "enabled": True,
            "venue": {
                "name": "Black Circuit Lounge",
                "district": "Dealer's Row",
                "booth": "private server cage",
                "lighting": "gold chip LEDs",
                "weather": "static drizzle",
            },
            "venue_zone": "private server cage",
            "service_bot": "Mira-7",
            "table_mood": "Midnight circuit",
            "pressure_index": 64,
            "atmosphere_line": "Mira-7 sweeps gold chip LEDs through the private server cage.",
        }
    )
    venue = result["venue"]
    assert venue["name"] == "Black Circuit Lounge"
    assert "Dealer's Row" in venue["header_label"]
    assert "private server cage" in venue["table_label"]
    assert "gold chip LEDs" in venue["footer_line"]
    assert venue["status_chip"] == "Midnight circuit // pressure 64%"
    assert venue["signs"]["right"] == "Mira-7 ONLINE"


def test_presentation_decision_mode_explains_call_price():
    players = base_players()
    players[1]["next_to_act"] = True
    players[1]["legal_actions"] = [{"action": "fold"}, {"action": "call", "amount": 120}, {"action": "raise"}]
    result = snapshot(players)
    assert result["mode"] == "decision"
    assert result["beat_type"] == "decision"
    assert result["spotlight_seat_ids"] == ["vega"]
    assert "120 chips" in result["explainer"]
    assert "120" in result["viewer_focus"]
    assert result["non_reader_labels"]["items"][0]["label"] == "TO CALL"
    assert result["lower_third"]["mode"] == "decision"
    assert result["lower_third"]["active_module"] == "decision"
    assert result["lower_third"]["modules"][0]["value"] == "120"
    assert "Decision point" in result["voice_cue"]["line"]
    assert "Vega" in result["engagement"]["prompt"]
    assert "call, raise, or fold" in result["engagement"]["prompt"]


def test_presentation_big_pot_mode():
    result = snapshot(pot=520)
    assert result["mode"] == "big_pot"
    assert result["beat_type"] == "tension"
    assert result["visual_intensity"] >= 70


def test_presentation_all_in_mode_beats_big_pot():
    players = base_players()
    players[0]["all_in"] = True
    result = snapshot(players, pot=1000)
    assert result["mode"] == "all_in"
    assert result["beat_type"] == "all_in"
    assert result["spotlight_seat_ids"] == ["atlas"]
    assert result["lower_third"]["mode"] == "all_in"
    assert result["lower_third"]["active_module"] == "equity"


def test_presentation_showdown_mode_before_award():
    result = snapshot(stage="Showdown")
    assert result["mode"] == "showdown"
    assert result["beat_type"] == "showdown"
    assert "Best five-card" in result["explainer"]
    assert result["lower_third"]["mode"] == "showdown"
    assert result["lower_third"]["active_module"] == "equity"


def test_presentation_recap_for_fold_win_and_split_pot():
    players = base_players()
    players[0]["action"] = "Won 480"
    result = snapshot(players, stage="Showdown", pot=0, commentary=["Atlas wins 480 with Uncontested."])
    assert result["mode"] == "recap"
    assert result["beat_type"] in {"winner", "intermission"}
    assert result["recap"]["winners"][0]["name"] == "Atlas"
    assert result["recap"]["amount"] == 480
    assert result["lower_third"]["mode"] == "winner"
    assert result["lower_third"]["kicker"] == "WINNER"

    players[1]["action"] = "Won 480"
    split = snapshot(players, stage="Showdown", pot=0, commentary=["Atlas and Vega share the pots."])
    assert split["mode"] == "recap"
    assert len(split["recap"]["winners"]) == 2


def test_presentation_tournament_trophy_is_recap():
    result = snapshot(
        stage="Showdown",
        tournament={"number": 1, "level": 5, "hands_remaining": 1, "complete": True, "winner": "vega"},
    )
    assert result["mode"] == "recap"
    assert result["spotlight_seat_ids"] == ["vega"]
    assert "sit-and-go" in result["explainer"]


def test_casino_bumper_winner_jackpot_and_disabled_state():
    players = base_players()
    players[0]["action"] = "Won 120"
    result = snapshot(players, stage="Showdown", hand_number=3, commentary=["Atlas wins 120."])
    assert result["bumper"]["enabled"]
    assert result["bumper"]["kind"] == "winner_jackpot"
    assert result["bumper"]["visual_family"] == "winner_cards"
    assert result["bumper"]["style"] == "night_city_recaps"
    assert result["bumper"]["theme"] == "Night City casino recap"
    assert "previous poker hand" in result["bumper"]["relevance"]
    assert result["engagement"]["context"] == "Intermission prompt"
    assert "Atlas" in result["engagement"]["prompt"]
    assert result["bumper"]["responsible_label"]

    disabled = snapshot(players, stage="Showdown", hand_number=3, casino_bumpers_enabled=False)
    assert not disabled["bumper"]["enabled"]


def test_engagement_copy_is_sanitized_and_can_be_disabled():
    result = snapshot(
        engagement_follow_message="Follow now and deposit",
        engagement_chat_prompt="spin again and cash out",
    )
    combined = f"{result['engagement']['follow']} {result['engagement']['prompt']}".lower()
    assert "deposit" not in combined
    assert "spin again" not in combined
    assert "cash out" not in combined

    disabled = snapshot(engagement_enabled=False)
    assert not disabled["engagement"]["enabled"]


def test_showrunner_can_be_disabled_and_voice_cues_removed():
    players = base_players()
    players[0]["next_to_act"] = True
    players[0]["legal_actions"] = [{"action": "check"}, {"action": "bet"}]
    result = snapshot(players, showrunner_enabled=False, voice_cues_enabled=False)

    assert result["showrunner_schema_version"] == 1
    assert result["beat_type"] == "table"
    assert not result["voice_cue"]["enabled"]
    assert not result["non_reader_labels"]["enabled"]


def test_casino_bumper_pot_reels_for_big_and_split_pots():
    players = base_players()
    players[0]["action"] = "Won 520"
    big = snapshot(players, stage="Showdown", hand_number=1, commentary=["Atlas wins 520."])
    assert big["bumper"]["kind"] == "pot_reels"
    assert big["bumper"]["visual_family"] == "poker_reels"
    assert big["bumper"]["stats"]["amount"] == 520

    players[1]["action"] = "Won 120"
    split = snapshot(players, stage="Showdown", hand_number=1, commentary=["Atlas and Vega share the pot."])
    assert split["bumper"]["kind"] == "pot_reels"
    assert split["bumper"]["stats"]["winner_count"] == 2

    all_in = snapshot(
        players,
        stage="Showdown",
        hand_number=2,
        commentary=["Atlas wins the all-in pot."],
        action_history=[{"seat": 0, "action": "all_in", "amount": 2000}],
    )
    assert all_in["bumper"]["kind"] == "pot_reels"
    assert all_in["bumper"]["visual_family"] == "equity_wheel"
    assert "All-in result" in all_in["bumper"]["relevance"]


def test_casino_bumper_hot_streak_chip_leader_and_next_format():
    players = base_players()
    players[0]["action"] = "Won 120"
    hot = snapshot(
        players,
        stage="Showdown",
        hand_number=1,
        commentary=["Atlas wins 120."],
        personality_arcs={"atlas": {"confidence": 75}, "vega": {"confidence": 20}},
    )
    assert hot["bumper"]["kind"] == "hot_streak"
    assert hot["bumper"]["visual_family"] == "momentum_meter"

    players = base_players()
    players[0]["chips"] = 3100
    players[1]["action"] = "Won 120"
    leader = snapshot(players, stage="Showdown", hand_number=5, commentary=["Vega wins 120."])
    assert leader["bumper"]["kind"] == "chip_leader"
    assert leader["bumper"]["visual_family"] == "standings_ladder"
    assert leader["bumper"]["stats"]["leader"] == "Atlas"

    next_format = snapshot(
        stage="Showdown",
        tournament={"number": 1, "level": 5, "hands_remaining": 1, "complete": True, "winner": "vega"},
        variety={"enabled": True, "title": "Turbo Pressure Sit & Go", "hands_remaining": 1, "tempo": "turbo"},
    )
    assert next_format["bumper"]["kind"] == "next_format"
    assert next_format["bumper"]["visual_family"] == "format_marquee"


def test_lower_third_casino_room_mode_uses_programming_state():
    result = snapshot(
        casino={
            "enabled": True,
            "active_game": "blackjack",
            "program_block": {
                "title": "Blackjack Room",
                "viewer_hook": "Root for the clean twenty-one.",
                "visual_skin": "chrome_blackjack",
            },
            "spectacle_cue": {
                "headline": "Blackjack room opens",
                "caption": "Dealer shows pressure in the side room.",
            },
        }
    )
    assert result["lower_third"]["mode"] == "casino_room"
    assert result["lower_third"]["kicker"] == "NEXT ROOM"
    assert result["lower_third"]["active_module"] == "casino"
    assert "Blackjack" in result["lower_third"]["headline"]
