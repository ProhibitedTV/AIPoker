"""Non-blocking, dependency-free generated sound cues for game events."""

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
import wave


class AudioService:
    def __init__(
        self,
        enabled=True,
        volume=0.35,
        cache_dir="data/audio_cache",
        playback=None,
        ambience_enabled=False,
        ambience_volume=0.16,
        effects_volume=0.72,
    ):
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self.ambience_enabled = bool(ambience_enabled)
        self.ambience_volume = max(0.0, min(1.0, ambience_volume))
        self.effects_volume = max(0.0, min(1.0, effects_volume))
        self.cache_dir = Path(cache_dir)
        self._backend_owner = None
        self._playback = playback or self._detect_playback()
        self.available = self._playback is not None
        self.enabled = self.enabled and self.available
        self._queue = Queue(maxsize=12)
        self._stop = Event()
        self._thread = None
        self._ambience_thread = None
        self._voice_active = False
        self._cues = {}
        if self.available:
            self._cues = self._ensure_cues()
            self._thread = Thread(target=self._run, name="poker-audio", daemon=True)
            self._thread.start()
            if self.ambience_enabled and self._cues.get("ambience"):
                self._ambience_thread = Thread(target=self._run_ambience, name="poker-ambience", daemon=True)
                self._ambience_thread.start()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled) and self.available
        if not self.enabled and self._backend_owner:
            self._backend_owner.stop_all()

    def set_channel_volumes(self, master=None, ambience=None, effects=None):
        changed = False
        if master is not None:
            self.volume = max(0.0, min(1.0, float(master)))
            changed = True
        if ambience is not None:
            self.ambience_volume = max(0.0, min(1.0, float(ambience)))
            changed = True
        if effects is not None:
            self.effects_volume = max(0.0, min(1.0, float(effects)))
            changed = True
        if changed and self.available:
            self._cues = self._ensure_cues()
            self._prune_cache()

    def set_ambience_enabled(self, enabled):
        self.ambience_enabled = bool(enabled)
        if not self.ambience_enabled and self._backend_owner:
            self._backend_owner.stop_ambience()

    def set_voice_active(self, active):
        """Duck nonessential layers while narration or player speech is active."""
        self._voice_active = bool(active)
        if active and self._backend_owner:
            self._backend_owner.stop_ambience()

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

    def close(self):
        self._stop.set()
        if self._backend_owner:
            self._backend_owner.stop_all()
        if self._thread:
            self._thread.join(timeout=2)
        if self._ambience_thread:
            self._ambience_thread.join(timeout=2)

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
        for path in self.cache_dir.glob("*.wav"):
            if path.resolve() not in keep:
                try:
                    path.unlink()
                except OSError:
                    pass

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
                    stop_all_requested = pyqtSignal()

                    def __init__(self):
                        super().__init__()
                        self.effects = {}
                        self.play_requested.connect(self._play)
                        self.stop_ambience_requested.connect(self._stop_ambience)
                        self.stop_all_requested.connect(self._stop_all)

                    def play(self, path):
                        self.play_requested.emit(str(path))

                    def stop_ambience(self):
                        self.stop_ambience_requested.emit()

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
                            if "ambience-" in path:
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
