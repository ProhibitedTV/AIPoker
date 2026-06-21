"""Command-line entry point for AI Poker."""

import argparse

from audio import AudioService
from commentary import CommentaryService
from game import PokerGame
from gui import run_gui
from metrics import MetricsStore
from overlay_server import OverlayServer
from settings import AppSettings


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the AI Poker spectator table")
    parser.add_argument("--config", default="config.json", help="JSON settings file")
    parser.add_argument("--stage-delay", type=float, help="Seconds between game stages")
    parser.add_argument("--hand-delay", type=float, help="Seconds between hands")
    parser.add_argument("--animation-duration", type=float, help="Card animation duration in seconds")
    parser.add_argument("--overlay-port", type=int)
    parser.add_argument("--no-overlay", action="store_true")
    parser.add_argument("--tts", action="store_true")
    parser.add_argument("--mute", action="store_true", help="Disable generated game sound cues")
    parser.add_argument("--audio-volume", type=float, help="Sound cue volume from 0.0 to 1.0")
    parser.add_argument("--windowed", action="store_true")
    continuous = parser.add_mutually_exclusive_group()
    continuous.add_argument("--continuous-play", action="store_true")
    continuous.add_argument("--single-hand", action="store_true")
    return parser.parse_args(argv)


def build_settings(args):
    settings = AppSettings.load(args.config)
    if args.stage_delay is not None:
        settings.stage_delay_ms = max(0, int(args.stage_delay * 1000))
    if args.hand_delay is not None:
        settings.between_hands_delay_ms = max(0, int(args.hand_delay * 1000))
    if args.animation_duration is not None:
        settings.animation_duration_ms = max(0, int(args.animation_duration * 1000))
    if args.overlay_port is not None:
        settings.overlay_port = args.overlay_port
    if args.no_overlay:
        settings.overlay_enabled = False
    if args.tts:
        settings.tts_enabled = True
    if args.mute:
        settings.audio_enabled = False
    if args.audio_volume is not None:
        settings.audio_volume = max(0.0, min(1.0, args.audio_volume))
    if args.windowed:
        settings.fullscreen = False
    if args.continuous_play:
        settings.continuous_play = True
    if args.single_hand:
        settings.continuous_play = False
    return settings


def main(argv=None):
    settings = build_settings(parse_args(argv))
    metrics = MetricsStore(settings.stats_path)
    game = PokerGame(
        num_players=4,
        small_blind=settings.small_blind,
        big_blind=settings.big_blind,
        metrics_store=metrics,
    )
    commentary = CommentaryService(
        enabled=settings.tts_enabled,
        volume=settings.tts_volume,
        rate=settings.tts_rate,
        voice=settings.tts_voice,
    )
    game.subscribe(commentary.handle_event)
    audio = AudioService(
        enabled=settings.audio_enabled,
        volume=settings.audio_volume,
        cache_dir=settings.audio_cache_path,
    )
    game.subscribe(audio.handle_event)
    overlay = None
    if settings.overlay_enabled:
        overlay = OverlayServer(
            game,
            host=settings.overlay_host,
            port=settings.overlay_port,
            background=settings.overlay_background,
            accent=settings.overlay_accent,
            font=settings.overlay_font,
            layout=settings.overlay_layout,
        ).start()
        print(f"Streaming overlay: {overlay.url}")

    try:
        return run_gui(game, settings, audio_service=audio)
    finally:
        audio.close()
        commentary.close()
        if overlay:
            overlay.close()


if __name__ == "__main__":
    raise SystemExit(main())
