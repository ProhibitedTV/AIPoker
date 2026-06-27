"""Command-line entry point for AI Poker."""

import argparse
import sys

from audio import AudioService
from commentary import CommentaryService
from game import PokerGame
from metrics import MetricsStore
from overlay_server import OverlayServer
from settings import AppSettings


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the AI Poker spectator table")
    parser.add_argument("--config", default="config.json", help="JSON settings file")
    parser.add_argument("--stage-delay", type=float, help="Seconds between game stages")
    parser.add_argument("--action-delay", type=float, help="Minimum seconds each action remains readable")
    parser.add_argument("--deal-delay", type=float, help="Seconds between dealt seats and forced bets")
    parser.add_argument("--hand-delay", type=float, help="Seconds between hands")
    parser.add_argument("--animation-duration", type=float, help="Card animation duration in seconds")
    parser.add_argument("--overlay-port", type=int)
    parser.add_argument("--no-overlay", action="store_true")
    parser.add_argument("--no-simulation-disclaimer", action="store_true")
    parser.add_argument("--no-director", action="store_true", help="Disable directed OBS visual moments")
    parser.add_argument("--overlay-recap-duration", type=float, help="Seconds to hold between-hand recap visuals")
    parser.add_argument("--overlay-moment-duration", type=float, help="Seconds to hold major moment visuals")
    parser.add_argument("--overlay-visual-debug", action="store_true", help="Show OBS safe-area and director-mode labels")
    parser.add_argument("--no-casino-bumpers", action="store_true", help="Disable non-wagering casino-style intermission bumpers")
    parser.add_argument("--mode", choices=("cash", "tournament"))
    parser.add_argument("--players", type=int, choices=range(2, 7), metavar="2-6")
    parser.add_argument("--seed", type=int, help="Deterministic deck seed")
    parser.add_argument("--no-variety-rotation", action="store_true", help="Keep the same table format/style indefinitely")
    parser.add_argument("--variety-interval-hands", type=int, help="Fallback hand count for custom variety segments")
    parser.add_argument("--reduced-motion", action="store_true")
    parser.add_argument("--tts", action="store_true")
    parser.add_argument("--mute", action="store_true", help="Disable generated game sound cues")
    parser.add_argument("--no-ambience", action="store_true")
    parser.add_argument("--no-music", action="store_true", help="Disable the casino music playlist")
    parser.add_argument("--audio-volume", type=float, help="Sound cue volume from 0.0 to 1.0")
    parser.add_argument("--music-volume", type=float, help="Music-bed volume from 0.0 to 1.0")
    parser.add_argument("--music-path", help="Directory containing stream-safe WAV music tracks")
    parser.add_argument("--windowed", action="store_true")
    continuous = parser.add_mutually_exclusive_group()
    continuous.add_argument("--continuous-play", action="store_true")
    continuous.add_argument("--single-hand", action="store_true")
    return parser.parse_args(argv)


def build_settings(args):
    settings = AppSettings.load(args.config)
    if args.stage_delay is not None:
        settings.stage_delay_ms = max(0, int(args.stage_delay * 1000))
    if args.action_delay is not None:
        settings.action_delay_ms = max(0, int(args.action_delay * 1000))
    if args.deal_delay is not None:
        settings.deal_delay_ms = max(0, int(args.deal_delay * 1000))
    if args.hand_delay is not None:
        settings.between_hands_delay_ms = max(0, int(args.hand_delay * 1000))
    if args.animation_duration is not None:
        settings.animation_duration_ms = max(0, int(args.animation_duration * 1000))
    if args.overlay_port is not None:
        settings.overlay_port = args.overlay_port
    if args.no_overlay:
        settings.overlay_enabled = False
    if args.no_simulation_disclaimer:
        settings.overlay_disclaimer_enabled = False
    if args.no_director:
        settings.overlay_director_enabled = False
    if args.overlay_recap_duration is not None:
        settings.overlay_recap_duration_ms = max(1200, int(args.overlay_recap_duration * 1000))
    if args.overlay_moment_duration is not None:
        settings.overlay_moment_duration_ms = max(1200, int(args.overlay_moment_duration * 1000))
    if args.overlay_visual_debug:
        settings.overlay_visual_debug = True
    if args.no_casino_bumpers:
        settings.casino_bumpers_enabled = False
    if args.mode:
        settings.game_mode = args.mode
    if args.players:
        settings.table_size = args.players
    if args.seed is not None:
        settings.rng_seed = args.seed
    if args.no_variety_rotation:
        settings.variety_rotation_enabled = False
    if args.variety_interval_hands is not None:
        settings.variety_rotation_interval_hands = max(1, int(args.variety_interval_hands))
    if args.reduced_motion:
        settings.reduced_motion = True
    if args.tts:
        settings.tts_enabled = True
    if args.mute:
        settings.audio_enabled = False
    if args.no_ambience:
        settings.ambience_enabled = False
    if args.no_music:
        settings.music_enabled = False
    if args.audio_volume is not None:
        settings.audio_volume = max(0.0, min(1.0, args.audio_volume))
    if args.music_volume is not None:
        settings.music_volume = max(0.0, min(1.0, args.music_volume))
    if args.music_path:
        settings.music_path = args.music_path
    if args.windowed:
        settings.fullscreen = False
    if args.continuous_play:
        settings.continuous_play = True
    if args.single_hand:
        settings.continuous_play = False
    return settings


