# AI Poker

AI Poker League is a local-first, always-on fictional No-Limit Texas Hold'em sports simulation. Local [Ollama](https://ollama.com/) models play for simulated chips while a deterministic rules engine, Qt control room, and 1080p OBS overlay present every card, pot, decision, equity swing, and season storyline. It is entertainment software with no real-money wagering, deposits, prizes, promotions, or payouts.

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

For Twitch-ready title, description, panel copy, moderation notes, audio capture, VOD guidance, and a preflight checklist, use the [Twitch Broadcast Guide](docs/TWITCH_BROADCAST_GUIDE.md). Copy-safe live metadata is also available from `http://127.0.0.1:8765/stream-info`. The subtle simulation-only overlay label is enabled by default and can be disabled with `overlay_disclaimer_enabled: false` or `--no-simulation-disclaimer` for private previews.

The header health badge summarizes normal play, safe model fallback, checkpoint recovery, muted audio, persistence warnings, and SSE reconnection without exposing errors or local details. Preview these states with `--health-state normal`, `degraded`, `recovered`, `persistence-warning`, or `audio-muted`; the same sanitized health object is available in `/state` and `/health`.

- `/state` publishes backward-compatible state plus the version-2 player, pot, tournament, analysis, audio, and health schema.
- `/events` is a reconnectable server-sent event stream with monotonic IDs for animation and custom integrations.
- `/health` provides a minimal service probe.

The OBS browser source now carries table cues and the casino music bed by default, so OBS's **Control audio via OBS** option can mix the `AI Poker` source directly. Use `?audio=0`, `?music=0`, or `overlay_audio_enabled: false` if you instead capture the desktop app through OBS Application Audio Capture and want to prevent doubled sound. Master, ambience, effects, music, and voice levels are separate, and nonessential sound is ducked around speech.

Stream-safe WAV tracks placed in `music/` play as a shuffled casino music bed by default in both the desktop mixer and the OBS browser source. Use `music_enabled`, `music_path`, `music_volume`, and `music_shuffle` in config, or launch with `--no-music`, `--music-path`, and `--music-volume`, to tune the playlist without changing the Foley or voice mix.

Preview the real overlay without Ollama:

```bash
python scripts/preview_overlay.py
python scripts/preview_gui.py ui-preview.png
```

### Human-readable broadcast pacing

The default Broadcast pace guarantees a visible beat even when a model answers instantly: 320 ms between dealt seats and forced bets, 1.25 seconds per player action, 4.5 seconds between streets, and 6.5 seconds after each hand. Model inference and pacing both run away from Qt's event thread, so the interface stays responsive. Cinematic, Broadcast, and Brisk presets remain human-legible; CLI/config values can still be set to zero for headless tests and accelerated simulations.

Only newly dealt cards flip, only changed wagers slide chips forward, and winners retain a gold award treatment long enough to read the result. Reduced-motion mode disables these transitions without removing state information.

### Audience-first spectator design

The OBS scene explains each street in plain English, expands dealer and blind abbreviations, identifies the acting player, describes the immediate choice, and labels equity as “chance to win.” A five-step hand tracker, chip-leader marker, big-pot and all-in tension cues, newcomer-friendly statistics, winner takeover, and restrained celebration animation keep the story legible even for viewers who have never played poker. These layers are event-driven, so idle polling never replays a card, chip, action, or award animation.

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
- `audio.py` / `commentary.py` — generated effects, ambience, shuffled music bed, ducking, and optional speech

Season data, checkpoints, hand histories, and generated audio are written beneath `data/` by default. Resetting season statistics does not delete replay histories or checkpoints.
