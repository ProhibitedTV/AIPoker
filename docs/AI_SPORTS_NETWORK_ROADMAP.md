# AI Poker Network Roadmap

AI Poker’s north star is a local-first autonomous AI sports channel: deterministic poker rules, persistent fictional competitors, replayable history, and OBS-ready programming that can run unattended.

## Phase 1 — Foundation

Complete in the current app:

- deterministic No-Limit Texas Hold’em engine;
- cash and sit-and-go modes;
- legal action enforcement independent of model output;
- OBS overlay, SSE events, health badge, browser audio, and music bed;
- checkpoint recovery, hand histories, metrics, and soak tests.

## Phase 2 — Operational maturity

Implemented support:

- [Operator runbook](OPERATOR_RUNBOOK.md);
- `/health` and overlay health badge;
- `scripts/broadcast_smoke.py` artifact gate;
- `scripts/benchmark_models.py` local model calibration;
- `scripts/replay_hand.py` audited hand replay/export.

## Phase 3 — League layer

The public `/state` schema now exposes a deterministic `league` object:

- current season/session identifier;
- season hand and tournament counts;
- standings by tournament wins, net chips, and stack;
- all-time style records such as largest pot, tournament wins, winning streak, aggression, and net leader;
- recent championship banners.

This turns resets and long sessions into an inspectable fictional sport without external services.

## Phase 4 — Character layer

The public `/state` schema now exposes `personality_arcs`:

- deterministic confidence, tilt, and risk appetite;
- style labels derived from VPIP, PFR, aggression, all-ins, and showdowns;
- persistent bio and arc summaries;
- notable career events such as biggest pots and tournament banners.

These character arcs are bounded broadcast context. They do not change card rules, reveal hidden cards to models, or create unbounded LLM memory.

## Phase 5 — Autonomous television mode

The public `/state` schema now exposes a `program` segment:

- `Live Sit & Go`;
- `Cash Table Live`;
- `Showdown Desk`;
- `Trophy Ceremony`;
- `Recovery Break`.

The OBS overlay displays the current program and rotates deterministic season storylines so viewers joining mid-stream can understand why the current hand matters.

## Phase 6 — AI Poker Network

Future expansion can add multiple simultaneous tables, championship calendars, promotion/relegation, player drafts, retirements, specials, and recap shows. The current direction keeps those ambitions local-first and audit-friendly: every new “TV” layer should be derivable from persisted state, hand histories, and metrics before asking an LLM to embellish it.

## Viewer success test

A new viewer should understand within 30 seconds:

- who is leading;
- what format and program segment is live;
- what record or storyline matters;
- whether the stream is healthy;
- that all chips and standings are fictional.
