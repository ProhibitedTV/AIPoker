# AI Poker

AI Poker League is a local-first, always-on fictional No-Limit Texas Hold'em sports simulation. Local [Ollama](https://ollama.com/) models play for simulated chips while a deterministic rules engine, Qt control room, and 1080p OBS overlay present every card, pot, decision, equity swing, and season storyline. It is entertainment software with no real-money wagering, deposits, prizes, promotions, or payouts.

The engine is designed to be auditable and recoverable for 24/7 operation. It enforces legal actions independently of model output; an LLM can make a poor strategic decision, but it cannot check while facing a bet, create chips, see another player's hole cards, or award itself the wrong pot.

## Highlights

- Complete street-based No-Limit Hold'em betting with calls, minimum raises, short all-ins, reopening rules, uncalled returns, and automatic all-in runouts
- Correct heads-up and multiway action order, burn cards, best-five evaluation, main/side pots, split pots, and odd-chip awards
- Four-player named local cast by default—Atlas, Vega, Nova, and Echo—with configurable models, personas, colors, voices, temperatures, and OBS avatar identities
- Cash mode with fixed stakes and zero-stack reloads, plus escalating hand-count sit-and-go tournaments with big-blind antes and automatic restarts
- Spectator-visible hole cards and live equity, while each Ollama prompt receives only that player's private cards and public table information
- Persistent schema-v2 statistics: VPIP, PFR, three-bets, aggression, showdown results, all-ins, tournament finishes, notable hands, and chip history
- League/program/story/personality state plus scheduled 24/7 variety blocks for autonomous sports-channel context without requiring Ollama
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
python main.py --headless --continuous-play
python main.py --single-hand --seed 42 --reduced-motion --no-ambience
```

Copy `config.example.json` to `config.json` to select per-seat Ollama models, game mode, stacks, tournament levels, pacing, analysis depth, audio channels, persistence paths, and overlay styling. Explicit CLI options override the file. An `auto` model is resolved from installed Ollama models at runtime; if Ollama is unavailable, bounded fallback policy keeps the stream moving and the overlay reports fallback health. The real `python main.py` path uses Ollama-backed decisions by default; preview and smoke scripts are fixture drivers for layout testing.

The 24/7 variety rotation is enabled by default for the app. It changes safe hand-boundary table blocks such as championship sit-and-go, turbo sit-and-go, deep-stack cash, ante splash cash, and high-roller cash spotlight so the stream does not become ten hours of identical texture. Each block publishes `/state.variety`, updates the OBS browser-source labels and table skin, and gives AI players a public table-style hint without changing hidden-card privacy. Use `--no-variety-rotation` or `variety_rotation_enabled: false` for one fixed format.

Casino-floor variety is presentation-only and always tied back to the poker being shown. Between selected hands, the OBS overlay may use reel, wheel, card, standings, or marquee visual language to recap the winner, pot, hand class, all-in pressure, chip leader, hot streak, or next poker format. These are not playable side games: there are no credits, balances, buttons, deposits, cash-outs, wager prompts, or reward loops.

The Night City casino programming layer is also enabled by default for the OBS browser source. It rotates safe between-hand channel blocks such as the main poker table, blackjack room, baccarat pit, lounge recap, high-roller spotlight, rivalry heat, and room-transition intermission. Blackjack and baccarat are deterministic AI-only simulations with replayable `/events`, fictional bankroll deltas, host captions, and full-screen room visuals in `/overlay`; viewers can predict outcomes for bragging rights, but viewer input never affects cards, decisions, bankrolls, or payouts. Public state is exposed under `/state.casino`, and `/stream-info` reports the current room for Twitch title/panel automation. Use `--no-casino-program`, `casino_program_enabled: false`, `--casino-bankroll`, and `--casino-unit` to tune or disable the programming loop.

The fictional AI lounge is also enabled by default. It gives each profile a public synthetic "drink" and night-progress mood that can nudge risk, bluff, focus, table-talk flavor, and model temperature as the stream goes deeper into the session. The lounge state also publishes venue/district, scene name, service bot, table mood, rivalry, atmosphere line, service round, pressure index, table-wide effects, flavor notes, glassware, neon color, and visible player tells for OBS storytelling. This is simulation texture only: there is no real alcohol, the modifiers are visible in `/state.lounge` and the OBS rotator, the legal poker engine remains authoritative, and AI prompts still receive only the acting player's private cards plus public table context. Use `--no-ai-lounge`, `ai_lounge_enabled: false`, or `--ai-lounge-interval-hands` to tune it.

## OBS and audio

The full browser source is `http://127.0.0.1:8765/overlay`. Configure OBS at **1920×1080** with the same frame rate as the stream. Use `?compact=1` for the compact panel. The server binds only to localhost unless configured otherwise.

For production OBS browser-source operation, prefer `python main.py --headless --continuous-play`. Headless mode runs the same deterministic poker engine, Ollama decision path, audio state, `/state`, `/events`, and `/overlay` server without depending on a visible Qt control-room window. Use the normal Qt app when you want local controls; use headless when OBS is the product surface.

