import json
from pathlib import Path
import random
import tempfile

from game import PokerGame
from metrics import MetricsStore


def passive(context):
    names = {item["action"] for item in context["legal_actions"]}
    return "check" if "check" in names else "call"


def test_multiway_and_heads_up_action_order():
    order = []

    def remember(context):
        order.append((context["street"], context["player"]["seat"]))
        return passive(context)

    game = PokerGame(4, decision_provider=remember, rng_seed=10)
    game.play_pre_flop()
    assert [seat for street, seat in order if street == "pre-flop"] == [3, 0, 1, 2]
    game.play_flop()
    assert [seat for street, seat in order if street == "flop"] == [1, 2, 3, 0]

    order.clear()
    heads_up = PokerGame(2, decision_provider=remember, rng_seed=11)
    heads_up.play_pre_flop()
    assert heads_up.dealer_position == 0
    assert heads_up.small_blind_position == 0
    assert heads_up.big_blind_position == 1
    assert [seat for street, seat in order if street == "pre-flop"] == [0, 1]
    heads_up.play_flop()
    assert [seat for street, seat in order if street == "flop"] == [1, 0]


def test_legal_actions_enforce_call_minimum_raise_and_closed_action():
    game = PokerGame(2, decision_provider=passive)
    for player in game.players:
        player.reset_for_next_round()
    game.players[0].current_bet = 10
    game.players[0].chips = 990
    game.players[1].current_bet = 20

    legal = {item["action"]: item for item in game.legal_actions(0, current_bet=20, last_full_raise=20)}
    assert "check" not in legal
    assert legal["call"]["amount"] == 10
    assert legal["raise"]["min_target"] == 40

    game.players[0].acted_since_full_raise = True
    closed = {item["action"] for item in game.legal_actions(0, current_bet=20, last_full_raise=20)}
    assert closed == {"fold", "call"}

    game.players[0].chips = 5
    short = {item["action"] for item in game.legal_actions(0, current_bet=20, last_full_raise=20)}
    assert short == {"fold", "call", "all_in"}


def test_short_opening_all_in_can_be_completed_and_short_bb_keeps_full_bring_in():
    game = PokerGame(3, decision_provider=passive)
    for player in game.players:
        player.reset_for_next_round()
    game.players[0].current_bet = 10
    game.players[0].chips = 0
    game.players[0].all_in = True
    legal = {
        item["action"]: item
        for item in game.legal_actions(1, current_bet=10, last_full_raise=20, last_full_bet_level=0)
    }
    assert legal["raise"]["min_target"] == 20

    captured = []

    def inspect_first(context):
        captured.append(context)
        return passive(context)

    short_blind = PokerGame(3, starting_chips=1000, decision_provider=inspect_first)
    short_blind.players[2].chips = 5  # seat 2 is the first hand's big blind
    short_blind.play_pre_flop()
    first = captured[0]
    assert first["to_call"] == 20
    assert next(item for item in first["legal_actions"] if item["action"] == "raise")["min_target"] == 40


def test_single_short_all_in_does_not_reopen_but_cumulative_short_raises_do():
    observations = []
    counts = {}

    def scripted(context):
        seat = context["player"]["seat"]
        counts[seat] = counts.get(seat, 0) + 1
        legal = {item["action"]: item for item in context["legal_actions"]}
        observations.append((seat, counts[seat], set(legal)))
        if seat == 0 and counts[seat] == 1:
            return {"action": "raise", "amount": 100}
        if seat == 1:
            return {"action": "all_in"}
        if seat == 2:
            return {"action": "all_in"}
        return passive(context)

    game = PokerGame(3, starting_chips=1000, decision_provider=scripted, rng_seed=2)
    game.players[1].chips = 150
    game.players[2].chips = 200
    game.play_pre_flop()

    # Two +50 short raises cumulatively reach the prior full raise amount,
    # so seat 0 is allowed to raise when action returns.
    seat_zero_second = next(legal for seat, count, legal in observations if seat == 0 and count == 2)
    assert "raise" in seat_zero_second


def test_side_pots_uncalled_return_and_independent_winners():
    game = PokerGame(3, starting_chips=300, decision_provider=passive)
    game.hand_in_progress = True
    game.dealer_position = 2
    contributions = [100, 200, 300]
    for player, contribution in zip(game.players, contributions):
        player.reset_for_next_round()
        player.chips = 0
        player.total_committed = contribution
        player.current_bet = contribution
    game.players[0].hand = [(14, "hearts"), (13, "hearts")]
    game.players[1].hand = [(9, "spades"), (9, "diamonds")]
    game.players[2].hand = [(8, "spades"), (8, "diamonds")]
    game.community_cards = [
        (12, "hearts"), (11, "hearts"), (10, "hearts"), (2, "clubs"), (3, "diamonds")
    ]
    game.pot = 600
    game._opening_chips = {player.name: contribution for player, contribution in zip(game.players, contributions)}

    game.determine_winner()

    assert [player.chips for player in game.players] == [300, 200, 100]
    assert [pot["amount"] for pot in game.pots] == [300, 200]
    assert sum(player.chips for player in game.players) == 600


