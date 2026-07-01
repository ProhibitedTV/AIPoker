"""Command-line entry point for AI Poker."""

import argparse
import os
from pathlib import Path
import sys
import time
import traceback

from audio import AudioService
from commentary import CommentaryService
from game import PokerGame
from metrics import MetricsStore
from overlay_server import OverlayServer
from settings import AppSettings
from voice_service import VoiceService


class InstanceLock:
    """Best-effort local guard against launching two production tables at once."""

    def __init__(self, path, pid):
        self.path = Path(path)
        self.pid = int(pid)
        self.acquired = True

    def release(self):
        if not self.acquired:
            return
        try:
            current = self.path.read_text(encoding="utf-8").strip()
        except OSError:
            self.acquired = False
            return
        if current == str(self.pid):
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self.acquired = False


def _pid_is_running(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def acquire_instance_lock(lock_path, allow_multiple=False, pid=None, pid_checker=None):
    """Create a PID lock so OBS/audio don't accidentally point at split processes."""
    if allow_multiple or not lock_path:
        return None
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pid = int(pid or os.getpid())
    pid_checker = pid_checker or _pid_is_running

    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                existing_raw = path.read_text(encoding="utf-8").strip()
                existing_pid = int(existing_raw)
            except (OSError, ValueError):
                existing_pid = 0
            if existing_pid and pid_checker(existing_pid):
                raise RuntimeError(
                    f"AI Poker already appears to be running as PID {existing_pid}. "
                    f"Stop that process or relaunch with --allow-multiple if this is intentional."
                )
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise RuntimeError(f"Could not replace stale instance lock at {path}: {exc}") from exc
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"{pid}\n")
        return InstanceLock(path, pid)

    raise RuntimeError(f"Could not acquire instance lock at {path}")


