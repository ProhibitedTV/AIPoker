"""Night City casino programming layer for the OBS browser source.

This module intentionally keeps the non-poker casino rooms AI-only and
simulation-only.  The games create broadcast variety, public events, and
fictional bankroll drama; they never accept viewer input and never drive poker
rules or hidden poker information.
"""

from __future__ import annotations

from copy import deepcopy
import random
from typing import Callable, Iterable


RESPONSIBLE_LABEL = "SIMULATION ONLY · FICTIONAL BANKROLLS · NO REAL MONEY · NO VIEWER WAGERS"

CARD_SUITS = ("spades", "hearts", "diamonds", "clubs")
CARD_RANKS = tuple(range(2, 15))


def default_casino_blocks():
    """Return the default 24/7 programming loop for the OBS channel surface."""
    return [
        {
            "id": "main_poker",
            "active_game": "poker",
            "title": "Main Poker Table",
            "duration_rounds": 4,
            "visual_skin": "neon_felt",
            "host_intro": "Back to the main table: private cards, public pressure, AI egos.",
            "viewer_hook": "Watch who controls the next decision.",
            "safety_label": RESPONSIBLE_LABEL,
        },
        {
            "id": "blackjack_room",
            "active_game": "blackjack",
            "title": "Blackjack Room",
            "duration_rounds": 2,
            "visual_skin": "chrome_blackjack",
            "host_intro": "The side room opens: quick blackjack beats with fictional bankroll swings.",
            "viewer_hook": "Root for the clean twenty-one or the dealer bust.",
            "safety_label": RESPONSIBLE_LABEL,
        },
        {
            "id": "lounge_recap",
            "active_game": "lounge",
            "title": "Neon Lounge Recap",
            "duration_rounds": 1,
            "visual_skin": "holo_lounge",
            "host_intro": "The AIs cool their circuits while the board recaps the last run.",
            "viewer_hook": "Catch the rivalry heat before the next room opens.",
            "safety_label": RESPONSIBLE_LABEL,
        },
        {
            "id": "baccarat_pit",
            "active_game": "baccarat",
            "title": "Baccarat Pit",
            "duration_rounds": 2,
            "visual_skin": "magenta_baccarat",
            "host_intro": "Fast cards in the baccarat pit: banker, player, or tie on the neon rail.",
            "viewer_hook": "Pick a side for bragging rights before the reveal.",
            "safety_label": RESPONSIBLE_LABEL,
        },
        {
            "id": "high_roller",
            "active_game": "poker",
            "title": "High-Roller Spotlight",
            "duration_rounds": 2,
            "visual_skin": "gold_vip",
            "host_intro": "High-roller spotlight: bigger pots, louder reads, same fictional chips.",
            "viewer_hook": "Track the chip leader and the next big swing.",
            "safety_label": RESPONSIBLE_LABEL,
        },
        {
            "id": "rivalry_match",
            "active_game": "poker",
            "title": "Rivalry Heat",
            "duration_rounds": 2,
            "visual_skin": "redline_duel",
            "host_intro": "Rivalry heat: the table narrows its focus to the sharpest conflict.",
            "viewer_hook": "Watch the two loudest arcs collide.",
            "safety_label": RESPONSIBLE_LABEL,
        },
        {
            "id": "intermission",
            "active_game": "intermission",
            "title": "Next Room Opens",
            "duration_rounds": 1,
            "visual_skin": "city_transition",
            "host_intro": "Room change: the underground casino resets the lights for the next segment.",
            "viewer_hook": "Stay for the next room reveal.",
            "safety_label": RESPONSIBLE_LABEL,
        },
    ]


def _card_dict(card):
    rank, suit = card
    return {"rank": int(rank), "suit": suit}


def _fresh_deck(rng: random.Random):
    deck = [(rank, suit) for suit in CARD_SUITS for rank in CARD_RANKS]
    rng.shuffle(deck)
    return deck


def blackjack_value(cards):
    total = 0
    aces = 0
    for rank, _ in cards:
        if rank == 14:
            aces += 1
            total += 11
        else:
            total += min(10, int(rank))
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def baccarat_value(cards):
    return sum(0 if rank >= 10 else 1 if rank == 14 else int(rank) for rank, _ in cards) % 10


