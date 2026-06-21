# AI Poker

AI Poker is a local-first Texas Hold'em broadcast engine. Ollama models make every player decision on the host machine while the game runs continuously, publishes an OBS-ready spectator overlay, and builds persistent player statistics across sessions.

## Project goal

The project is designed to become a genuinely watchable 24/7 AI poker stream, not merely a poker simulation that happens to run in a window. Work on the project should reinforce four priorities:

1. **Local AI:** Player decisions run through locally hosted Ollama models without requiring a cloud inference service.
2. **Unattended reliability:** Games continue automatically, recover playable tables when players run out of chips, and preserve season data across restarts.
3. **Human-readable drama:** Pacing, animations, commentary, actions, win rates, and clear table state should make each hand understandable to a casual viewer.
4. **Long-running stories:** Wins, losses, streaks, chip movement, and leaderboards should give viewers players and seasons worth following over time.

## Features

- Four Ollama-driven AI players with validated fold/check/bet/raise responses
- Non-blocking Qt deal and card-flip transitions
- Configurable stage, animation, and between-hand timing
- Continuous play plus pause/resume controls (`Space` toggles, `R` resumes)
- Browser-source overlay showing pot, blinds, board, dealer, next player, actions, chips, and win rates
- Live JSON state endpoint for custom widgets
- Text commentary feed and optional background text-to-speech
- Persistent hands, wins, ties, win rates, chip results, streaks, and chip history
- In-app leaderboard with an explicitly confirmed season reset

## Requirements

- Python 3.9+
- [Ollama](https://ollama.com/) running locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Start Ollama and make sure at least one local model is installed:

```bash
ollama serve
ollama list
```

The game automatically prefers installed model names containing `llama3`, `command-r`, or `qwen`. If none match, it requests `llama3:latest`; install that model or adjust model selection in `ollama_integration.py` before leaving the table unattended.

## Broadcast quick start

Create a local configuration, then start the table:

```bash
# Windows
Copy-Item config.example.json config.json

# macOS/Linux
cp config.example.json config.json

python main.py --continuous-play
```

For a narrated stream, install the optional TTS dependency and enable it:

```bash
pip install pyttsx3
python main.py --continuous-play --tts
```

By default the OBS/browser overlay is available at `http://127.0.0.1:8765/overlay` and machine-readable state at `http://127.0.0.1:8765/state`. Add the overlay URL to OBS as a Browser Source. The server binds only to localhost unless configured otherwise.

Before a long broadcast:

- Confirm every Ollama model responds locally.
- Add the browser overlay to OBS and verify its dimensions and theme.
- Tune stage and between-hand delays for viewers rather than maximum throughput.
- Confirm `data/leaderboard.json` is writable and backed up if the season matters.
- Disable host sleep and run the process under an appropriate supervisor for the operating system.
- Test pause/resume and audio levels before going live.

Useful command-line controls:

```bash
python main.py --stage-delay 3 --hand-delay 8 --animation-duration 0.8
python main.py --single-hand --windowed --no-overlay
python main.py --continuous-play --tts --overlay-port 9000
python main.py --config my-stream.json
```

Copy `config.example.json` to `config.json` to customize colors, fonts, pacing, blinds, overlay binding, TTS voice/rate/volume, and the leaderboard path. CLI values override the configuration file.

If Ollama temporarily fails to answer, a player safely falls back to folding after the request timeout. Set the `OLLAMA_TIMEOUT_SECONDS` environment variable to tune that timeout. The table automatically re-seats all players when fewer than two have chips, allowing continuous play without operator intervention.

## Keeping the stream engaging

The bundled interface exposes the information a viewer needs to follow a hand: current stage, pot, blinds, community cards, dealer, next player, chip stacks, actions, commentary, and running win percentages. The persistent leaderboard and chip-history chart turn isolated hands into an ongoing season.

When extending the project, favor features that improve spectator comprehension or create recurring narratives. Examples include distinct player identities and model personalities, richer hand commentary, tournament milestones, rivalries, notable-hand replays, and broadcast alerts for streaks or major chip swings. Any addition intended for 24/7 use should remain non-blocking, bounded in resource use, and safe to recover after a restart.

## Persistent leaderboard

Season statistics are written atomically to `data/leaderboard.json` after each hand. The file includes aggregate player records and the latest 1,000 chip-distribution snapshots. Use **Reset season stats** in the GUI to start a fresh season.

The `/state` response includes the same data under `leaderboard`, so custom overlays can build charts without reading local files.

## Development

The test suite does not require Ollama or a display:

```bash
pip install -r requirements-dev.txt
pytest -q
```

GitHub Actions runs the suite on Python 3.10 and 3.12 for every push and pull request targeting `main`.

Main modules:

- `game.py` - game lifecycle, events, pot accounting, serializable state
- `gui.py` - spectator UI, controls, animations, leaderboard
- `overlay_server.py` - OBS page and JSON endpoint
- `metrics.py` - durable season metrics
- `commentary.py` - queued optional TTS
- `settings.py` - JSON configuration model

## License

MIT
