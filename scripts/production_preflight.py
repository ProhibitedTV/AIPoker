"""Production preflight checks for the OBS-first AI Poker broadcast."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ollama_integration import get_available_models  # noqa: E402
from settings import AppSettings  # noqa: E402


FORBIDDEN_CALLS_TO_ACTION = ("deposit", "cash out", "spin again")
REQUIRED_OVERLAY_MARKERS = (
    "AI POKER",
    "SIMULATION ONLY",
    "FICTIONAL CHIPS",
    "NO REAL MONEY",
    'id="casinoBumper"',
    'id="audienceRibbon"',
    'id="winnerEngagement"',
    'id="broadcastRotator"',
    'id="healthPill"',
    "OLLAMA LIVE",
    "MODEL FALLBACK",
)


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


def _result(name, status, detail):
    return CheckResult(name=name, status=status, detail=detail)


def _fetch_text(url, timeout=4):
    with urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _fetch_json(url, timeout=4):
    return json.loads(_fetch_text(url, timeout=timeout))


def _writable_parent(path):
    target = Path(path)
    parent = target if target.suffix == "" else target.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".aipoker-preflight-", dir=parent, delete=True):
        return True


def check_settings(settings):
    checks = []
    checks.append(_result("overlay.enabled", "pass" if settings.overlay_enabled else "fail", "OBS browser source is enabled." if settings.overlay_enabled else "Overlay is disabled; OBS will have no table source."))
    checks.append(_result("overlay.localhost", "pass" if settings.overlay_host in {"127.0.0.1", "localhost"} else "warn", f"Overlay host is {settings.overlay_host!r}. Keep public streams on localhost unless you add network hardening."))
    checks.append(_result("continuous.play", "pass" if settings.continuous_play else "warn", "Continuous play is enabled." if settings.continuous_play else "Single-hand mode is set; the 24/7 stream will stop."))
    checks.append(_result("simulation.disclaimer", "pass" if settings.overlay_disclaimer_enabled else "fail", "Simulation-only disclaimer is enabled." if settings.overlay_disclaimer_enabled else "Simulation disclaimer is disabled; public release should keep it visible."))
    checks.append(_result("director.layer", "pass" if settings.overlay_director_enabled else "warn", "Broadcast director layer is enabled." if settings.overlay_director_enabled else "Director moments are disabled; the overlay will be flatter."))
    checks.append(_result("analysis.rotation", "pass" if settings.overlay_rotation_enabled else "warn", "OBS analysis rotator is enabled." if settings.overlay_rotation_enabled else "Analysis rotator is disabled; long sessions may feel repetitive."))
    checks.append(_result("safe.bumpers", "pass" if settings.casino_bumpers_enabled else "warn", "Safe casino-style bumpers are enabled." if settings.casino_bumpers_enabled else "Casino-style intermission variety is disabled."))
    checks.append(_result("single.instance", "pass" if not settings.allow_multiple_instances else "warn", "Single-instance launch guard is enabled." if not settings.allow_multiple_instances else "Multiple instances are allowed; OBS/audio ownership can become confusing."))
    return checks


def check_paths(settings):
    checks = []
    for name, path in (
        ("stats.path", settings.stats_path),
        ("checkpoint.path", settings.checkpoint_path),
        ("hand.history.path", settings.hand_history_path),
        ("audio.cache.path", settings.audio_cache_path),
        ("instance.lock.path", settings.single_instance_lock_path),
    ):
        try:
            _writable_parent(path)
            checks.append(_result(name, "pass", f"Writable parent for {path}."))
        except OSError as exc:
            checks.append(_result(name, "fail", f"Cannot write near {path}: {exc}"))

    music_dir = Path(settings.music_path)
    sound_dir = Path(settings.sound_effects_path)
    music_count = len([path for path in music_dir.glob("*") if path.suffix.lower() in {".wav", ".mp3", ".ogg"}]) if music_dir.exists() else 0
    sound_count = len([path for path in sound_dir.glob("*") if path.suffix.lower() in {".wav", ".mp3", ".ogg"}]) if sound_dir.exists() else 0
    checks.append(_result("music.assets", "pass" if music_count else "warn", f"{music_count} music track(s) found in {music_dir}."))
    checks.append(_result("sound.assets", "pass" if sound_count else "warn", f"{sound_count} sound effect(s) found in {sound_dir}."))
    return checks


def check_static_overlay_source():
    checks = []
    text = Path("overlay_server.py").read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_OVERLAY_MARKERS if marker not in text]
    checks.append(_result("overlay.markers", "pass" if not missing else "fail", "Static overlay contains required production markers." if not missing else f"Missing overlay markers: {', '.join(missing)}"))
    lowered = text.lower()
    forbidden = [term for term in FORBIDDEN_CALLS_TO_ACTION if term in lowered]
    checks.append(_result("overlay.no_wager_cta", "pass" if not forbidden else "fail", "No interactive wagering calls-to-action in overlay source." if not forbidden else f"Forbidden terms in overlay source: {', '.join(forbidden)}"))
    return checks


def check_ollama(strict=False):
    try:
        models = get_available_models(force=True)
    except Exception as exc:  # pragma: no cover - defensive only
        models = []
        detail = f"Ollama model discovery failed: {exc}"
    else:
        detail = f"{len(models)} local Ollama model(s) available." if models else "No local Ollama models currently visible; gameplay will use visible legal fallback until Ollama returns."
    if models:
        return [_result("ollama.models", "pass", detail)]
    return [_result("ollama.models", "fail" if strict else "warn", detail)]


def check_live_server(base_url, strict_ollama=False):
    base = base_url.rstrip("/")
    checks = []
    try:
        health = _fetch_json(f"{base}/health")
        state = _fetch_json(f"{base}/state")
        stream_info = _fetch_json(f"{base}/stream-info")
        overlay = _fetch_text(f"{base}/overlay")
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        return [_result("live.server", "fail", f"Could not read live overlay server at {base}: {exc}")]

    checks.append(_result("live.health", "pass" if health.get("status") in {"ok", "warning"} else "fail", f"/health status is {health.get('status')!r}."))
    checks.append(_result("live.state_schema", "pass" if state.get("schema_version") == 2 else "fail", f"/state schema_version is {state.get('schema_version')!r}."))
    checks.append(_result("live.overlay_html", "pass" if "AI Poker Overlay" in overlay and "casinoBumper" in overlay else "fail", "Overlay HTML includes the OBS show surface."))
    checks.append(_result("live.stream_info", "pass" if "No Real Money" in stream_info.get("title", "") else "fail", "Stream metadata carries no-real-money framing."))

    lowered_overlay = overlay.lower()
    forbidden = [term for term in FORBIDDEN_CALLS_TO_ACTION if term in lowered_overlay]
    checks.append(_result("live.no_wager_cta", "pass" if not forbidden else "fail", "Live overlay has no interactive wagering calls-to-action." if not forbidden else f"Forbidden terms in live overlay: {', '.join(forbidden)}"))

    health_overall = (state.get("health") or {}).get("overall")
    source = (state.get("model_activity") or {}).get("source")
    if source == "ollama":
        checks.append(_result("live.ollama_source", "pass", "Recent live decisions are coming from Ollama."))
    elif strict_ollama:
        checks.append(_result("live.ollama_source", "fail", f"Recent live decision source is {source or 'pending'}, not Ollama."))
    else:
        checks.append(_result("live.ollama_source", "warn", f"Recent live decision source is {source or 'pending'}; fallback is visible but AI entertainment is not fully live yet."))
    checks.append(_result("live.health_overall", "pass" if health_overall in {"normal", "recovered", "notice"} else "warn", f"Public health state is {health_overall!r}."))
    return checks


def run_preflight(settings, url=None, strict_ollama=False):
    checks = []
    checks.extend(check_settings(settings))
    checks.extend(check_paths(settings))
    checks.extend(check_static_overlay_source())
    checks.extend(check_ollama(strict=strict_ollama))
    if url:
        checks.extend(check_live_server(url, strict_ollama=strict_ollama))
    return checks


def print_human(checks):
    order = {"fail": 0, "warn": 1, "pass": 2}
    for check in sorted(checks, key=lambda item: (order.get(item.status, 9), item.name)):
        icon = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(check.status, check.status.upper())
        print(f"[{icon}] {check.name}: {check.detail}")
    failures = sum(1 for check in checks if check.status == "fail")
    warnings = sum(1 for check in checks if check.status == "warn")
    print(f"\nProduction preflight: {failures} failure(s), {warnings} warning(s), {len(checks)} check(s).")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Check AI Poker production readiness for an OBS browser-source stream")
    parser.add_argument("--config", default="config.json", help="Settings file to inspect")
    parser.add_argument("--url", help="Optional running overlay server URL, such as http://127.0.0.1:8765")
    parser.add_argument("--strict-ollama", action="store_true", help="Fail if Ollama models or live Ollama decisions are unavailable")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    settings = AppSettings.load(args.config)
    checks = run_preflight(settings, url=args.url, strict_ollama=args.strict_ollama)
    if args.json:
        print(json.dumps([asdict(check) for check in checks], indent=2))
    else:
        print_human(checks)
    return 1 if any(check.status == "fail" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
