import json
from types import SimpleNamespace

from casino_program import (
    CasinoProgram,
    RESPONSIBLE_LABEL,
    blackjack_value,
    baccarat_value,
    play_baccarat_round,
    play_blackjack_round,
)


def player(pid, name):
    return SimpleNamespace(
        id=pid,
        name=name,
        profile=SimpleNamespace(
            id=pid,
            persona=f"{name} casino persona",
            color="#65f7ff",
        ),
    )


def test_blackjack_round_dealer_behavior_and_bankroll_deltas():
    players = [player("atlas", "Atlas"), player("vega", "Vega")]
    deck = [
        (14, "spades"),
        (13, "hearts"),
        (10, "clubs"),
        (6, "hearts"),
        (9, "clubs"),
        (7, "diamonds"),
        (4, "spades"),
        (5, "clubs"),
    ]
    result = play_blackjack_round(
        players,
        {"atlas": 5000, "vega": 5000},
        deck=deck,
        unit=100,
    )
    assert blackjack_value([(14, "spades"), (13, "hearts")]) == 21
    assert result["dealer"]["total"] == 21
    assert result["deltas"] == {"atlas": 150, "vega": -100}
    assert sum(result["deltas"].values()) + result["house_delta"] == 0
    assert result["participants"][0]["outcome"] == "blackjack"
    assert "beat the dealer" in result["outcome"]["headline"]


def test_baccarat_third_card_rule_and_player_side_outcome():
    players = [player("atlas", "Atlas"), player("vega", "Vega")]
    deck = [
        (2, "hearts"),
        (3, "clubs"),
        (4, "diamonds"),
        (2, "spades"),
        (4, "hearts"),
    ]
    result = play_baccarat_round(
        players,
        {"atlas": 5000, "vega": 5000},
        deck=deck,
        unit=100,
        round_id=2,
    )
    assert baccarat_value([(2, "hearts"), (3, "clubs"), (4, "hearts")]) == 9
    assert result["player_total"] == 9
    assert result["banker_total"] == 6
    assert result["winning_side"] == "player"
    assert result["deltas"] == {"atlas": 100, "vega": 100}
    assert sum(result["deltas"].values()) + result["house_delta"] == 0


def test_casino_program_emits_replayable_events_and_state_shape():
    program = CasinoProgram(
        [player("atlas", "Atlas"), player("vega", "Vega")],
        rng_seed=12,
        blocks=[
            {
                "id": "blackjack_room",
                "active_game": "blackjack",
                "title": "Blackjack Room",
                "duration_rounds": 1,
                "visual_skin": "chrome_blackjack",
                "host_intro": "Blackjack room opens.",
                "viewer_hook": "Watch the dealer.",
            }
        ],
    )
    events = []
    program.advance(7, emit=lambda event_type, message="", **details: events.append({"type": event_type, **details}))
    snapshot = program.snapshot()
    assert snapshot["schema_version"] == 1
    assert snapshot["active_game"] == "blackjack"
    assert snapshot["program_block"]["title"] == "Blackjack Room"
    assert snapshot["round_id"] == 1
    assert snapshot["responsible_label"] == RESPONSIBLE_LABEL
    assert {"casino_block_start", "casino_round_start", "casino_card", "casino_decision", "casino_outcome", "casino_bankroll_update", "casino_host_line"} <= {event["type"] for event in events}
    for participant_id, delta in snapshot["outcome"]["deltas"].items():
        assert snapshot["fictional_bankrolls"][participant_id] == 5000 + delta


def test_casino_prompt_context_does_not_leak_other_participants_or_viewer_analysis():
    program = CasinoProgram([player("atlas", "Atlas"), player("vega", "Vega")], rng_seed=4)
    program.force_fixture("blackjack")
    context = program.decision_context_for_player("atlas")
    encoded = json.dumps(context).lower()
    assert context["participant"]["id"] == "atlas"
    assert "vega" not in encoded
    assert "other_hands" not in encoded
    assert "dealer_hole" not in encoded
    assert "equity" not in encoded
    assert "viewer" not in encoded.replace("no viewer", "")
