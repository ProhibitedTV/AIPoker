# AI Poker 24/7 Operator Runbook

AI Poker is a local-first fictional poker broadcast. It uses simulated chips only: no deposits, payouts, prizes, or real-money wagering.

## First launch

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
ollama serve
python main.py
```

Expected local URLs:

- `http://127.0.0.1:8765/overlay` — OBS browser source.
- `http://127.0.0.1:8765/state` — full public state.
- `http://127.0.0.1:8765/events` — reconnectable event stream.
- `http://127.0.0.1:8765/health` — compact health probe.
- `http://127.0.0.1:8765/stream-info` — copy-safe channel metadata.

## OBS setup

Use a Browser Source at 1920×1080 pointed at `http://127.0.0.1:8765/overlay`. The plain URL is the production view: lower-third on, simplified HUD, and side desk hidden. Use `?desk=1`, `?hud=full`, or `?lowerthird=0` only for troubleshooting captures. Enable **Control audio via OBS** to capture browser-source table cues and the `music/` casino bed. Use `?audio=0` or `?music=0` only if you are separately capturing the desktop app audio and need to prevent doubling.

## 24/7 variety rotation

The app rotates through safe table blocks by default so the stream does not sit in one texture forever. The default playlist includes standard sit-and-go, turbo sit-and-go, deep-stack cash, ante splash cash, and high-roller cash spotlight blocks. Cash blocks can reset stacks and change blinds/antes at hand boundaries; tournament blocks wait for the current sit-and-go to complete before changing format. The active block is visible in `/state.variety`, OBS browser-source labels, and `/stream-info`.

Use `--no-variety-rotation` or `variety_rotation_enabled: false` to lock one format. Edit `variety_segments` in `config.json` to tune titles, durations, accents, table skins, cash blinds/antes, starting chips, and tournament hands-per-level.

Safe casino-style bumpers may appear between selected hands. They are decorative broadcast intermissions derived from poker results, not playable slot games. Keep `casino_bumper_responsible_label` enabled on public streams so the no-real-money simulation framing remains visible.

The Night City casino programming layer rotates OBS-first channel blocks around the poker table: main table, blackjack room, baccarat pit, lounge recap, high-roller spotlight, rivalry heat, and room-transition intermission. Blackjack and baccarat are AI-only simulations with fictional bankroll deltas, replayable `/events`, and `/state.casino`; viewers can make chat predictions for bragging rights only. Use `--no-casino-program` or `casino_program_enabled: false` if you want a pure poker feed, and check `/stream-info` to see the current public room title.

The bumper variety should always explain the poker on screen. Reel, wheel, card, standings, and marquee treatments are visual metaphors for the previous hand, all-in pressure, chip movement, leader board, hot streak, or next scheduled poker block. If a bumper feels disconnected from the hand, disable bumpers until the presentation data is fixed.

Audience engagement prompts are safe to leave on for public streams when they stay tied to the table: follow the channel, call the next winner, discuss the current decision, or react to a winner banner. They must remain bragging-rights-only and should never ask viewers to wager, deposit, cash out, or chase a reward loop. Use `--no-overlay-engagement`, `overlay_engagement_enabled: false`, or `/overlay?engagement=0` if a scene needs a cleaner look.

## Production launch guardrails

The app writes a local PID lock at `data/aipoker.pid` by default. This prevents accidental duplicate launches where one process owns the OBS port and another process owns audio. Use `--allow-multiple` only for deliberate preview/testing work.

Run the production preflight after starting the app and before leaving the stream unattended:

```bash
python scripts/production_preflight.py --url http://127.0.0.1:8765
```

Warnings are acceptable only when understood. For example, Ollama being closed is a warning because legal fallback keeps the broadcast moving, but it means AI entertainment is not fully live yet. Use `--strict-ollama` when launching a show that must not begin until local model decisions are visible.

## Before going live

```bash
python scripts/broadcast_smoke.py
python scripts/production_preflight.py --url http://127.0.0.1:8765
python scripts/soak_test.py --hands 10000 --players 6
python scripts/benchmark_models.py --fixture
python scripts/replay_hand.py --list
```

