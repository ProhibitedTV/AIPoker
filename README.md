# AI Poker Game

AI Poker is a PyQt5 Texas Hold'em spectator table whose players use local Ollama models. It can run continuously for an unattended stream, publish a live OBS overlay, narrate the action, and retain a season leaderboard across restarts.

## Features

- Four Ollama-driven AI players with validated fold/check/bet/raise responses
- Non-blocking Qt deal and card-flip transitions
- Configurable stage, animation, and between-hand timing
- Continuous play plus pause/resume controls (`Space` toggles, `R` resumes)
- Browser-source overlay showing pot, blinds, board, dealer, next player, actions, chips, and win rates
- Live JSON state endpoint for custom widgets
- Text commentary feed and optional background text-to-speech
- Persistent hands, wins, win rates, chip results, streaks, and chip history
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

Optional narration uses `pyttsx3`:

```bash
pip install pyttsx3
```

## Run

```bash
python main.py
```

By default the OBS/browser overlay is available at `http://127.0.0.1:8765/overlay` and machine-readable state at `http://127.0.0.1:8765/state`. Add the overlay URL to OBS as a Browser Source. The server binds only to localhost unless configured otherwise.

Useful command-line controls:

```bash
python main.py --stage-delay 3 --hand-delay 8 --animation-duration 0.8
python main.py --single-hand --windowed --no-overlay
python main.py --continuous-play --tts --overlay-port 9000
python main.py --config my-stream.json
```

Copy `config.example.json` to `config.json` to customize colors, fonts, pacing, blinds, overlay binding, TTS voice/rate/volume, and the leaderboard path. CLI values override the configuration file.

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

- `game.py` — game lifecycle, events, pot accounting, serializable state
- `gui.py` — spectator UI, controls, animations, leaderboard
- `overlay_server.py` — OBS page and JSON endpoint
- `metrics.py` — durable season metrics
- `commentary.py` — queued optional TTS
- `settings.py` — JSON configuration model

## License

MIT
