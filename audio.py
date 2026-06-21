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
    def __init__(self, enabled=True, volume=0.35, cache_dir="data/audio_cache", playback=None):
        self.enabled = enabled
        self.volume = max(0.0, min(1.0, volume))
        self.cache_dir = Path(cache_dir)
        self._playback = playback or self._detect_playback()
        self.available = self._playback is not None
        self.enabled = self.enabled and self.available
        self._queue = Queue(maxsize=12)
        self._stop = Event()
        self._thread = None
        self._cues = {}
        if self.available:
            self._cues = self._ensure_cues()
            self._thread = Thread(target=self._run, name="poker-audio", daemon=True)
            self._thread.start()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled) and self.available

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
        if event_type == "error":
            return "error"
        if event_type == "action":
            message = event.get("message", "").lower()
            return "chips" if any(word in message for word in ("bet", "raise", "blind")) else "action"
        return None

    def _run(self):
        while not self._stop.is_set():
            try:
                cue = self._queue.get(timeout=0.2)
            except Empty:
                continue
            path = self._cues.get(cue)
            if path:
                try:
                    self._playback(path)
                except (OSError, subprocess.SubprocessError):
                    continue

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _ensure_cues(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        volume_key = round(self.volume * 100)
        cues = {}
        for name, duration in {
            "card": 0.16,
            "chips": 0.2,
            "action": 0.11,
            "reveal": 0.36,
            "winner": 0.85,
            "error": 0.42,
        }.items():
            path = self.cache_dir / f"{name}-{volume_key}.wav"
            if not path.exists():
                self._write_cue(path, name, duration)
            cues[name] = path
        return cues

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

            sample = int(max(-1.0, min(1.0, value)) * 32767 * self.volume)
            frames.extend(struct.pack("<h", sample))

        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(frames)

    @staticmethod
    def _detect_playback():
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