Confirm:

- `/health` returns `status: ok`.
- OBS canvas/output are 1920×1080.
- The simulation disclaimer is visible.
- The health badge says `OLLAMA LIVE`, `TABLE HEALTHY`, `SAFE FALLBACK`, `RECOVERED`, `AUDIO MUTED`, or `SAVE WARNING` as appropriate.
- Audio meters move once the OBS source is refreshed or unlocked with **Interact**.
- `artifacts/broadcast-smoke/overlay-full.html` and `overlay-compact.html` contain a non-empty table render.

## Health states

- `OLLAMA LIVE` — recent player decisions are coming from the local Ollama chat API.
- `TABLE HEALTHY` — overlay, persistence, and audio are ready while the model source is still warming or not yet observed.
- `SAFE FALLBACK` — Ollama is offline or cooling down; deterministic legal fallback play continues.
- `RECOVERED` — the last complete checkpoint was restored after a restart.
- `AUDIO MUTED` — gameplay continues without sound.
- `SAVE WARNING` — checkpoint or hand-history persistence needs attention.
- `RECONNECTING` — the browser source is reconnecting to `/events`.

## Recovery checklist

### Ollama stopped or slow

1. Leave the stream running; the rules engine keeps play legal with fallback decisions.
2. Restart Ollama: `ollama serve`.
3. Watch the overlay health badge return from `SAFE FALLBACK` to `OLLAMA LIVE`; the seat cards should also switch from `MODEL FALLBACK` to `OLLAMA LIVE` after each player acts again.
4. Use `python scripts/benchmark_models.py --models <model>` before assigning a new model to a seat.

### Qt GUI frozen or accidentally closed

1. Stop the process normally if possible.
2. Restart with `python main.py`.
3. The app restores the last completed-hand checkpoint and discards incomplete-hand state.
4. Verify `/health` and the hand number before leaving it unattended.

### OBS browser source stale

1. Click **Refresh** on the Browser Source.
2. If audio is silent, click **Interact** and click inside the source once to unlock browser autoplay.
3. If the source still shows old content, verify `http://127.0.0.1:8765/overlay` in a browser.

### Audio is playing but the table is missing

1. Check that only one AI Poker process is running. New production builds prevent duplicate launches with `data/aipoker.pid`, but older/stale processes may still exist.
2. Open `http://127.0.0.1:8765/health`. If it fails, restart the app and let the PID lock clear normally.
3. Refresh the OBS browser source after the overlay URL responds.

### Audio doubled or missing

1. Browser-source audio path: keep OBS **Control audio via OBS** enabled and use the plain `/overlay` URL.
2. Desktop-capture path: use `/overlay?audio=0` and capture the Python/Qt application audio separately.
3. Use `?music=0` if only the music bed is doubled.
4. Confirm `music/` contains WAV tracks, `sound_effects/card_flip.mp3` exists for browser card Foley, and `music_enabled` is true.

### Corrupted or partial data files

1. Do not edit `data/` while the app is running.
2. Stop the app.
3. Preserve the current `data/` directory for audit.
4. Restart; invalid metrics fall back to a blank schema-v2 season, while checkpoint failures surface as `SAVE WARNING`.
5. Use `python scripts/replay_hand.py --history data/hand_history.jsonl --list` to inspect usable histories.

### Host reboot

1. Start Ollama.
2. Start `python main.py`.
3. Confirm `RECOVERED` if a checkpoint was restored.
4. Refresh OBS and verify `/state`, `/events`, `/health`, and `/overlay`.

## Do not do this live

- Delete `data/` during a broadcast.
- Manually change table size, mode, or blinds mid-hand; the built-in variety rotation only changes formats at safe hand/tournament boundaries.
- Expose the overlay server beyond `127.0.0.1` without authentication and network hardening.
- Disable the simulation disclaimer on a public stream.
- Commit unreviewed copyrighted music into `music/`.
