"""Poker seat state and model-backed decision compatibility helpers."""

from dataclasses import dataclass, field
import inspect
import re

from ollama_integration import get_ai_decision


@dataclass(frozen=True)
class PlayerProfile:
    id: str
    name: str
    persona: str = "balanced"
    model: str = "auto"
    color: str = "#e6b94a"
    voice: str = ""
    temperature: float = 0.25
    avatar: str = "neon_mask"
    sigil: str = ""
    tagline: str = "AI competitor"
    nickname: str = ""
    archetype: str = "AI regular"
    model_name: str = "Local model"
    attitude: str = "composed"
    reputation: str = "steady table regular"
    moment_lines: dict = field(default_factory=dict)

    @classmethod
    def from_value(cls, value, seat):
        if isinstance(value, cls):
            return value
        value = value or {}
        color = str(value.get("color", "#e6b94a"))
        if not re.fullmatch(r"#[0-9a-fA-F]{3,8}", color):
            color = "#e6b94a"
        avatar = re.sub(r"[^a-zA-Z0-9_-]", "", str(value.get("avatar", "neon_mask")))[:32] or "neon_mask"
        sigil = str(value.get("sigil", "")).strip().upper()[:4]
        if not sigil:
            sigil = str(value.get("name", f"P{seat + 1}")).strip().upper()[:2] or f"P{seat + 1}"
        moment_lines = value.get("moment_lines") or value.get("lines") or {}
        if not isinstance(moment_lines, dict):
            moment_lines = {}
        moment_lines = {
            key: str(moment_lines.get(key, "")).strip()[:120]
            for key in ("all_in", "win", "loss", "fold", "idle")
            if str(moment_lines.get(key, "")).strip()
        }
        name = str(value.get("name", f"AI Player {seat + 1}"))
        return cls(
            id=str(value.get("id", f"seat-{seat + 1}")),
            name=name,
            persona=str(value.get("persona", "balanced")),
            model=str(value.get("model", "auto")),
            color=color,
            voice=str(value.get("voice", "")),
            temperature=float(value.get("temperature", 0.25)),
            avatar=avatar,
            sigil=sigil,
            tagline=str(value.get("tagline", value.get("persona", "AI competitor")))[:72],
            nickname=str(value.get("nickname", name))[:32],
            archetype=str(value.get("archetype", value.get("persona", "AI regular")))[:48],
            model_name=str(value.get("model_name", value.get("display_model", value.get("model", "Local model"))))[:48],
            attitude=str(value.get("attitude", "composed"))[:48],
            reputation=str(value.get("reputation", value.get("tagline", "steady table regular")))[:96],
            moment_lines=moment_lines,
        )


@dataclass
class AIPlayer:
    name: str
    chips: int = 2000
    decision_provider: object = None
    seat: int = 0
    profile: PlayerProfile = None
    hand: list = field(default_factory=list)
    current_bet: int = 0
    total_committed: int = 0
    is_active: bool = True
    folded: bool = False
    all_in: bool = False
    eliminated: bool = False
    wins: int = 0
    ties: int = 0
    total_rounds: int = 0
    last_action: str = "Waiting"
    last_wager: int = 0
    acted_since_full_raise: bool = False
    voluntarily_put_money: bool = False
    preflop_raised: bool = False
    three_bet: bool = False
    bets_raises: int = 0
    calls: int = 0
    went_to_showdown: bool = False
    won_at_showdown: bool = False
    all_in_counted: bool = False
    model_status: str = "pending"
    model_source: str = "pending"
    resolved_model: str = "auto"
    ollama_decisions: int = 0
    fallback_decisions: int = 0

    def __post_init__(self):
        self.profile = self.profile or PlayerProfile(f"seat-{self.seat + 1}", self.name)
        self.name = self.profile.name
        self._decision_provider = self.decision_provider or get_ai_decision

    @property
    def id(self):
        return self.profile.id

    @property
    def status(self):
        if self.eliminated:
            return "eliminated"
        if self.folded:
            return "folded"
        if self.all_in:
            return "all_in"
        if self.is_active:
            return "active"
        return "sitting_out"

    @property
    def can_act(self):
        return self.is_active and not self.folded and not self.all_in and self.chips > 0

    def deal_hand(self, hand):
        self.hand = list(hand)

    def request_decision(self, context):
        """Call new context providers while retaining two-argument providers."""
        provider = self._decision_provider
        try:
            signature = inspect.signature(provider)
            positional = [
                parameter
                for parameter in signature.parameters.values()
                if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
            ]
            required = [parameter for parameter in positional if parameter.default is parameter.empty]
            if len(required) >= 2:
                return provider(self.hand, context.get("community_cards_raw", []))
        except (TypeError, ValueError):
            pass
        return provider(context)

    def commit(self, amount, street=True):
        paid = min(self.chips, max(0, int(amount)))
        self.chips -= paid
        if street:
            self.current_bet += paid
        self.total_committed += paid
        self.last_wager = paid
        if self.chips == 0 and self.is_active and not self.folded:
            self.all_in = True
        return paid

    def wager_to(self, target):
        return self.commit(max(0, int(target) - self.current_bet))

    def post_blind(self, amount, label):
        paid = self.commit(amount)
        self.last_action = f"{label} {paid}" + (" (all-in)" if self.all_in else "")
        return paid

    def reset_for_next_round(self):
        self.hand = []
        self.current_bet = 0
        self.total_committed = 0
        self.folded = False
        self.all_in = False
        self.is_active = self.chips > 0 and not self.eliminated
        self.last_action = "Waiting"
        self.last_wager = 0
        self.acted_since_full_raise = False
        self.voluntarily_put_money = False
        self.preflop_raised = False
        self.three_bet = False
        self.bets_raises = 0
        self.calls = 0
        self.went_to_showdown = False
        self.won_at_showdown = False
        self.all_in_counted = False

    def get_win_percentage(self):
        return 0.0 if self.total_rounds == 0 else (self.wins / self.total_rounds) * 100

    def is_bankrupt(self):
        return self.chips <= 0