def test_folded_contributions_remain_dead_money_but_never_win_a_pot():
    game = PokerGame(3, decision_provider=passive)
    contributions = [50, 100, 100]
    for player, contribution in zip(game.players, contributions):
        player.reset_for_next_round()
        player.total_committed = contribution
    game.players[1].folded = True
    game.players[1].is_active = False
    game.pot = 250
    pots = game.build_side_pots()
    assert [pot["amount"] for pot in pots] == [150, 100]
    assert game.players[1].id not in pots[0]["eligible"]
    assert pots[1]["eligible"] == [game.players[2].id]


def test_burn_cards_and_deck_uniqueness_through_a_complete_hand():
    game = PokerGame(6, decision_provider=passive, rng_seed=22)
    game.play_hand()
    visible = [card for player in game.players for card in player.hand] + game.community_cards + game.deck.burned
    assert len(game.deck.burned) == 3
    assert len(visible) == 20
    assert len(set(visible)) == len(visible)
    assert len(game.deck.cards) == 32


def test_actor_prompt_context_is_private_but_viewer_state_is_omniscient():
    captured = []

    def inspect_context(context):
        captured.append(context)
        return passive(context)

    game = PokerGame(4, decision_provider=inspect_context, rng_seed=7)
    game.play_pre_flop()
    context = captured[0]
    assert len(context["player"]["hole_cards"]) == 2
    assert all("hole_cards" not in opponent for opponent in context["players"])
    assert "equity" not in context
    snapshot = game.state_snapshot()
    assert all(len(player["hole_cards"]) == 2 for player in snapshot["players"])
    assert snapshot["schema_version"] == 2


def test_modern_provider_with_optional_arguments_receives_full_context():
    captured = []

    def modern(context, optional_retry_count=2):
        captured.append((context, optional_retry_count))
        return passive(context)

    game = PokerGame(2, decision_provider=modern)
    game.play_pre_flop()
    assert isinstance(captured[0][0], dict)
    assert "legal_actions" in captured[0][0]
    assert captured[0][1] == 2


def test_checkpoint_restores_only_completed_hand_state():
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / "checkpoint.json"
        game = PokerGame(2, decision_provider=passive, checkpoint_path=checkpoint, rng_seed=12)
        game.play_hand()
        chips = [player.chips for player in game.players]
        restored = PokerGame(2, decision_provider=passive, checkpoint_path=checkpoint, rng_seed=99)
        assert restored.hand_number == 1
        assert [player.chips for player in restored.players] == chips
        assert restored.stage == "Restored"


def test_tournament_levels_big_blind_ante_and_restart():
    game = PokerGame(4, starting_chips=2000, mode="tournament", decision_provider=passive, hands_per_level=8)
    game.tournament_hand_number = 25
    game._apply_tournament_level()
    assert (game.small_blind, game.big_blind, game.ante) == (40, 80, 80)

    game.tournament_complete = True
    game.tournament_winner = game.players[0].id
    game.players[1].chips = 0
    game.players[1].eliminated = True
    game._ensure_playable_table()
    assert not game.tournament_complete
    assert all(player.chips == 2000 for player in game.players)
    assert all(not player.eliminated for player in game.players)


def test_cash_reloads_only_zero_stack_at_hand_boundary():
    game = PokerGame(3, starting_chips=2000, mode="cash", decision_provider=passive)
    game.players[0].chips = 0
    game.players[1].chips = 5
    game._ensure_playable_table()
    assert game.players[0].chips == 2000
    assert game.players[1].chips == 5


def test_metrics_v1_migrates_with_backup_and_new_fields():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "leaderboard.json"
        path.write_text(json.dumps({"version": 1, "hands_played": 3, "players": {"AI Player 1": {"hands_played": 3, "hands_won": 1}}}), encoding="utf-8")
        store = MetricsStore(path)
        snapshot = store.snapshot()
        assert snapshot["version"] == 2
        assert snapshot["players"]["AI Player 1"]["vpip_rate"] == 0.0
        assert path.with_suffix(".json.v1.bak").exists()

        game = PokerGame(
            2,
            metrics_store=store,
            profiles=[
                {"id": "atlas", "name": "Atlas"},
                {"id": "vega", "name": "Vega"},
            ],
            decision_provider=passive,
        )
        assert game.players[0].total_rounds == 3
        assert "Atlas" in store.snapshot()["players"]
        assert "AI Player 1" not in store.snapshot()["players"]


def test_randomized_cash_soak_preserves_chips_and_legal_progress():
    rng = random.Random(314159)

    def random_legal(context):
        legal = context["legal_actions"]
        choice = rng.choice(legal)
        result = {"action": choice["action"]}
        if choice["action"] in {"bet", "raise"}:
            result["amount"] = rng.randint(choice["min_target"], choice["max_target"])
        return result

    game = PokerGame(6, starting_chips=2000, decision_provider=random_legal, rng_seed=2718)
    for _ in range(250):
        before = sum(player.chips for player in game.players)
        game.play_hand()
        after = sum(player.chips for player in game.players)
        assert after == before
        assert game.pot == 0
        assert all(player.chips >= 0 for player in game.players)
        # Re-seat busted test bots outside the measured hand so every hand has
        # a fixed conservation boundary.
        for player in game.players:
            if player.chips == 0:
                player.chips = game.starting_chips