def main(argv=None):
    from gui import run_gui
    from PyQt5.QtWidgets import QApplication

    settings = build_settings(parse_args(argv))
    app = QApplication.instance() or QApplication(sys.argv)
    metrics = MetricsStore(settings.stats_path)
    game = PokerGame(
        num_players=settings.table_size,
        starting_chips=settings.starting_chips,
        small_blind=settings.small_blind,
        big_blind=settings.big_blind,
        metrics_store=metrics,
        mode=settings.game_mode,
        profiles=settings.player_profiles[: settings.table_size],
        rng_seed=settings.rng_seed,
        hands_per_level=settings.hands_per_level,
        tournament_levels=settings.tournament_levels,
        variety_rotation_enabled=settings.variety_rotation_enabled,
        variety_rotation_interval_hands=settings.variety_rotation_interval_hands,
        variety_segments=settings.variety_segments,
        casino_bumpers_enabled=settings.casino_bumpers_enabled,
        casino_bumper_duration_ms=settings.casino_bumper_duration_ms,
        casino_bumper_responsible_label=settings.casino_bumper_responsible_label,
        casino_bumper_frequency=settings.casino_bumper_frequency,
        history_path=settings.hand_history_path,
        checkpoint_path=settings.checkpoint_path,
        equity_samples=settings.equity_samples,
        analysis_depth=settings.analysis_depth,
        action_delay_ms=settings.action_delay_ms,
        deal_delay_ms=settings.deal_delay_ms,
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
        ambience_enabled=settings.ambience_enabled,
        ambience_volume=settings.ambience_volume,
        effects_volume=settings.effects_volume,
        music_enabled=settings.music_enabled,
        music_dir=settings.music_path,
        music_volume=settings.music_volume,
        music_shuffle=settings.music_shuffle,
        sound_effects_dir=settings.sound_effects_path,
    )
    commentary.on_speaking = audio.set_voice_active
    game.audio_state = {
        "enabled": audio.enabled or settings.overlay_audio_enabled,
        "desktop_enabled": audio.enabled,
        "browser_enabled": settings.overlay_audio_enabled,
        "master": settings.audio_volume,
        "ambience_enabled": audio.ambience_enabled,
        "ambience": settings.ambience_volume,
        "effects": settings.effects_volume,
        "music": settings.music_volume,
        "music_enabled": audio.music_enabled and bool(audio.music_tracks),
        "music_tracks": len(audio.music_tracks),
        "sound_effects": sorted(audio.sound_effects),
        "voice": settings.voice_volume,
    }
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
            reduced_motion=settings.reduced_motion,
            audio_enabled=settings.overlay_audio_enabled,
            disclaimer_enabled=settings.overlay_disclaimer_enabled,
            director_enabled=settings.overlay_director_enabled,
            recap_duration_ms=settings.overlay_recap_duration_ms,
            moment_duration_ms=settings.overlay_moment_duration_ms,
            visual_debug=settings.overlay_visual_debug,
            music_dir=settings.music_path,
            music_enabled=settings.music_enabled,
            sound_effects_dir=settings.sound_effects_path,
        ).start()
        game.service_health["overlay"] = "online"
        print(f"Streaming overlay: {overlay.url}")

    try:
        return run_gui(game, settings, audio_service=audio, app=app)
    finally:
        audio.close()
        commentary.close()
        game.close()
        if overlay:
            overlay.close()


if __name__ == "__main__":
    raise SystemExit(main())
