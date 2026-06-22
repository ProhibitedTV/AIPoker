# AI Poker

AI Poker is a local-first, always-on No-Limit Texas Hold'em broadcast. Local [Ollama](https://ollama.com/) models play a rules-checked cash game or sit-and-go while a Qt control room and 1080p OBS overlay expose every card, pot, decision, equity swing, and season storyline to viewers.

The engine is designed to be auditable and recoverable for 24/7 operation. It enforces legal actions independently of model output; an LLM can make a poor strategic decision, but it cannot check while facing a bet, create chips, see another player's hole cards, or award itself the wrong pot.

## Highlights

- Complete street-based No-Limit Hold'em betting with calls, minimum raises, short all-ins, reopening rules, uncalled returns, and automatic all-in runouts
- Correct heads-up and multiway action order, burn cards, best-five evaluation, main/side pots, split pots, and odd-chip awards
- Four-player named local cast by default—Atlas, Vega, Nova, and Echo—with configurable models, personas, colors, voices, and temperatures
- Cash mode with fixed stakes and zero-stack reloads, plus escalating hand-count sit-and-go tournaments with big-blind antes and automatic restarts
- Spectator-visible hole cards and live equity, while each Ollama prompt receives only that player's private cards and public table information
- Persistent schema-v2 statistics: VPIP, PFR, three-bets, aggression, showdown results, all-ins, tournament finishes, notable hands, and chip history
- Atomic hand-boundary checkpoints, rotating replayable JSONL hand histories, bounded queues, and legal fallback play during Ollama outages
- 1920×1080 OBS scene, compact overlay, SSE event feed, layered original audio, optional TTS, reduced motion, and offline preview tools

## Install and run

Use Python 3.10+ and Ollama. The GUI requirements are pinned in `requirements.txt`; development tools are in `requirements-dev.txt`.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
ollama serve
ollama pull qwen2.5:7b
python main.py
```

Useful launch overrides:

```bash
python main.py --mode tournament --players 4 --continuous-play
python main.py --mode cash --players 6 --windowed --tts
python main.py --single-hand --seed 42 --reduced-motion --no-ambience
```

Copy `config.example.json` to `config.json` to select per-seat Ollama models, game mode, stacks, tournament levels, pacing, analysis depth, audio channels, persistence paths, and overlay styling. Explicit CLI options override the file. An `auto` model is resolved from installed Ollama models at runtime; if Ollama is unavailable, bounded fallback policy keeps the stream moving and the overlay reports fallback health.

## OBS and audio

The full browser source is `http://127.0.0.1:8765/overlay`. Configure OBS at **1920×1080** with the same frame rate as the stream. Use `?compact=1` for the compact panel. The server binds only to localhost unless configured otherwise.

- `/state` publishes backward-compatible state plus the version-2 player, pot, tournament, analysis, audio, and health schema.
- `/events` is a reconnectable server-sent event stream with monotonic IDs for animation and custom integrations.
- `/health` provides a minimal service probe.

Desktop effects, ambience, and TTS should be captured through OBS Application Audio Capture. Browser-source cues are independently available through `overlay_audio_enabled`; leave that disabled when desktop audio is already captured to avoid doubling. Master, ambience, effects, and voice levels are separate, and nonessential sound is ducked around speech.

Preview the real overlay without Ollama:

```bash
python scripts/preview_overlay.py
python scripts/preview_gui.py ui-preview.png
```

## Rules and house policy

Tournament behavior follows the latest inspected published [Poker TDA rules](https://www.pokertda.com/poker-tda-rules/), including heads-up blind/action order, short all-in reopening, dead-button progression, big-blind ante handling, side-pot eligibility, and odd chips clockwise from the button.

Cash mode is a no-rake entertainment table: 10/20 default blinds, 2,000-chip buy-in, fixed stakes, and automatic reload only after a seat reaches zero. Sit-and-go defaults are four 2,000-chip stacks, eight hands per level, a big-blind ante beginning at 40/80, no rebuys, a 15-second winner sequence, and automatic restart. Straddles, insurance, run-it-twice, real-money payouts, and non-Hold'em variants are intentionally out of scope.

## Verification

The normal suite does not require Ollama. GUI tests use Qt's offscreen platform.

```bash
pytest -m "not slow"
pytest -m slow tests/test_hand_evaluator_exhaustive.py
python scripts/soak_test.py --hands 10000 --players 6
python scripts/soak_test.py --hands 2000 --players 4 --mode tournament
```

The release gate covers legal-action tables, heads-up transitions, minimum raises, cumulative short all-ins, uncalled excess, folded dead money, independent side-pot winners, split/odd chips, burn/deck invariants, prompt privacy, malformed model output, metrics migration, checkpoints, SSE replay, 1080p/compact layouts, and a deterministic 10,000-hand chip-conservation soak. The slow evaluator proof checks all 2,598,960 five-card combinations against canonical category frequencies.

## Main components

- `game.py` — deterministic rules state machine, modes, pots, events, checkpoints, and public state
- `player.py` — stable profiles and seat/contribution state
- `ollama_integration.py` — cached model discovery, strict private JSON decisions, validation, and fallback
- `analysis.py` — bounded asynchronous spectator equity
- `metrics.py` — atomic schema-v2 season and tournament records
- `gui.py` — non-blocking Qt broadcast control room
- `overlay_server.py` — OBS page, state API, SSE events, and health probe
- `audio.py` / `commentary.py` — generated effects, ambience, ducking, and optional speech

Season data, checkpoints, hand histories, and generated audio are written beneath `data/` by default. Resetting season statistics does not delete replay histories or checkpoints.