For Twitch-ready title, description, panel copy, moderation notes, audio capture, VOD guidance, and a preflight checklist, use the [Twitch Broadcast Guide](docs/TWITCH_BROADCAST_GUIDE.md). For unattended operation, use the [24/7 Operator Runbook](docs/OPERATOR_RUNBOOK.md). Copy-safe live metadata is also available from `http://127.0.0.1:8765/stream-info`. The subtle simulation-only overlay label is enabled by default and can be disabled with `overlay_disclaimer_enabled: false` or `--no-simulation-disclaimer` for private previews.

The header health badge summarizes normal play, live Ollama decisions, safe model fallback, checkpoint recovery, muted audio, persistence warnings, and SSE reconnection without exposing errors or local details. Each OBS seat card also exposes a compact model-source chip: `OLLAMA LIVE` means that player's recent decision came from the local model API, while `MODEL FALLBACK` means the deterministic legal fallback acted because Ollama was unavailable or cooling down. Preview these states with `--health-state normal`, `degraded`, `recovered`, `persistence-warning`, or `audio-muted`; the same sanitized health object is available in `/state` and `/health`.

- `/state` publishes backward-compatible state plus the version-2 player, pot, tournament, analysis, audio, health, program, league, storyline, and personality-arc schema.
- `/state.model_activity` and each player's `model_health` identify recent Ollama-vs-fallback decision source, resolved model, and bounded decision counts without exposing prompts.
- `/events` is a reconnectable server-sent event stream with monotonic IDs for animation and custom integrations.
- `/health` provides a minimal service probe.

The OBS browser source carries table cues and the casino music bed by default, so OBS's **Control audio via OBS** option can mix the `AI Poker` source directly. Headless production runs keep local desktop playback muted by default to avoid hearing the same show in both headphones and OBS. Use `--desktop-audio` only when you intentionally want the Python/Qt app to play locally, and use `?audio=0`, `?music=0`, or `overlay_audio_enabled: false` only if you are capturing that desktop app audio separately.

Before a long production run, use the preflight checker:

```bash
python scripts/production_preflight.py --url http://127.0.0.1:8765
```

Add `--strict-ollama` when you want launch to fail unless local Ollama models and recent live Ollama decisions are visible. Without strict mode, an Ollama outage is a warning because the stream remains rules-safe and visibly labeled as fallback.

Stream-safe WAV tracks placed in `music/` play as a shuffled casino music bed in the OBS browser source. Short samples in `sound_effects/` add tactile broadcast Foley; `card_flip.mp3` is served to the OBS browser source for card/deck reveals, and a matching `card_flip.wav` can override generated desktop card Foley if local desktop audio is explicitly enabled. Use `music_enabled`, `music_path`, `music_volume`, `music_shuffle`, and `sound_effects_path` in config, or launch with `--no-music`, `--music-path`, and `--music-volume`, to tune the playlist without changing the Foley or voice mix.

Optional generated voice clips are served through the OBS browser source too. The app can create short host and AI table-talk WAVs with a local base TTS backend, then optionally pass those WAVs through an operator-supplied RVC command template for Atlas/Vega/Nova/Echo-style voices. RVC is not bundled and is not required for the stream to run; configure `rvc_enabled`, `rvc_command`, and `rvc_models_path` only after you have a local RVC install and consented/original voice models such as `voices/rvc/atlas_rvc.pth`. Use `--no-voice-clips` to return to captions/browser speech only, or `--rvc-enabled --rvc-command ...` to bridge a local converter. Generated clips are cached under `voice_clip_cache_path` and played by `/overlay` as `/voice/*.wav`, so OBS **Control audio via OBS** remains the intended capture path.

Preview and inspect the real broadcast without Ollama:

```bash
python scripts/preview_overlay.py
python scripts/preview_gui.py ui-preview.png
python scripts/broadcast_smoke.py
python scripts/replay_hand.py --list
python scripts/benchmark_models.py --fixture
```

### Human-readable broadcast pacing

The default Broadcast pace guarantees a visible beat even when a model answers instantly: 320 ms between dealt seats and forced bets, 1.25 seconds per player action, 4.5 seconds between streets, and 6.5 seconds after each hand. Model inference and pacing both run away from Qt's event thread, so the interface stays responsive. Cinematic, Broadcast, and Brisk presets remain human-legible; CLI/config values can still be set to zero for headless tests and accelerated simulations.

Only newly dealt cards flip, only changed wagers slide chips forward, and winners retain a gold award treatment long enough to read the result. Reduced-motion mode disables these transitions without removing state information.

### Audience-first spectator design

The OBS scene uses a seated casino-table layout for 2–6 players, with a dealer/deck tray, visible pot chips, per-seat stack chips, committed wager chips, and a TV-style lower third for the current beat, plain-English headline, rotating info module, and recent-action crawl. It explains each street in plain English, expands dealer and blind abbreviations, identifies the acting player, describes the immediate choice, and labels equity as “chance to win.” A five-step hand tracker, chip-leader marker, big-pot and all-in tension cues, newcomer-friendly statistics, winner takeover, and restrained celebration animation keep the story legible even for viewers who have never played poker. These layers are event-driven, so idle polling never replays a card, chip, action, or award animation.