def _deal(deck):
    if not deck:
        raise ValueError("casino deck exhausted")
    return deck.pop(0)


def _profile_id(player):
    return getattr(getattr(player, "profile", None), "id", None) or getattr(player, "id", None) or getattr(player, "name", "ai").lower()


def _profile_name(player):
    return getattr(player, "name", None) or str(_profile_id(player)).title()


def _profile_color(player):
    return getattr(getattr(player, "profile", None), "color", None) or "#65f7ff"


def _profile_persona(player):
    return getattr(getattr(player, "profile", None), "persona", None) or "AI casino regular"


def _participant(player, bankroll):
    return {
        "id": str(_profile_id(player)),
        "name": _profile_name(player),
        "color": _profile_color(player),
        "persona": _profile_persona(player),
        "bankroll": int(bankroll),
    }


def _blackjack_decision(hand, dealer_upcard):
    total = blackjack_value(hand)
    up_rank = dealer_upcard[0]
    up_value = 11 if up_rank == 14 else min(10, up_rank)
    if total <= 11:
        return "hit"
    if total <= 16 and up_value >= 7:
        return "hit"
    if total <= 15 and up_value == 14:
        return "hit"
    return "stand"


def _settle_blackjack(player_total, dealer_total, player_blackjack, dealer_blackjack, unit):
    if player_total > 21:
        return "bust", -unit
    if dealer_total > 21:
        return "dealer_bust", unit
    if player_blackjack and not dealer_blackjack:
        return "blackjack", int(unit * 1.5)
    if dealer_blackjack and not player_blackjack:
        return "dealer_blackjack", -unit
    if player_total > dealer_total:
        return "win", unit
    if player_total < dealer_total:
        return "loss", -unit
    return "push", 0


def play_blackjack_round(players, bankrolls, *, rng=None, deck=None, unit=100):
    """Play one deterministic, AI-only blackjack round and return replay data."""
    rng = rng or random.Random()
    deck = list(deck) if deck is not None else _fresh_deck(rng)
    participants = [_participant(player, bankrolls.get(str(_profile_id(player)), 0)) for player in players]
    dealer = {"hand": [], "visible": [], "total": 0}
    for participant in participants:
        participant["hand"] = [_deal(deck), _deal(deck)]
    dealer["hand"] = [_deal(deck), _deal(deck)]
    dealer["visible"] = [dealer["hand"][0]]
    events = []
    for participant in participants:
        for card in participant["hand"]:
            events.append(
                {
                    "type": "casino_card",
                    "game": "blackjack",
                    "role": "participant",
                    "participant_id": participant["id"],
                    "participant": participant["name"],
                    "card": _card_dict(card),
                }
            )
    for card in dealer["hand"]:
        events.append({"type": "casino_card", "game": "blackjack", "role": "dealer", "card": _card_dict(card)})
    for participant in participants:
        hand = participant["hand"]
        decisions = []
        while blackjack_value(hand) < 21:
            decision = _blackjack_decision(hand, dealer["visible"][0])
            decisions.append(decision)
            events.append(
                {
                    "type": "casino_decision",
                    "game": "blackjack",
                    "participant_id": participant["id"],
                    "participant": participant["name"],
                    "decision": decision,
                    "total": blackjack_value(hand),
                }
            )
            if decision != "hit":
                break
            hand.append(_deal(deck))
        if not decisions:
            decisions.append("stand")
            events.append(
                {
                    "type": "casino_decision",
                    "game": "blackjack",
                    "participant_id": participant["id"],
                    "participant": participant["name"],
                    "decision": "stand",
                    "total": blackjack_value(hand),
                }
            )
        participant["decisions"] = decisions
        participant["total"] = blackjack_value(hand)
        participant["cards"] = [_card_dict(card) for card in hand]
    while blackjack_value(dealer["hand"]) < 17:
        dealer["hand"].append(_deal(deck))
        events.append(
            {
                "type": "casino_card",
                "game": "blackjack",
                "role": "dealer",
                "card": _card_dict(dealer["hand"][-1]),
            }
        )
    dealer["total"] = blackjack_value(dealer["hand"])
    dealer_blackjack = len(dealer["hand"]) == 2 and dealer["total"] == 21
    deltas = {}
    for participant in participants:
        player_blackjack = len(participant["hand"]) == 2 and participant["total"] == 21
        outcome, delta = _settle_blackjack(
            participant["total"],
            dealer["total"],
            player_blackjack,
            dealer_blackjack,
            int(unit),
        )
        participant["outcome"] = outcome
        participant["delta"] = delta
        participant["bankroll"] += delta
        deltas[participant["id"]] = delta
        participant.pop("hand", None)
    dealer["cards"] = [_card_dict(card) for card in dealer["hand"]]
    dealer.pop("hand", None)
    winners = [item for item in participants if item["delta"] > 0]
    house_delta = -sum(deltas.values())
    if winners:
        headline = f"{', '.join(item['name'] for item in winners[:2])} beat the dealer"
        if len(winners) > 2:
            headline += f" +{len(winners) - 2}"
    else:
        headline = "Dealer holds the blackjack room"
    return {
        "game": "blackjack",
        "unit": int(unit),
        "participants": participants,
        "dealer": dealer,
        "deltas": deltas,
        "house_delta": house_delta,
        "events": events,
        "outcome": {
            "headline": headline,
            "summary": f"Dealer shows {dealer['total']}; fictional bankrolls update after the AI-only round.",
            "winners": [item["id"] for item in winners],
        },
    }