def safe_print(message, file=None):
    try:
        print(message, file=file or sys.stdout, flush=True)
    except Exception:
        pass


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
    parser.add_argument("--no-overlay-rotation", action="store_true", help="Disable rotating OBS analysis desk panels")
    parser.add_argument("--overlay-rotation-interval", type=float, help="Seconds between OBS analysis desk panels")
    parser.add_argument("--overlay-narration", action="store_true", help="Enable browser speech narration for OBS analysis panels")
    parser.add_argument("--no-showrunner", action="store_true", help="Disable the OBS showrunner focus/voice cue layer")
    parser.add_argument("--no-overlay-voice-cues", action="store_true", help="Disable showrunner voice cue metadata and speech")
    parser.add_argument("--overlay-voice-cooldown", type=float, help="Minimum seconds between OBS showrunner voice cues")
    parser.add_argument("--no-non-reader-mode", action="store_true", help="Disable large icon/label helpers for non-poker viewers")
    parser.add_argument("--night-city-intensity", choices=("low", "medium", "high"), help="Cyberpunk visual intensity for the OBS source")
    parser.add_argument("--no-venue-theme", action="store_true", help="Disable OBS back-alley casino venue signage")
    parser.add_argument("--overlay-recap-duration", type=float, help="Seconds to hold between-hand recap visuals")
    parser.add_argument("--overlay-moment-duration", type=float, help="Seconds to hold major moment visuals")
    parser.add_argument("--overlay-visual-debug", action="store_true", help="Show OBS safe-area and director-mode labels")
    parser.add_argument("--no-overlay-engagement", action="store_true", help="Disable OBS follow/chat engagement prompts")
    parser.add_argument("--overlay-follow-message", help="Short follow-channel message for OBS engagement panels")
    parser.add_argument("--overlay-chat-prompt", help="Short chat prompt for OBS engagement panels")
    parser.add_argument("--no-casino-bumpers", action="store_true", help="Disable non-wagering casino-style intermission bumpers")
    parser.add_argument("--no-casino-program", action="store_true", help="Disable AI-only blackjack/baccarat/lounge programming blocks")
    parser.add_argument("--casino-bankroll", type=int, help="Starting fictional bankroll for AI-only side-room drama")
    parser.add_argument("--casino-unit", type=int, help="Fictional unit size for AI-only blackjack/baccarat side rooms")
    parser.add_argument("--mode", choices=("cash", "tournament"))
    parser.add_argument("--players", type=int, choices=range(2, 7), metavar="2-6")
    parser.add_argument("--seed", type=int, help="Deterministic deck seed")
    parser.add_argument("--allow-multiple", action="store_true", help="Permit more than one local AI Poker process")
    parser.add_argument("--single-instance-lock", help="PID lock path used to prevent duplicate OBS/audio owners")
    parser.add_argument("--no-variety-rotation", action="store_true", help="Keep the same table format/style indefinitely")
    parser.add_argument("--variety-interval-hands", type=int, help="Fallback hand count for custom variety segments")
    parser.add_argument("--no-ai-lounge", action="store_true", help="Disable fictional AI lounge behavior modifiers")
    parser.add_argument("--ai-lounge-interval-hands", type=int, help="Hands between AI lounge charge changes")
    parser.add_argument("--reduced-motion", action="store_true")
    parser.add_argument("--tts", action="store_true")
    parser.add_argument("--no-voice-clips", action="store_true", help="Disable generated OBS voice clips and use captions/browser fallback only")
    parser.add_argument("--voice-tts-backend", choices=("pyttsx3", "none"), help="Local base TTS backend used before optional RVC conversion")
    parser.add_argument("--voice-cache-path", help="Directory for generated OBS voice clips")
    parser.add_argument("--rvc-enabled", action="store_true", help="Enable optional RVC conversion command for generated voice clips")
    parser.add_argument("--rvc-command", nargs="+", help="RVC command template with placeholders like {input}, {output}, {voice}, {model}, {index}, {pitch}")
    parser.add_argument("--rvc-models-path", help="Directory containing per-profile RVC .pth/.index files")
    parser.add_argument("--rvc-timeout", type=float, help="Seconds before an RVC conversion command is abandoned")
    parser.add_argument("--rvc-pitch", type=int, help="Pitch shift passed through to the RVC command template")
    parser.add_argument("--mute", action="store_true", help="Disable generated game sound cues")
    parser.add_argument("--desktop-audio", action="store_true", help="Opt into local desktop audio playback; headless OBS runs keep this off by default")
    parser.add_argument("--no-ambience", action="store_true")
    parser.add_argument("--no-music", action="store_true", help="Disable the casino music playlist")
    parser.add_argument("--audio-volume", type=float, help="Sound cue volume from 0.0 to 1.0")
    parser.add_argument("--music-volume", type=float, help="Music-bed volume from 0.0 to 1.0")
    parser.add_argument("--music-path", help="Directory containing stream-safe WAV music tracks")
    parser.add_argument("--windowed", action="store_true")
    parser.add_argument("--headless", action="store_true", help="Run the OBS overlay/game loop without the Qt control room")
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
    if args.no_overlay_rotation:
        settings.overlay_rotation_enabled = False
    if args.overlay_rotation_interval is not None:
        settings.overlay_rotation_interval_ms = max(5000, int(args.overlay_rotation_interval * 1000))
    if args.overlay_narration:
        settings.overlay_narration_enabled = True
    if args.no_showrunner:
        settings.overlay_showrunner_enabled = False
    if args.no_overlay_voice_cues:
        settings.overlay_voice_cues_enabled = False
    if args.overlay_voice_cooldown is not None:
        settings.overlay_voice_cooldown_ms = max(3000, int(args.overlay_voice_cooldown * 1000))
    if args.no_non_reader_mode:
        settings.overlay_non_reader_mode = False
    if args.night_city_intensity:
        settings.overlay_night_city_intensity = args.night_city_intensity
    if args.no_venue_theme:
        settings.overlay_venue_theme_enabled = False
    if args.overlay_recap_duration is not None:
        settings.overlay_recap_duration_ms = max(1200, int(args.overlay_recap_duration * 1000))
    if args.overlay_moment_duration is not None:
        settings.overlay_moment_duration_ms = max(1200, int(args.overlay_moment_duration * 1000))
    if args.overlay_visual_debug:
        settings.overlay_visual_debug = True
    if args.no_overlay_engagement:
        settings.overlay_engagement_enabled = False
    if args.overlay_follow_message:
        settings.overlay_follow_message = args.overlay_follow_message[:96]
    if args.overlay_chat_prompt:
        settings.overlay_chat_prompt = args.overlay_chat_prompt[:96]
    if args.no_casino_bumpers:
        settings.casino_bumpers_enabled = False
    if args.no_casino_program:
        settings.casino_program_enabled = False
    if args.casino_bankroll is not None:
        settings.casino_program_starting_bankroll = max(1, int(args.casino_bankroll))
    if args.casino_unit is not None:
        settings.casino_program_unit = max(1, int(args.casino_unit))
    if args.mode:
        settings.game_mode = args.mode
    if args.players:
        settings.table_size = args.players
    if args.seed is not None:
        settings.rng_seed = args.seed
    if args.allow_multiple:
        settings.allow_multiple_instances = True
    if args.single_instance_lock:
        settings.single_instance_lock_path = args.single_instance_lock
    if args.no_variety_rotation:
        settings.variety_rotation_enabled = False
    if args.variety_interval_hands is not None:
        settings.variety_rotation_interval_hands = max(1, int(args.variety_interval_hands))
    if args.no_ai_lounge:
        settings.ai_lounge_enabled = False
    if args.ai_lounge_interval_hands is not None:
        settings.ai_lounge_interval_hands = max(1, int(args.ai_lounge_interval_hands))
    if args.reduced_motion:
        settings.reduced_motion = True
    if args.tts:
        settings.tts_enabled = True
    if args.no_voice_clips:
        settings.voice_clips_enabled = False
    if args.voice_tts_backend:
        settings.voice_tts_backend = args.voice_tts_backend
    if args.voice_cache_path:
        settings.voice_clip_cache_path = args.voice_cache_path
    if args.rvc_enabled:
        settings.rvc_enabled = True
    if args.rvc_command:
        settings.rvc_command = list(args.rvc_command)
    if args.rvc_models_path:
        settings.rvc_models_path = args.rvc_models_path
    if args.rvc_timeout is not None:
        settings.rvc_timeout_seconds = max(5, int(args.rvc_timeout))
    if args.rvc_pitch is not None:
        settings.rvc_pitch = int(args.rvc_pitch)
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
    if args.headless:
        settings.headless = True
    if settings.headless and not args.desktop_audio:
        settings.audio_enabled = False
    if args.desktop_audio and not args.mute:
        settings.audio_enabled = True
    if args.continuous_play:
        settings.continuous_play = True
    if args.single_hand:
        settings.continuous_play = False
    return settings


