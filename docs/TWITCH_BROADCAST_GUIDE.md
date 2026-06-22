# Twitch Broadcast Guide

AI Poker League is entertainment software: autonomous local AI players compete with fictional chips inside a deterministic poker simulation. It has no real-money wagering, deposits, prizes, promotions, or payouts. This guide is operational guidance, not legal advice; review Twitch's current rules before each launch.

## Copy-ready channel identity

**Recommended title**

> AI Poker League | Autonomous AI Players | Simulation Only | No Real Money

**Short description**

> Autonomous local AI players compete with fictional chips across persistent simulated seasons. AI Poker League is rules-checked entertainment software, not real-world play.

**Channel panel**

> AI Poker League is a local-first fictional sports broadcast. Named AI competitors play No-Limit Texas Hold'em with simulated chips while deterministic software controls cards, legal actions, pots, and results. Viewer odds are spectator analysis only. There are no deposits, prizes, cash-outs, promotions, or real-world stakes.

Choose a non-gambling category appropriate to a software simulation, such as **Software and Game Development**, when available. Confirm the current category names and platform rules in Twitch before going live.

The same safe metadata is available locally at `http://127.0.0.1:8765/stream-info` for copy/paste or automation.

## OBS browser source

1. Start AI Poker and confirm `http://127.0.0.1:8765/health` returns `status: ok`.
2. Add a Browser Source using `http://127.0.0.1:8765/overlay`.
3. Set the source to **1920×1080**, 30 or 60 FPS, and match the canvas/output frame rate.
4. Use `?compact=1` only for a smaller secondary scene.
5. Keep the server bound to `127.0.0.1`; do not expose it publicly without adding authentication and network hardening.

The simulation disclaimer is enabled by default. Set `overlay_disclaimer_enabled` to `false` in private configurations or launch with `--no-simulation-disclaimer` to hide it.

## Audio capture

- Capture desktop Foley, ambience, and voices with OBS Application Audio Capture.
- Leave `overlay_audio_enabled` off when desktop audio is already captured to prevent doubled cues.
- Keep voices above ambience and verify the limiter does not pump during winner stingers.
- Run a private recording before launch and listen for missing, doubled, or clipped audio.

## Chat, VODs, and clips

- Pin a message explaining that all chips, records, and standings are fictional.
- Block or correct claims that the channel accepts bets, deposits, or prizes.
- Do not solicit wagers, financial information, or off-platform transactions.
- Give moderators the copy-ready disclaimer above and a short escalation path.
- Keep the simulation tag visible in clips; include “simulation” or “AI league” in clip titles when context could be lost.
- Review VOD audio for copyrighted material; the built-in generated effects and ambience are the safest defaults.

## Before going live

- [ ] `/health`, `/state`, `/events`, `/stream-info`, and `/overlay` respond locally.
- [ ] OBS canvas and output are 1920×1080 with no safe-area clipping.
- [ ] The title, description, panel, and category clearly frame the stream as fictional AI entertainment.
- [ ] The overlay simulation disclaimer is visible.
- [ ] Ollama health or deterministic fallback status is visible and play continues during a model outage.
- [ ] Cards, chips, voices, ambience, and winner cues are readable without doubling.
- [ ] Continuous play, checkpoint persistence, and disk-space monitoring are enabled.
- [ ] Moderators have the disclaimer and know there are no real-world stakes or prizes.
- [ ] A short local recording has been reviewed before publishing the live scene.

## Safe shutdown and restart

Stop the application normally so audio, histories, and checkpoints close cleanly. After a reboot, verify `/health`, load the OBS browser source again if it is stale, and confirm the next complete hand updates persisted statistics before leaving the stream unattended.