def _baccarat_side_for(player_id, round_id):
    if "echo" in player_id and round_id % 5 == 0:
        return "tie"
    if "vega" in player_id or round_id % 2 == 0:
        return "player"
    return "banker"


def _banker_draws(banker_total, player_third):
    if player_third is None:
        return banker_total <= 5
    third_value = 0 if player_third[0] >= 10 else 1 if player_third[0] == 14 else int(player_third[0])
    if banker_total <= 2:
        return True
    if banker_total == 3:
        return third_value != 8
    if banker_total == 4:
        return 2 <= third_value <= 7
    if banker_total == 5:
        return 4 <= third_value <= 7
    if banker_total == 6:
        return 6 <= third_value <= 7
    return False


def play_baccarat_round(players, bankrolls, *, rng=None, deck=None, unit=100, round_id=1):
    """Play one deterministic, AI-only baccarat round and return replay data."""
    rng = rng or random.Random()
    deck = list(deck) if deck is not None else _fresh_deck(rng)
    participants = [_participant(player, bankrolls.get(str(_profile_id(player)), 0)) for player in players]
    player_hand = [_deal(deck), _deal(deck)]
    banker_hand = [_deal(deck), _deal(deck)]
    events = [
        *({"type": "casino_card", "game": "baccarat", "role": "player", "card": _card_dict(card)} for card in player_hand),
        *({"type": "casino_card", "game": "baccarat", "role": "banker", "card": _card_dict(card)} for card in banker_hand),
    ]
    natural = baccarat_value(player_hand) >= 8 or baccarat_value(banker_hand) >= 8
    player_third = None
    if not natural and baccarat_value(player_hand) <= 5:
        player_third = _deal(deck)
        player_hand.append(player_third)
        events.append({"type": "casino_card", "game": "baccarat", "role": "player", "card": _card_dict(player_third)})
    if not natural and _banker_draws(baccarat_value(banker_hand), player_third):
        banker_card = _deal(deck)
        banker_hand.append(banker_card)
        events.append({"type": "casino_card", "game": "baccarat", "role": "banker", "card": _card_dict(banker_card)})
    player_total = baccarat_value(player_hand)
    banker_total = baccarat_value(banker_hand)
    if player_total > banker_total:
        winning_side = "player"
    elif banker_total > player_total:
        winning_side = "banker"
    else:
        winning_side = "tie"
    deltas = {}
    for participant in participants:
        side = _baccarat_side_for(participant["id"], int(round_id))
        participant["side"] = side
        events.append(
            {
                "type": "casino_decision",
                "game": "baccarat",
                "participant_id": participant["id"],
                "participant": participant["name"],
                "decision": side,
            }
        )
        if winning_side == "tie":
            delta = unit * 8 if side == "tie" else 0
            outcome = "tie_hit" if side == "tie" else "tie_push"
        elif side == winning_side:
            delta = unit
            outcome = "win"
        else:
            delta = -unit
            outcome = "loss"
        participant["outcome"] = outcome
        participant["delta"] = int(delta)
        participant["bankroll"] += int(delta)
        deltas[participant["id"]] = int(delta)
    house_delta = -sum(deltas.values())
    return {
        "game": "baccarat",
        "unit": int(unit),
        "participants": participants,
        "player_hand": [_card_dict(card) for card in player_hand],
        "banker_hand": [_card_dict(card) for card in banker_hand],
        "player_total": player_total,
        "banker_total": banker_total,
        "winning_side": winning_side,
        "deltas": deltas,
        "house_delta": house_delta,
        "events": events,
        "outcome": {
            "headline": f"{winning_side.title()} side takes the baccarat pit",
            "summary": f"Player {player_total}, banker {banker_total}. AI side calls resolve with fictional bankrolls.",
            "winners": [item["id"] for item in participants if item["delta"] > 0],
        },
    }


