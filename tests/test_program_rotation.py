from pathlib import Path
import tempfile

from game import PokerGame


SEGMENTS = [
    {
        "id": "cash_standard",
        "title": "Standard Cash",
        "mode": "cash",
        "duration_hands": 2,
        "small_blind": 10,
        "big_blind": 20,
        "ante": 0,
        "starting_chips": 2000,
        "tempo": "steady",
        "table_skin": "championship",
        "strategy_hint": "Play ordinary cash poker.",
    },
    {
        "id": "cash_ante",
        "title": "Ante Cash",
        "mode": "cash",
        "duration_hands": 2,
        "small_blind": 15,
        "big_blind": 30,
        "ante": 5,
        "starting_chips": 2500,
        "tempo": "splash",
        "table_skin": "splash",
        "strategy_hint": "Antes are live; steal prices improve.",
    },
    {
        "id": "turbo_sng",
        "title": "Turbo Sit & Go",
        "mode": "tournament",
        "duration_hands": 2,
        "hands_per_level": 3,
        "tempo": "turbo",
        "table_skin": "turbo",
        "strategy_hint": "Blind pressure arrives quickly.",
    },
]


def test_cash_rotation_changes_actual_blinds_antes_and_state():
    game = PokerGame(
        2,
        mode="cash",
        auto_restore=False,
        variety_rotation_enabled=True,
        variety_segments=SEGMENTS,
    )
    assert game.mode == "cash"
    assert (game.small_blind, game.big_blind, game.ante) == (10, 20, 0)
    assert game.variety_snapshot()["segment_id"] == "cash_standard"

    game.hand_number = 2
    game._maybe_rotate_variety_segment()

    assert game.mode == "cash"
    assert (game.small_blind, game.big_blind, game.ante) == (15, 30, 5)
    assert [player.chips for player in game.players] == [2500, 2500]
    state = game.state_snapshot()
    assert state["variety"]["segment_id"] == "cash_ante"
    assert state["program"]["segment"] == "Ante Cash"


def test_rotation_waits_for_tournament_completion_before_switching():
    game = PokerGame(
        4,
        mode="tournament",
        auto_restore=False,
        variety_rotation_enabled=True,
        variety_segments=SEGMENTS,
    )
    assert game.variety_snapshot()["segment_id"] == "turbo_sng"
    game.hand_number = 2
    game.tournament_hand_number = 2
    game.tournament_complete = False

    game._maybe_rotate_variety_segment()

    assert game.variety_snapshot()["segment_id"] == "turbo_sng"
    assert game.variety_snapshot()["rotation_delayed"]

    game.tournament_complete = True
    game._maybe_rotate_variety_segment()

    assert game.variety_snapshot()["segment_id"] == "cash_standard"
    assert game.mode == "cash"


def test_ai_decision_context_receives_public_table_program_hint_only():
    captured = {}

    def inspect_context(context):
        captured.update(context)
        return "check"

    game = PokerGame(
        2,
        mode="cash",
        auto_restore=False,
        decision_provider=inspect_context,
        variety_rotation_enabled=True,
        variety_segments=SEGMENTS,
        rng_seed=4,
    )
    game.play_pre_flop()

    assert captured["table_program"]["segment_id"] == "cash_standard"
    assert captured["strategy_hint"]["segment_hint"] == "Play ordinary cash poker."
    assert "hole_cards" not in captured["players"][0]


def test_checkpoint_restores_active_rotation_segment():
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / "checkpoint.json"
        game = PokerGame(
            2,
            mode="cash",
            auto_restore=False,
            checkpoint_path=checkpoint,
            variety_rotation_enabled=True,
            variety_segments=SEGMENTS,
        )
        game.hand_number = 2
        game._maybe_rotate_variety_segment()
        game.save_checkpoint()

        restored = PokerGame(
            2,
            mode="cash",
            checkpoint_path=checkpoint,
            variety_rotation_enabled=True,
            variety_segments=SEGMENTS,
        )

        assert restored.variety_snapshot()["segment_id"] == "cash_ante"
        assert (restored.small_blind, restored.big_blind, restored.ante) == (15, 30, 5)
