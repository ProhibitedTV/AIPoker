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

Use a Browser Source at 1920×1080 pointed at `http://127.0.0.1:8765/overlay`. Enable **Control audio via OBS** to capture browser-source table cues and the `music/` casino bed. Use `?audio=0` or `?music=0` only if you are separately capturing the desktop app audio and need to prevent doubling.

## 24/7 variety rotation

The app rotates through safe table blocks by default so the stream does not sit in one texture forever. The default playlist includes standard sit-and-go, turbo sit-and-go, deep-stack cash, ante splash cash, and high-roller cash spotlight blocks. Cash blocks can reset stacks and change blinds/antes at hand boundaries; tournament blocks wait for the current sit-and-go to complete before changing format. The active block is visible in `/state.variety`, OBS browser-source labels, and `/stream-info`.

Use `--no-variety-rotation` or `variety_rotation_enabled: false` to lock one format. Edit `variety_segments` in `config.json` to tune titles, durations, accents, table skins, cash blinds/antes, starting chips, and tournament hands-per-level.

Safe casino-style bumpers may appear between selected hands. They are decorative broadcast intermissions derived from poker results, not playable slot games. Keep `casino_bumper_responsible_label` enabled on public streams so the no-real-money simulation framing remains visible.

## Before going live

```bash
python scripts/broadcast_smoke.py
python scripts/soak_test.py --hands 10000 --players 6
python scripts/benchmark_models.py --fixture
python scripts/replay_hand.py --list
```

Confirm:

- `/health` returns `status: ok`.
- OBS canvas/output are 1920×1080.
- The simulation disclaimer is visible.
- The health badge says `TABLE HEALTHY`, `SAFE FALLBACK`, `RECOVERED`, `AUDIO MUTED`, or `SAVE WARNING` as appropriate.
- Audio meters move once the OBS source is refreshed or unlocked with **Interact**.
- `artifacts/broadcast-smoke/overlay-full.html` and `overlay-compact.html` contain a non-empty table render.

## Health states

- `TABLE HEALTHY` — overlay, persistence, and audio are ready.
- `SAFE FALLBACK` — Ollama is offline or cooling down; deterministic legal fallback play continues.
- `RECOVERED` — the last complete checkpoint was restored after a restart.
- `AUDIO MUTED` — gameplay continues without sound.
- `SAVE WARNING` — checkpoint or hand-history persistence needs attention.
- `RECONNECTING` — the browser source is reconnecting to `/events`.

## Recovery checklist

### Ollama stopped or slow

1. Leave the stream running; the rules engine keeps play legal with fallback decisions.
2. Restart Ollama: `ollama serve`.
3. Watch the overlay health badge return from `SAFE FALLBACK`.
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
