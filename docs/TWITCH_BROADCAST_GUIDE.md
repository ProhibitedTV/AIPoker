# Twitch Broadcast Guide

AI Poker League is entertainment software: autonomous local AI players compete with fictional chips inside a deterministic poker simulation and AI-only side-room casino segments. It has no real-money wagering, deposits, prizes, promotions, or payouts. This guide is operational guidance, not legal advice; review Twitch's current rules before each launch.

## Copy-ready channel identity

**Recommended title**

> Night City AI Gambling Den | Autonomous AI Casino | Simulation Only | No Real Money

**Short description**

> Autonomous local AI players compete with fictional chips across persistent simulated seasons, poker tables, and AI-only casino rooms. This is rules-checked entertainment software, not real-world play.

**Channel panel**

> AI Poker League is a local-first fictional casino broadcast. Named AI competitors play No-Limit Texas Hold'em plus AI-only blackjack/baccarat side-room segments with simulated chips and fictional bankrolls while deterministic software controls cards, legal actions, pots, and results. Viewer odds and chat predictions are spectator entertainment only. There are no deposits, prizes, cash-outs, promotions, or real-world stakes.

Choose a non-gambling category appropriate to a software simulation, such as **Software and Game Development**, when available. Confirm the current category names and platform rules in Twitch before going live.

The same safe metadata is available locally at `http://127.0.0.1:8765/stream-info` for copy/paste or automation.

The current room title is exposed in `/stream-info.casino_program`; use it for Twitch panel/title automation if you want the channel copy to reflect poker, blackjack, baccarat, lounge recap, or intermission blocks.

## OBS browser source

1. Start AI Poker and confirm `http://127.0.0.1:8765/health` returns `status: ok`.
2. Add a Browser Source using `http://127.0.0.1:8765/overlay`.
3. Set the source to **1920×1080**, 30 or 60 FPS, and match the canvas/output frame rate.
4. Use `?compact=1` only for a smaller secondary scene.
5. Keep the server bound to `127.0.0.1`; do not expose it publicly without adding authentication and network hardening.

The simulation disclaimer is enabled by default. Set `overlay_disclaimer_enabled` to `false` in private configurations or launch with `--no-simulation-disclaimer` to hide it.

## Broadcast health badge

The header badge gives viewers a calm summary while `/state` and `/health` expose the same sanitized fields for operators:

- **TABLE HEALTHY** — local broadcast systems are ready.
- **SAFE FALLBACK** — Ollama is unavailable or cooling down; deterministic legal play continues.
- **RECOVERED** — the last complete checkpoint was restored after restart.
- **AUDIO MUTED** — visuals and gameplay remain live without sound.
- **SAVE WARNING** — hand history or checkpoint persistence needs operator attention.
- **RECONNECTING** — the browser source is catching up to the event feed.

No badge or health payload contains prompts, exception text, local paths, or private card data. Exercise fixtures without Ollama before changing an OBS scene:

```bash
python scripts/preview_overlay.py --port 8771 --health-state normal
python scripts/preview_overlay.py --port 8772 --health-state degraded
python scripts/preview_overlay.py --port 8773 --health-state recovered
python scripts/preview_overlay.py --port 8774 --health-state persistence-warning
python scripts/preview_overlay.py --port 8775 --health-state audio-muted
```

## Audio capture

- For the simplest OBS setup, enable **Control audio via OBS** on the Browser Source and let `http://127.0.0.1:8765/overlay` carry table cues plus the casino music bed.
- Headless production runs keep local desktop playback muted by default. If you still hear the source in headphones, set the OBS `AI Poker` source monitoring to **Monitor Off** in Advanced Audio Properties.
- Use `--desktop-audio` plus `?audio=0`, `?music=0`, or `overlay_audio_enabled: false` only when desktop Foley, casino music, ambience, and voices are captured separately through OBS Application Audio Capture.
- Generated host/player voice clips, including optional operator-supplied RVC conversions, are also browser-source audio. Keep them on this path to avoid doubled headphone and OBS playback.
- The default playlist scans `music/` for WAV tracks, shuffles them, and serves them to the browser source; local desktop playback is opt-in.
- The browser source also scans `sound_effects/` for short Foley samples; `card_flip.mp3` is used for single-card/deck reveal cues when audio is enabled.
- Use `--no-music` for silent test streams or `--music-volume 0.12` to tuck the bed farther under table action.
- Keep voices above ambience and verify the limiter does not pump during winner stingers.
- Review custom tracks for stream rights before going live; user-supplied music is outside the built-in generated-safe Foley/ambience set.
- Run a private recording before launch and listen for missing, doubled, or clipped audio. If OBS meters are silent, refresh the browser source and confirm the source URL is not using `?audio=0`.
- Generate local smoke artifacts with `python scripts/broadcast_smoke.py`; review `artifacts/broadcast-smoke/overlay-full.html`, `overlay-compact.html`, `state.json`, and `health.json` before long unattended runs.

## Chat, VODs, and clips

- Pin a message explaining that all chips, records, and standings are fictional.
- Block or correct claims that the channel accepts bets, deposits, or prizes.
- Do not solicit wagers, financial information, or off-platform transactions.
- Keep engagement prompts such as “call the next winner” as bragging-rights-only chat participation. Do not add odds, stakes, rewards, credits, deposits, cash-outs, or betting-style loops.
- Give moderators the copy-ready disclaimer above and a short escalation path.
- Keep the simulation tag visible in clips; include “simulation” or “AI league” in clip titles when context could be lost.
- Review VOD audio for copyrighted material; the built-in generated effects and ambience are the safest defaults, while `music/` contains operator-supplied tracks.

## Before going live

- [ ] `/health`, `/state`, `/events`, `/stream-info`, and `/overlay` respond locally and the health badge matches the fixture or live service state.
- [ ] `python scripts/broadcast_smoke.py` produced fresh full and compact overlay artifacts.
- [ ] OBS canvas and output are 1920×1080 with no safe-area clipping.
- [ ] At 50% OBS preview scale, the board cards, current pot, active decision, player stack, and lower-third headline can be identified within 2-3 seconds.
- [ ] The title, description, panel, and category clearly frame the stream as fictional AI entertainment.
- [ ] The overlay simulation disclaimer is visible.
- [ ] Ollama health or deterministic fallback status is visible and play continues during a model outage.
- [ ] Cards, chips, music, voices, ambience, and winner cues are readable without doubling.
- [ ] Continuous play, checkpoint persistence, and disk-space monitoring are enabled.
- [ ] The current program segment, season story, and league context are visible in the bottom ticker.
- [ ] Moderators have the disclaimer and know there are no real-world stakes or prizes.
- [ ] A short local recording has been reviewed before publishing the live scene.

## Safe shutdown and restart

Stop the application normally so audio, histories, and checkpoints close cleanly. After a reboot, verify `/health`, load the OBS browser source again if it is stale, and confirm the next complete hand updates persisted statistics before leaving the stream unattended.
