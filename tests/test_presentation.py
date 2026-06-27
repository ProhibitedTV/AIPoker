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
    assert result["chip_leader"] == "atlas"
    assert result["profile_signals"]["vega"]["risk_appetite"] == 78


def test_presentation_decision_mode_explains_call_price():
    players = base_players()
    players[1]["next_to_act"] = True
    players[1]["legal_actions"] = [{"action": "fold"}, {"action": "call", "amount": 120}, {"action": "raise"}]
    result = snapshot(players)
    assert result["mode"] == "decision"
    assert result["spotlight_seat_ids"] == ["vega"]
    assert "120 chips" in result["explainer"]


def test_presentation_big_pot_mode():
    result = snapshot(pot=520)
    assert result["mode"] == "big_pot"
    assert result["visual_intensity"] >= 70


def test_presentation_all_in_mode_beats_big_pot():
    players = base_players()
    players[0]["all_in"] = True
    result = snapshot(players, pot=1000)
    assert result["mode"] == "all_in"
    assert result["spotlight_seat_ids"] == ["atlas"]


def test_presentation_showdown_mode_before_award():
    result = snapshot(stage="Showdown")
    assert result["mode"] == "showdown"
    assert "Best five-card" in result["explainer"]


def test_presentation_recap_for_fold_win_and_split_pot():
    players = base_players()
    players[0]["action"] = "Won 480"
    result = snapshot(players, stage="Showdown", pot=0, commentary=["Atlas wins 480 with Uncontested."])
    assert result["mode"] == "recap"
    assert result["recap"]["winners"][0]["name"] == "Atlas"
    assert result["recap"]["amount"] == 480

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
    assert result["bumper"]["responsible_label"]

    disabled = snapshot(players, stage="Showdown", hand_number=3, casino_bumpers_enabled=False)
    assert not disabled["bumper"]["enabled"]


def test_casino_bumper_pot_reels_for_big_and_split_pots():
    players = base_players()
    players[0]["action"] = "Won 520"
    big = snapshot(players, stage="Showdown", hand_number=1, commentary=["Atlas wins 520."])
    assert big["bumper"]["kind"] == "pot_reels"
    assert big["bumper"]["stats"]["amount"] == 520

    players[1]["action"] = "Won 120"
    split = snapshot(players, stage="Showdown", hand_number=1, commentary=["Atlas and Vega share the pot."])
    assert split["bumper"]["kind"] == "pot_reels"
    assert split["bumper"]["stats"]["winner_count"] == 2


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

    players = base_players()
    players[0]["chips"] = 3100
    players[1]["action"] = "Won 120"
    leader = snapshot(players, stage="Showdown", hand_number=5, commentary=["Vega wins 120."])
    assert leader["bumper"]["kind"] == "chip_leader"
    assert leader["bumper"]["stats"]["leader"] == "Atlas"

    next_format = snapshot(
        stage="Showdown",
        tournament={"number": 1, "level": 5, "hands_remaining": 1, "complete": True, "winner": "vega"},
        variety={"enabled": True, "title": "Turbo Pressure Sit & Go", "hands_remaining": 1, "tempo": "turbo"},
    )
    assert next_format["bumper"]["kind"] == "next_format"