Player identity is presentation metadata on top of the poker state. The default cast now carries scalable OBS avatar archetypes, sigils, and short taglines, rendered as cyberpunk neon medallions inside each seat card. The OBS card faces use a stronger holo-card treatment with cyan/magenta suit glow, circuit-like borders, scanlines, and Night-City-style rim lighting. The scene also layers in an original rainy megacity skyline, diegetic neon signs, and holographic board labeling behind the felt. A presentation-only venue skin pulls public AI-lounge data into compact header chips, table labels, city signs, and footer copy so the room feels like a back-alley AI casino without covering the hand. Use `overlay_venue_theme_enabled: false`, `--no-venue-theme`, or `?venue=0` on the browser source to disable that skin while iterating. The same cyan/magenta glass treatment now extends across table, decision, big-pot, all-in, showdown, recap, winner, bumper, compact, and reduced-motion modes while preserving high-contrast cards, pot, actions, odds, and safety labels.

The broadcast director layer is enabled by default. `/state.presentation` tells the OBS page when to use table, decision, big-pot, all-in, showdown, or recap presentation. Use `?director=0` for a plain table source and `?visual_debug=1` to show safe-area/director labels while tuning OBS. `python scripts/visual_smoke.py` generates and checks deterministic visual fixtures for every director mode.

The OBS browser source is the canonical viewer-facing show surface; the Qt window is the local control room. To keep the stream understandable without requiring poker literacy or reading every panel, `/state.presentation` includes a showrunner beat with a one-line viewer focus, large non-reader labels, optional host voice cues, and `presentation.lower_third` for the main TV-broadcast information package. The lower third rotates public-state modules for pot/cost, equity, stacks, model health, casino program status, lounge mood, and chat prompts while the hand remains visually unobstructed. The legacy side broadcast desk is hidden during normal lower-third mode; use `?desk=1` to show it for debugging, `?hud=full` to restore dense seat diagnostics, or `?lowerthird=0` for a plain-table capture. Use `overlay_showrunner_enabled`, `overlay_voice_cues_enabled`, `overlay_voice_cooldown_ms`, `overlay_non_reader_mode`, `overlay_rotation_enabled`, `overlay_rotation_interval_ms`, and `overlay_narration_enabled` in config, or URL overrides like `?showrunner=0`, `?voice=0`, `?nonreader=0`, `?rotation=0`, `?rotation_ms=12000`, and `?narration=1` / `?tts=1`, to tune the TV-style guidance and optional browser speech narration.

Audience engagement prompts are enabled by default for the OBS source. A lower ribbon, winner banner plug, and intermission splash copy can ask viewers to follow the channel, call out the next winner, or discuss the current decision. These prompts are informational only and always carry bragging-rights/fictional-chip/no-wager framing. Use `overlay_engagement_enabled`, `overlay_follow_message`, and `overlay_chat_prompt` in config, CLI flags such as `--no-overlay-engagement`, or `?engagement=0` on the browser source to tune or disable them.

Safe casino-style bumpers are enabled by default between selected hands. They add short decorative reel, wheel, jackpot-light, chip-rain, winner, streak, chip-leader, all-in, and next-format intermissions derived from poker results only. Each bumper carries a relevance line explaining which pot, player, hand, standing, or upcoming table block it represents. They are not playable slots: there are no credits, balances, buttons, deposits, cash-outs, or wager prompts, and the bumper keeps the simulation-only/no-real-money label visible. Use `--no-casino-bumpers` or `casino_bumpers_enabled: false` to disable them.

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
python scripts/broadcast_smoke.py
python scripts/benchmark_models.py --fixture
```

The release gate covers legal-action tables, heads-up transitions, minimum raises, cumulative short all-ins, uncalled excess, folded dead money, independent side-pot winners, split/odd chips, burn/deck invariants, prompt privacy, malformed model output, metrics migration, checkpoints, SSE replay, 1080p/compact layouts, broadcast smoke artifacts, local model calibration, replay inspection, and a deterministic 10,000-hand chip-conservation soak. The slow evaluator proof checks all 2,598,960 five-card combinations against canonical category frequencies.

The longer product direction is documented in the [AI Poker Network Roadmap](docs/AI_SPORTS_NETWORK_ROADMAP.md).

## Main components

- `game.py` — deterministic rules state machine, modes, pots, events, checkpoints, and public state
- `player.py` — stable profiles and seat/contribution state
- `ollama_integration.py` — cached model discovery, strict private JSON decisions, validation, and fallback
- `analysis.py` — bounded asynchronous spectator equity
- `metrics.py` — atomic schema-v2 season and tournament records
- `broadcast_context.py` — deterministic program, league, storyline, and character arc snapshots
- `gui.py` — non-blocking Qt broadcast control room
- `overlay_server.py` — OBS page, state API, SSE events, and health probe
- `audio.py` / `commentary.py` — generated/custom effects, ambience, shuffled music bed, ducking, and optional speech

Season data, checkpoints, hand histories, and generated audio are written beneath `data/` by default. Resetting season statistics does not delete replay histories or checkpoints.