class CasinoProgram:
    """Deterministic showrunner for non-poker OBS casino blocks."""

    def __init__(
        self,
        players: Iterable,
        *,
        rng_seed=None,
        enabled=True,
        starting_bankroll=5000,
        unit=100,
        blocks=None,
    ):
        self.enabled = bool(enabled)
        self.players = list(players)
        self.rng_seed = 0 if rng_seed is None else int(rng_seed)
        self.unit = max(1, int(unit or 100))
        self.blocks = [dict(block) for block in (blocks or default_casino_blocks())]
        if not self.blocks:
            self.blocks = default_casino_blocks()
        self.block_index = 0
        self.block_round = 0
        self.round_id = 0
        self.fictional_bankrolls = {
            str(_profile_id(player)): int(starting_bankroll) for player in self.players
        }
        self.outcome = {}
        self.spectacle_cue = {
            "headline": "Night City casino program warming up",
            "caption": "Poker remains the main table; side rooms are AI-only simulation beats.",
            "voice_line": "The underground AI casino is warming the side rooms.",
            "priority": "low",
        }
        self.last_events = []

    def current_block(self):
        block = dict(self.blocks[self.block_index % len(self.blocks)])
        block.setdefault("safety_label", RESPONSIBLE_LABEL)
        block.setdefault("duration_rounds", 1)
        block.setdefault("visual_skin", "night_city")
        block.setdefault("viewer_hook", "Stay with the current room.")
        block.setdefault("host_intro", block.get("title", "Night City block"))
        return block

    def _rng_for_round(self, active_game):
        salt = sum(ord(ch) for ch in str(active_game))
        return random.Random((self.rng_seed * 1_000_003) + self.round_id * 9_176 + salt)

    def _emit(self, emit: Callable | None, event_type, message="", **details):
        event = {"type": event_type, "message": message, **details}
        self.last_events.append(event)
        if emit:
            emit(event_type, message, **details)

    def _start_next_block_if_needed(self, emit=None):
        block = self.current_block()
        if self.block_round >= max(1, int(block.get("duration_rounds", 1))):
            self.block_index = (self.block_index + 1) % len(self.blocks)
            self.block_round = 0
            block = self.current_block()
        if self.block_round == 0:
            self._emit(
                emit,
                "casino_block_start",
                block["host_intro"],
                block_id=block.get("id"),
                active_game=block.get("active_game"),
                title=block.get("title"),
                visual_skin=block.get("visual_skin"),
                viewer_hook=block.get("viewer_hook"),
                responsible_label=block.get("safety_label", RESPONSIBLE_LABEL),
            )
            self._emit(
                emit,
                "casino_host_line",
                block["host_intro"],
                priority="medium",
                active_game=block.get("active_game"),
                title=block.get("title"),
            )
        return block

    def advance(self, hand_number=0, emit=None):
        """Advance the programming layer once at a safe between-hand boundary."""
        if not self.enabled:
            return self.snapshot()
        self.last_events = []
        self.round_id += 1
        block = self._start_next_block_if_needed(emit=emit)
        active_game = block.get("active_game", "poker")
        self._emit(
            emit,
            "casino_round_start",
            f"{block.get('title', 'Night City block')} round {self.round_id} begins.",
            active_game=active_game,
            round_id=self.round_id,
            block_id=block.get("id"),
            hand_number=hand_number,
        )
        if active_game == "blackjack":
            result = play_blackjack_round(
                self.players,
                self.fictional_bankrolls,
                rng=self._rng_for_round(active_game),
                unit=self.unit,
            )
            self._apply_result(block, result, emit=emit)
        elif active_game == "baccarat":
            result = play_baccarat_round(
                self.players,
                self.fictional_bankrolls,
                rng=self._rng_for_round(active_game),
                unit=self.unit,
                round_id=self.round_id,
            )
            self._apply_result(block, result, emit=emit)
        else:
            self.outcome = {
                "game": active_game,
                "headline": block.get("title", "Night City block"),
                "summary": block.get("viewer_hook", "Stay with the current room."),
                "winners": [],
            }
            self.spectacle_cue = {
                "headline": block.get("title", "Night City block"),
                "caption": block.get("viewer_hook", "The next room is loading."),
                "voice_line": block.get("host_intro", "The next Night City block is live."),
                "priority": "medium" if active_game in {"lounge", "intermission"} else "low",
            }
        self.block_round += 1
        return self.snapshot()

    def _apply_result(self, block, result, emit=None):
        for event in result.get("events", []):
            event = dict(event)
            event_type = event.pop("type", "casino_decision")
            self._emit(emit, event_type, event.get("message", ""), round_id=self.round_id, **event)
        for player_id, delta in result.get("deltas", {}).items():
            self.fictional_bankrolls[player_id] = int(self.fictional_bankrolls.get(player_id, 0)) + int(delta)
            self._emit(
                emit,
                "casino_bankroll_update",
                f"{player_id} bankroll changes by {delta}.",
                participant_id=player_id,
                delta=int(delta),
                bankroll=self.fictional_bankrolls[player_id],
                active_game=result.get("game"),
                round_id=self.round_id,
            )
        self.outcome = deepcopy(result)
        self.outcome.pop("events", None)
        self.outcome["headline"] = result.get("outcome", {}).get("headline")
        self.outcome["summary"] = result.get("outcome", {}).get("summary")
        self.spectacle_cue = {
            "headline": result.get("outcome", {}).get("headline", block.get("title", "Casino room")),
            "caption": result.get("outcome", {}).get("summary", block.get("viewer_hook", "")),
            "voice_line": f"{block.get('title', 'Casino room')}: {result.get('outcome', {}).get('headline', 'round complete')}.",
            "priority": "high",
        }
        self._emit(
            emit,
            "casino_outcome",
            self.spectacle_cue["voice_line"],
            active_game=result.get("game"),
            round_id=self.round_id,
            outcome=result.get("outcome", {}),
            deltas=result.get("deltas", {}),
        )
        self._emit(
            emit,
            "casino_host_line",
            self.spectacle_cue["voice_line"],
            priority="high",
            active_game=result.get("game"),
            round_id=self.round_id,
        )

    def decision_context_for_player(self, player_id):
        """Return the public/role-limited context a casino AI could receive."""
        player_id = str(player_id)
        participant = next((item for item in self.participants_snapshot() if item["id"] == player_id), None)
        program_block = {
            key: value
            for key, value in self.public_block().items()
            if key not in {"viewer_hook"}
        }
        context = {
            "active_game": self.current_block().get("active_game", "poker"),
            "program_block": program_block,
            "round_id": self.round_id,
            "participant": participant,
            "fictional_bankroll": self.fictional_bankrolls.get(player_id),
            "responsible_label": RESPONSIBLE_LABEL,
            "allowed_context": "public room state plus this AI participant profile only",
        }
        if context["active_game"] == "blackjack":
            context["legal_decisions"] = ["hit", "stand"]
            context["visible_dealer_card"] = (self.outcome.get("dealer") or {}).get("visible", [])[:1]
        elif context["active_game"] == "baccarat":
            context["legal_decisions"] = ["player", "banker", "tie"]
            context["visible_sides"] = ["player", "banker", "tie"]
        return context

    def public_block(self):
        block = self.current_block()
        return {
            "id": block.get("id"),
            "title": block.get("title"),
            "active_game": block.get("active_game"),
            "duration_rounds": int(block.get("duration_rounds", 1)),
            "round_in_block": self.block_round,
            "visual_skin": block.get("visual_skin"),
            "host_intro": block.get("host_intro"),
            "viewer_hook": block.get("viewer_hook"),
            "safety_label": block.get("safety_label", RESPONSIBLE_LABEL),
        }

    def participants_snapshot(self):
        by_id = {item["id"]: item for item in self._latest_participants()}
        return [
            {
                "id": str(_profile_id(player)),
                "name": _profile_name(player),
                "color": _profile_color(player),
                "persona": _profile_persona(player),
                "bankroll": int(self.fictional_bankrolls.get(str(_profile_id(player)), 0)),
                **{
                    key: value
                    for key, value in by_id.get(str(_profile_id(player)), {}).items()
                    if key not in {"id", "name", "color", "persona", "bankroll"}
                },
            }
            for player in self.players
        ]

    def _latest_participants(self):
        data = self.outcome.get("participants") if isinstance(self.outcome, dict) else None
        return data if isinstance(data, list) else []

    def snapshot(self):
        if not self.enabled:
            return {
                "schema_version": 1,
                "enabled": False,
                "active_game": "poker",
                "program_block": {},
                "round_id": self.round_id,
                "participants": [],
                "fictional_bankrolls": {},
                "outcome": {},
                "spectacle_cue": {},
                "responsible_label": RESPONSIBLE_LABEL,
            }
        return {
            "schema_version": 1,
            "enabled": True,
            "active_game": self.current_block().get("active_game", "poker"),
            "program_block": self.public_block(),
            "round_id": self.round_id,
            "participants": self.participants_snapshot(),
            "fictional_bankrolls": dict(self.fictional_bankrolls),
            "outcome": deepcopy(self.outcome),
            "spectacle_cue": dict(self.spectacle_cue),
            "responsible_label": RESPONSIBLE_LABEL,
        }

    def force_fixture(self, active_game):
        """Build a stable visual-smoke fixture for a room mode."""
        active_game = str(active_game)
        match = next(
            (index for index, block in enumerate(self.blocks) if block.get("active_game") == active_game),
            0,
        )
        self.block_index = match
        self.block_round = 0
        self.round_id += 1
        block = self.current_block()
        if active_game == "blackjack":
            deck = [
                (10, "spades"),
                (9, "hearts"),
                (8, "clubs"),
                (14, "diamonds"),
                (7, "clubs"),
                (6, "spades"),
                (13, "hearts"),
                (5, "diamonds"),
                (4, "hearts"),
                (3, "clubs"),
                (2, "diamonds"),
                (9, "spades"),
            ]
            result = play_blackjack_round(self.players, self.fictional_bankrolls, deck=deck, unit=self.unit)
            self._apply_result(block, result)
        elif active_game == "baccarat":
            deck = [
                (7, "hearts"),
                (2, "clubs"),
                (6, "diamonds"),
                (10, "spades"),
                (5, "clubs"),
                (3, "hearts"),
            ]
            result = play_baccarat_round(self.players, self.fictional_bankrolls, deck=deck, unit=self.unit, round_id=self.round_id)
            self._apply_result(block, result)
        else:
            self.outcome = {
                "game": active_game,
                "headline": block.get("title", "Night City block"),
                "summary": block.get("viewer_hook", "Stay with the current room."),
                "winners": [],
            }
            self.spectacle_cue = {
                "headline": block.get("title", "Night City block"),
                "caption": block.get("viewer_hook", "Stay with the current room."),
                "voice_line": block.get("host_intro", "The Night City casino changes rooms."),
                "priority": "medium",
            }
        return self.snapshot()
