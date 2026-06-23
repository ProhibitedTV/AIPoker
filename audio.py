"""Non-blocking, dependency-free generated sound cues and music for game events."""

import hashlib
from pathlib import Path
from queue import Empty, Full, Queue
import math
import os
import random
import shutil
import struct
import subprocess
import sys
from threading import Event, Thread
import time
import wave


class AudioService:
    MUSIC_EXTENSIONS = {".wav"}
    SOUND_EFFECT_EXTENSIONS = {".wav"}

    def __init__(
        self,
        enabled=True,
        volume=0.35,
        cache_dir="data/audio_cache",
        playback=None,
        ambience_enabled=False,
        ambience_volume=0.16,
        effects_volume=0.72,
        music_enabled=False,
        music_dir="music",
        music_volume=0.18,
        music_shuffle=True,
        sound_effects_dir="sound_effects",
    ):
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self.ambience_enabled = bool(ambience_enabled)
        self.ambience_volume = max(0.0, min(1.0, ambience_volume))
        self.effects_volume = max(0.0, min(1.0, effects_volume))
        self.music_enabled = bool(music_enabled)
        self.music_dir = Path(music_dir)
        self.music_volume = max(0.0, min(1.0, music_volume))
        self.music_shuffle = bool(music_shuffle)
        self.sound_effects_dir = Path(sound_effects_dir)
        self.cache_dir = Path(cache_dir)
        self._backend_owner = None
        self._playback_is_async = False
        self._playback = playback or self._detect_playback()
        self.available = self._playback is not None
        self.enabled = self.enabled and self.available
        self._queue = Queue(maxsize=12)
        self._stop = Event()
        self._music_interrupt = Event()
        self._thread = None
        self._ambience_thread = None
        self._music_thread = None
        self._voice_active = False
        self._cues = {}
        self.music_tracks = self._discover_music_tracks()
        self.sound_effects = self._discover_sound_effects()
        self._music_rng = random.Random("casino-music-playlist")
        if self.available:
            self._cues = self._ensure_cues()
            self._thread = Thread(target=self._run, name="poker-audio", daemon=True)
            self._thread.start()
            if self.ambience_enabled and self._cues.get("ambience"):
                self._ambience_thread = Thread(target=self._run_ambience, name="poker-ambience", daemon=True)
                self._ambience_thread.start()
            self._ensure_music_thread()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled) and self.available
        if not self.enabled and self._backend_owner:
            self._backend_owner.stop_all()
        self._music_interrupt.set()

    def set_channel_volumes(self, master=None, ambience=None, effects=None, music=None):
        changed = False
        music_changed = False
        if master is not None:
            self.volume = max(0.0, min(1.0, float(master)))
            changed = True
            music_changed = True
        if ambience is not None:
            self.ambience_volume = max(0.0, min(1.0, float(ambience)))
            changed = True
        if effects is not None:
            self.effects_volume = max(0.0, min(1.0, float(effects)))
            changed = True
        if music is not None:
            self.music_volume = max(0.0, min(1.0, float(music)))
            music_changed = True
        if changed and self.available:
            self._cues = self._ensure_cues()
            self._prune_cache()
        if music_changed:
            self._prune_cache()
            if self._backend_owner:
                self._backend_owner.stop_music()
            self._music_interrupt.set()

    def set_ambience_enabled(self, enabled):
        self.ambience_enabled = bool(enabled)
        if not self.ambience_enabled and self._backend_owner:
            self._backend_owner.stop_ambience()

    def set_music_enabled(self, enabled):
        self.music_enabled = bool(enabled)
        if self.music_enabled:
            self._ensure_music_thread()
        elif self._backend_owner:
            self._backend_owner.stop_music()
        self._music_interrupt.set()

    def set_voice_active(self, active):
        """Duck nonessential layers while narration or player speech is active."""
        self._voice_active = bool(active)
        if active and self._backend_owner:
            self._backend_owner.stop_ambience()
            self._backend_owner.stop_music()
        self._music_interrupt.set()

    def handle_event(self, event):
        if not self.enabled or not self.available:
            return
        cue = self._cue_for_event(event)
        if not cue:
            return
        try:
            self._queue.put_nowait(cue)
        except Full:
            try:
                self._queue.get_nowait()
            except Empty:
                pass
            try:
                self._queue.put_nowait(cue)
            except Full:
                pass

    @staticmethod
    def _cue_for_event(event):
        event_type = event.get("type")
        if event_type == "deal":
            return "card"
        if event_type == "community":
            return "reveal"
        if event_type == "winner":
            return "winner"
        if event_type in {"all_in", "tournament_winner"}:
            return "all_in"
        if event_type == "elimination":
            return "elimination"
        if event_type == "error":
            return "error"
        if event_type == "action":
            message = event.get("message", "").lower()
            if "all-in" in message:
                return "all_in"
            return "chips" if any(word in message for word in ("bet", "raise", "blind")) else "action"
        return None

    def _run(self):
        while not self._stop.is_set():
            try:
                cue = self._queue.get(timeout=0.2)
            except Empty:
                continue
            path = self._cues.get(cue)
            if path and (not self._voice_active or cue in {"winner", "all_in", "error"}):
                try:
                    self._playback(path)
                except (OSError, RuntimeError, subprocess.SubprocessError):
                    continue

    def _run_ambience(self):
        while not self._stop.is_set():
            if self.enabled and self.ambience_enabled and not self._voice_active:
                try:
                    self._playback(self._cues["ambience"])
                except (OSError, RuntimeError, subprocess.SubprocessError):
                    pass
            self._stop.wait(7.5)

    def _run_music(self):
        playlist = []
        index = 0
        while not self._stop.is_set():
            if (
                not self.enabled
                or not self.music_enabled
                or self._voice_active
                or self._music_gain() <= 0
                or not self.music_tracks
            ):
                self._music_interrupt.wait(0.5)
                self._music_interrupt.clear()
                continue
            if not playlist or index >= len(playlist):
                playlist = list(self.music_tracks)
                if self.music_shuffle and len(playlist) > 1:
                    self._music_rng.shuffle(playlist)
                index = 0
            source = playlist[index]
            index += 1
            try:
                path, duration = self._prepare_music_track(source)
            except (EOFError, OSError, RuntimeError, wave.Error):
                self._music_interrupt.wait(0.25)
                self._music_interrupt.clear()
                continue
            started = time.monotonic()
            try:
                self._playback(path)
            except (OSError, RuntimeError, subprocess.SubprocessError):
                pass
            elapsed = time.monotonic() - started
            wait_for = max(0.0, duration - elapsed) if duration else 1.0
            self._music_interrupt.wait(wait_for)
            self._music_interrupt.clear()

    def close(self):
        self._stop.set()
        self._music_interrupt.set()
        if self._backend_owner:
            self._backend_owner.stop_all()
        if self._thread:
            self._thread.join(timeout=2)
        if self._ambience_thread:
            self._ambience_thread.join(timeout=2)
        if self._music_thread:
            self._music_thread.join(timeout=2)

    def _ensure_cues(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        volume_key = round(self.volume * 100)
        effects_key = round(self.effects_volume * 100)
        cues = {}
        for name, duration in {
            "card": 0.16,
            "chips": 0.2,
            "action": 0.11,
            "reveal": 0.36,
            "winner": 0.85,
            "error": 0.42,
            "all_in": 0.68,
            "elimination": 0.72,
        }.items():
            source = self._effect_source_for_cue(name)
            if source:
                path = self._effect_cache_destination(name, source, self.volume * self.effects_volume)
                if not path.exists():
                    self._prepare_effect_cue(name, source, path)
            else:
                path = self.cache_dir / f"{name}-{volume_key}-{effects_key}.wav"
                if not path.exists():
                    self._write_cue(path, name, duration)
            cues[name] = path
        ambience_path = self.cache_dir / f"ambience-{volume_key}-{round(self.ambience_volume * 100)}.wav"
        if not ambience_path.exists():
            self._write_ambience(ambience_path, 7.5)
        cues["ambience"] = ambience_path
        return cues

    def _prune_cache(self):
        keep = {path.resolve() for path in self._cues.values()}
        keep.update(self._music_cache_destination(path, self._music_gain()).resolve() for path in self.music_tracks)
        for path in self.cache_dir.glob("*.wav"):
            if path.resolve() not in keep:
                try:
                    path.unlink()
                except OSError:
                    pass

    def _ensure_music_thread(self):
        if (
            not self.available
            or self._music_thread is not None
            or not self.music_enabled
            or not self.music_tracks
        ):
            return
        self._music_thread = Thread(target=self._run_music, name="poker-music", daemon=True)
        self._music_thread.start()

    def _discover_music_tracks(self):
        if not self.music_dir.exists() or not self.music_dir.is_dir():
            return ()
        return tuple(
            sorted(
                (
                    path
                    for path in self.music_dir.iterdir()
                    if path.is_file() and path.suffix.lower() in self.MUSIC_EXTENSIONS
                ),
                key=lambda path: path.name.lower(),
            )
        )

    def _discover_sound_effects(self):
        if not self.sound_effects_dir.exists() or not self.sound_effects_dir.is_dir():
            return {}
        effects = {}
        for path in sorted(self.sound_effects_dir.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file() or path.suffix.lower() not in self.SOUND_EFFECT_EXTENSIONS:
                continue
            normalized = path.stem.lower().replace("-", "_").replace(" ", "_")
            if "card" in normalized and "flip" in normalized:
                effects["card_flip"] = path
        return effects

    def _effect_source_for_cue(self, cue):
        if cue in {"card", "reveal"}:
            return self.sound_effects.get("card_flip")
        return None

    def _effect_cache_destination(self, name, source, gain):
        try:
            stat = source.stat()
            identity = f"{source.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{round(gain * 1000)}"
        except OSError:
            identity = f"{source}|missing|{round(gain * 1000)}"
        digest = hashlib.sha1(identity.encode("utf-8", "ignore")).hexdigest()[:12]
        return self.cache_dir / f"effect-{name}-{digest}.wav"

    def _prepare_effect_cue(self, name, source, destination):
        with wave.open(str(source), "rb") as input_wave:
            params = input_wave.getparams()
        self._write_scaled_wave(source, destination, self.volume * self.effects_volume, params)

    def _music_gain(self):
        return max(0.0, min(1.0, self.volume * self.music_volume))

    def _music_cache_destination(self, source, gain):
        source = Path(source)
        try:
            stat = source.stat()
            identity = f"{source.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{round(gain * 1000)}"
        except OSError:
            identity = f"{source}|missing|{round(gain * 1000)}"
        digest = hashlib.sha1(identity.encode("utf-8", "ignore")).hexdigest()[:12]
        stem = "".join(character if character.isalnum() else "-" for character in source.stem).strip("-")
        stem = (stem or "track")[:34]
        return self.cache_dir / f"music-{stem}-{digest}.wav"

    def _prepare_music_track(self, source):
        source = Path(source)
        gain = self._music_gain()
        destination = self._music_cache_destination(source, gain)
        with wave.open(str(source), "rb") as input_wave:
            frame_rate = input_wave.getframerate()
            duration = input_wave.getnframes() / frame_rate if frame_rate else 0.0
            params = input_wave.getparams()
        if not destination.exists():
            self._write_scaled_wave(source, destination, gain, params)
        return destination, duration

    @staticmethod
    def _write_scaled_wave(source, destination, gain, params):
        destination.parent.mkdir(parents=True, exist_ok=True)
        sample_width = params.sampwidth
        with wave.open(str(source), "rb") as input_wave, wave.open(str(destination), "wb") as output:
            output.setparams(params)
            while True:
                frames = input_wave.readframes(4096)
                if not frames:
                    break
                if sample_width == 2:
                    count = len(frames) // 2
                    samples = struct.unpack("<" + "h" * count, frames)
                    scaled = bytearray()
                    for sample in samples:
                        value = int(sample * gain)
                        scaled.extend(struct.pack("<h", max(-32768, min(32767, value))))
                    output.writeframes(scaled)
                else:
                    output.writeframes(frames)

    def _write_ambience(self, path, duration):
        """Create an original, subtle room bed without bundled licensed media."""
        sample_rate = 22050
        rng = random.Random("casino-room-ambience")
        frames = bytearray()
        previous = 0.0
        for index in range(int(sample_rate * duration)):
            time = index / sample_rate
            noise = rng.uniform(-1, 1)
            previous = previous * 0.992 + noise * 0.008
            room = previous * 0.55 + math.sin(2 * math.pi * 82 * time) * 0.018
            sparkle = 0.0
            phase = time % 2.7
            if phase < 0.045:
                sparkle = math.sin(2 * math.pi * 2400 * time) * math.exp(-70 * phase) * 0.05
            value = (room + sparkle) * self.volume * self.ambience_volume
            sample = int(max(-1.0, min(1.0, value)) * 32767)
            frames.extend(struct.pack("<h", sample))
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(frames)

    def _write_cue(self, path, name, duration):
        sample_rate = 22050
        rng = random.Random(name)
        frames = bytearray()
        total = int(sample_rate * duration)
        notes = {
            "winner": (523.25, 659.25, 783.99, 1046.5),
            "reveal": (440.0, 659.25),
        }

        for index in range(total):
            time = index / sample_rate
            progress = index / max(1, total - 1)
            envelope = min(1.0, time / 0.012) * (1.0 - progress) ** 1.8
            if name == "card":
                value = (rng.uniform(-1, 1) * 0.55 + math.sin(2 * math.pi * 170 * time) * 0.25) * envelope
            elif name == "chips":
                first = math.sin(2 * math.pi * 2300 * time) * math.exp(-25 * time)
                shifted = max(0.0, time - 0.065)
                second = math.sin(2 * math.pi * 3100 * shifted) * math.exp(-35 * shifted) if time >= 0.065 else 0
                value = (first + second) * 0.55
            elif name == "action":
                value = math.sin(2 * math.pi * 560 * time) * envelope
            elif name in notes:
                sequence = notes[name]
                note_length = duration / len(sequence)
                note_index = min(len(sequence) - 1, int(time / note_length))
                local = (time % note_length) / note_length
                note_envelope = math.sin(math.pi * local) ** 0.7
                value = math.sin(2 * math.pi * sequence[note_index] * time) * note_envelope * (1 - progress * 0.35)
            else:
                frequency = 190 - 55 * progress
                value = math.sin(2 * math.pi * frequency * time) * envelope

            sample = int(max(-1.0, min(1.0, value)) * 32767 * self.volume * self.effects_volume)
            frames.extend(struct.pack("<h", sample))

        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(frames)

    def _detect_playback(self):
        # When the Qt application already exists, QSoundEffect gives us true
        # overlapping ambience/effects through the platform mixer. Calls are
        # marshalled back to the GUI thread by signals.
        try:
            from PyQt5.QtCore import QCoreApplication, QObject, QUrl, pyqtSignal
            from PyQt5.QtMultimedia import QSoundEffect

            if QCoreApplication.instance() is not None:
                class QtSoundBackend(QObject):
                    play_requested = pyqtSignal(str)
                    stop_ambience_requested = pyqtSignal()
                    stop_music_requested = pyqtSignal()
                    stop_all_requested = pyqtSignal()

                    def __init__(self):
                        super().__init__()
                        self.effects = {}
                        self.play_requested.connect(self._play)
                        self.stop_ambience_requested.connect(self._stop_ambience)
                        self.stop_music_requested.connect(self._stop_music)
                        self.stop_all_requested.connect(self._stop_all)

                    def play(self, path):
                        self.play_requested.emit(str(path))

                    def stop_ambience(self):
                        self.stop_ambience_requested.emit()

                    def stop_music(self):
                        self.stop_music_requested.emit()

                    def stop_all(self):
                        self.stop_all_requested.emit()

                    def _play(self, path):
                        effect = self.effects.get(path)
                        if effect is None:
                            effect = QSoundEffect(self)
                            effect.setSource(QUrl.fromLocalFile(str(Path(path).resolve())))
                            effect.setVolume(1.0)
                            self.effects[path] = effect
                        effect.play()

                    def _stop_ambience(self):
                        for path, effect in self.effects.items():
                            if "ambience-" in Path(path).name:
                                effect.stop()

                    def _stop_music(self):
                        for path, effect in self.effects.items():
                            if Path(path).name.startswith("music-"):
                                effect.stop()

                    def _stop_all(self):
                        for effect in self.effects.values():
                            effect.stop()

                self._backend_owner = QtSoundBackend()
                return self._backend_owner.play
        except (ImportError, RuntimeError):
            pass
        if os.name == "nt":
            import winsound

            return lambda path: winsound.PlaySound(str(path), winsound.SND_FILENAME)
        if sys.platform == "darwin" and shutil.which("afplay"):
            return lambda path: subprocess.run(
                ["afplay", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4
            )
        for command in ("paplay", "aplay"):
            if shutil.which(command):
                return lambda path, player=command: subprocess.run(
                    [player, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4
                )
        return None