def _remaining_players(game):
    return sum(player.is_active and not player.folded for player in game.players)


def _sleep_ms(milliseconds):
    if milliseconds > 0:
        time.sleep(milliseconds / 1000)


def run_headless(game, settings):
    """Drive the same engine as the GUI for OBS-only 24/7 operation."""
    safe_print("Headless OBS runner active. Press Ctrl+C to stop.")
    while True:
        try:
            game.play_pre_flop()
            if _remaining_players(game) > 1:
                _sleep_ms(settings.stage_delay_ms)
                game.play_flop()
            if _remaining_players(game) > 1:
                _sleep_ms(settings.stage_delay_ms)
                game.play_turn()
            if _remaining_players(game) > 1:
                _sleep_ms(settings.stage_delay_ms)
                game.play_river()
            _sleep_ms(settings.stage_delay_ms)
            game.determine_winner()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            game.recover_from_error(exc)

        if not settings.continuous_play:
            return 0
        _sleep_ms(settings.between_tournaments_delay_ms if game.tournament_complete else settings.between_hands_delay_ms)


def main(argv=None):
    settings = build_settings(parse_args(argv))
    try:
        instance_lock = acquire_instance_lock(
            settings.single_instance_lock_path,
            allow_multiple=settings.allow_multiple_instances,
        )
    except RuntimeError as exc:
        safe_print(str(exc), file=sys.stderr)
        return 2

    app = None
    if not settings.headless:
        from gui import run_gui
        from PyQt5.QtWidgets import QApplication

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
        ai_lounge_enabled=settings.ai_lounge_enabled,
        ai_lounge_interval_hands=settings.ai_lounge_interval_hands,
        ai_lounge_max_charge=settings.ai_lounge_max_charge,
        casino_bumpers_enabled=settings.casino_bumpers_enabled,
        casino_bumper_duration_ms=settings.casino_bumper_duration_ms,
        casino_bumper_responsible_label=settings.casino_bumper_responsible_label,
        casino_bumper_frequency=settings.casino_bumper_frequency,
        casino_bumper_style=settings.casino_bumper_style,
        casino_program_enabled=settings.casino_program_enabled,
        casino_program_starting_bankroll=settings.casino_program_starting_bankroll,
        casino_program_unit=settings.casino_program_unit,
        casino_program_blocks=settings.casino_program_blocks,
        engagement_enabled=settings.overlay_engagement_enabled,
        engagement_follow_message=settings.overlay_follow_message,
        engagement_chat_prompt=settings.overlay_chat_prompt,
        showrunner_enabled=settings.overlay_showrunner_enabled,
        voice_cues_enabled=settings.overlay_voice_cues_enabled,
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
    voice_service = (
        VoiceService(
            enabled=settings.voice_clips_enabled,
            cache_dir=settings.voice_clip_cache_path,
            max_cache=settings.voice_clip_max_cache,
            tts_backend=settings.voice_tts_backend,
            tts_voice=settings.tts_voice,
            tts_rate=settings.tts_rate,
            tts_volume=settings.voice_volume,
            rvc_enabled=settings.rvc_enabled,
            rvc_command=settings.rvc_command,
            rvc_models_path=settings.rvc_models_path,
            rvc_timeout_seconds=settings.rvc_timeout_seconds,
            rvc_pitch=settings.rvc_pitch,
        )
        if settings.overlay_enabled
        else None
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
        "voice_clips_enabled": bool(voice_service and voice_service.enabled),
        "voice_backend": "rvc" if settings.rvc_enabled else settings.voice_tts_backend,
        "rvc_enabled": settings.rvc_enabled,
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
            rotation_enabled=settings.overlay_rotation_enabled,
            rotation_interval_ms=settings.overlay_rotation_interval_ms,
            narration_enabled=settings.overlay_narration_enabled,
            showrunner_enabled=settings.overlay_showrunner_enabled,
            voice_cues_enabled=settings.overlay_voice_cues_enabled,
            voice_cooldown_ms=settings.overlay_voice_cooldown_ms,
            non_reader_mode=settings.overlay_non_reader_mode,
            night_city_intensity=settings.overlay_night_city_intensity,
            venue_theme_enabled=settings.overlay_venue_theme_enabled,
            recap_duration_ms=settings.overlay_recap_duration_ms,
            moment_duration_ms=settings.overlay_moment_duration_ms,
            visual_debug=settings.overlay_visual_debug,
            music_dir=settings.music_path,
            music_enabled=settings.music_enabled,
            sound_effects_dir=settings.sound_effects_path,
            voice_service=voice_service,
        ).start()
        game.service_health["overlay"] = "online"
        safe_print(f"Streaming overlay: {overlay.url}")

    try:
        if settings.headless:
            return run_headless(game, settings)
        return run_gui(game, settings, audio_service=audio, app=app)
    finally:
        audio.close()
        commentary.close()
        game.close()
        if overlay:
            overlay.close()
        elif voice_service:
            voice_service.close()
        if instance_lock:
            instance_lock.release()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        try:
            path = Path("data") / "startup-crash.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise
