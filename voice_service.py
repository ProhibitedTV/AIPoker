"""Optional OBS-browser voice clip generation and RVC conversion.

The service is deliberately integration-oriented rather than opinionated about a
specific RVC checkout.  It can synthesize a neutral local TTS WAV, optionally run
an operator-supplied RVC command template over that WAV, cache the result, and
serve it back to the OBS browser source.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from queue import Empty, Full, Queue
import re
import shutil
import subprocess
from threading import Event, Lock, Thread
import time


FORBIDDEN_VOICE_TEXT = ("deposit", "cash out", "spin again")


class VoiceService:
    """Generate bounded, cached voice clips for OBS playback.

    RVC is treated as an optional speech-to-speech conversion step.  The service
    does not hard-code a particular RVC fork's CLI; instead ``rvc_command`` is a
    list of command arguments containing placeholders such as ``{input}``,
    ``{output}``, ``{voice}``, ``{model}``, ``{index}``, and ``{pitch}``.
    """

    def __init__(
        self,
        *,
        enabled=True,
        cache_dir="data/voice_cache",
        max_cache=160,
        tts_backend="pyttsx3",
        tts_voice="",
        tts_rate=175,
        tts_volume=0.8,
        rvc_enabled=False,
        rvc_command=None,
        rvc_models_path="voices/rvc",
        rvc_timeout_seconds=45,
        rvc_pitch=0,
        synthesizer=None,
    ):
        self.enabled = bool(enabled)
        self.cache_dir = Path(cache_dir)
        self.max_cache = max(8, int(max_cache or 160))
        self.tts_backend = str(tts_backend or "pyttsx3").strip().lower()
        self.tts_voice = str(tts_voice or "")
        self.tts_rate = int(tts_rate or 175)
        self.tts_volume = max(0.0, min(1.0, float(tts_volume or 0.8)))
        self.rvc_enabled = bool(rvc_enabled)
        self.rvc_command = tuple(str(part) for part in (rvc_command or []) if str(part).strip())
        self.rvc_models_path = Path(rvc_models_path)
        self.rvc_timeout_seconds = max(5, int(rvc_timeout_seconds or 45))
        self.rvc_pitch = int(rvc_pitch or 0)
        self._synthesizer = synthesizer
        self._queue = Queue(maxsize=24)
        self._jobs = {}
        self._lock = Lock()
        self._stop = Event()
        self._thread = None
        self._last_error = ""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.enabled:
            self._thread = Thread(target=self._run, name="poker-voice-clips", daemon=True)
            self._thread.start()

    def prepare_voice_cue(self, cue, *, speaker_id="host", speaker_name="", voice="", kind="host"):
        """Queue or return a cached clip for ``cue``.

        Returns a small public dict suitable to merge into ``/state``.
        """

        text = _safe_voice_text((cue or {}).get("line") or (cue or {}).get("voice_line") or "")
        cue_id = str((cue or {}).get("id") or (cue or {}).get("key") or text)
        voice_id = _safe_voice_id(voice or speaker_id or "host")
        speaker_id = _safe_voice_id(speaker_id or voice_id)
        key = self._cache_key(cue_id=cue_id, text=text, speaker_id=speaker_id, voice_id=voice_id, kind=kind)
        final_path = self.cache_dir / f"{key}.wav"
        if final_path.exists() and final_path.stat().st_size > 0:
            with self._lock:
                self._jobs[key] = {"status": "ready", "path": str(final_path), "backend": self._backend_label(voice_id)}
            return self._ready_payload(key, voice_id, speaker_name)
        if not self.enabled or not text:
            return self._status_payload("disabled", key, voice_id, speaker_name)

        with self._lock:
            job = self._jobs.get(key)
            if job and job.get("status") in {"pending", "running", "ready"}:
                return self._payload_for_job(key, voice_id, speaker_name, job)
            self._jobs[key] = {"status": "pending", "path": str(final_path), "backend": self._backend_label(voice_id)}
        try:
            self._queue.put_nowait(
                {
                    "key": key,
                    "text": text,
                    "speaker_id": speaker_id,
                    "speaker_name": speaker_name,
                    "voice_id": voice_id,
                    "kind": kind,
                    "path": final_path,
                }
            )
        except Full:
            with self._lock:
                self._jobs[key] = {"status": "dropped", "path": str(final_path), "backend": self._backend_label(voice_id)}
            return self._status_payload("dropped", key, voice_id, speaker_name)
        return self._status_payload("pending", key, voice_id, speaker_name)

    def voice_clip_path(self, filename):
        match = re.fullmatch(r"([a-f0-9]{24,64})\.wav", str(filename or ""))
        if not match:
            return None
        path = self.cache_dir / f"{match.group(1)}.wav"
        try:
            resolved = path.resolve()
            root = self.cache_dir.resolve()
        except OSError:
            return None
        if root not in resolved.parents and resolved != root:
            return None
        if not path.exists() or not path.is_file():
            return None
        return path

    def snapshot(self):
        with self._lock:
            statuses = [job.get("status") for job in self._jobs.values()]
        ready = statuses.count("ready")
        pending = statuses.count("pending") + statuses.count("running")
        return {
            "schema_version": 1,
            "enabled": self.enabled,
            "tts_backend": self.tts_backend,
            "rvc_enabled": self.rvc_enabled,
            "rvc_configured": bool(self.rvc_command),
            "status": "ready" if self.enabled and not pending else ("working" if pending else "disabled"),
            "ready": ready,
            "pending": pending,
            "last_error": self._last_error,
        }

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=0.2)
            except Empty:
                continue
            key = job["key"]
            with self._lock:
                self._jobs[key] = {"status": "running", "path": str(job["path"]), "backend": self._backend_label(job["voice_id"])}
            try:
                self._render_job(job)
            except Exception as exc:  # pragma: no cover - defensive in live broadcast
                self._last_error = f"{type(exc).__name__}: {exc}"
                with self._lock:
                    self._jobs[key] = {"status": "error", "path": str(job["path"]), "backend": self._backend_label(job["voice_id"])}
            else:
                with self._lock:
                    self._jobs[key] = {"status": "ready", "path": str(job["path"]), "backend": self._backend_label(job["voice_id"])}
                self._prune_cache()

    def _render_job(self, job):
        target = Path(job["path"])
        base = target.with_suffix(".base.wav")
        converted = target.with_suffix(".rvc.wav")
        self._synthesize(job["text"], base, job["voice_id"])
        output = base
        if self.rvc_enabled and self.rvc_command:
            rvc_output = self._run_rvc(base, converted, job["voice_id"])
            if rvc_output and rvc_output.exists() and rvc_output.stat().st_size > 0:
                output = rvc_output
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output, target)
        self._write_metadata(job, target)
        for scratch in (base, converted):
            try:
                scratch.unlink()
            except OSError:
                pass

    def _synthesize(self, text, output, voice_id):
        output.parent.mkdir(parents=True, exist_ok=True)
        if self._synthesizer:
            self._synthesizer(text, output, voice_id)
        elif self.tts_backend in {"", "none", "off", "disabled"}:
            raise RuntimeError("voice TTS backend is disabled")
        elif self.tts_backend == "pyttsx3":
            self._synthesize_pyttsx3(text, output, voice_id)
        else:
            raise RuntimeError(f"unsupported voice TTS backend: {self.tts_backend}")
        if not output.exists() or output.stat().st_size <= 0:
            raise RuntimeError("TTS backend did not create a voice clip")

    def _synthesize_pyttsx3(self, text, output, voice_id):
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("volume", self.tts_volume)
        engine.setProperty("rate", self.tts_rate)
        preferred_voice = self.tts_voice or voice_id
        if preferred_voice:
            for installed in engine.getProperty("voices"):
                haystack = " ".join(str(getattr(installed, attr, "")) for attr in ("id", "name")).lower()
                if preferred_voice.lower() in haystack:
                    engine.setProperty("voice", installed.id)
                    break
        engine.save_to_file(text, str(output))
        engine.runAndWait()

    def _run_rvc(self, source, target, voice_id):
        model = self._rvc_model_for_voice(voice_id)
        index = self._rvc_index_for_voice(voice_id)
        if not model:
            return source
        replacements = {
            "input": str(source),
            "output": str(target),
            "voice": voice_id,
            "model": str(model),
            "index": str(index or ""),
            "pitch": str(self.rvc_pitch),
        }
        command = [part.format(**replacements) for part in self.rvc_command]
        subprocess.run(
            command,
            check=True,
            timeout=self.rvc_timeout_seconds,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return target

    def _rvc_model_for_voice(self, voice_id):
        if not voice_id:
            return None
        direct = Path(voice_id)
        if direct.exists() and direct.suffix.lower() in {".pth", ".onnx"}:
            return direct
        candidate = self.rvc_models_path / f"{voice_id}.pth"
        if candidate.exists():
            return candidate
        candidate = self.rvc_models_path / voice_id / f"{voice_id}.pth"
        if candidate.exists():
            return candidate
        return None

    def _rvc_index_for_voice(self, voice_id):
        candidates = [
            self.rvc_models_path / f"{voice_id}.index",
            self.rvc_models_path / voice_id / f"{voice_id}.index",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _write_metadata(self, job, target):
        meta = {
            "speaker_id": job["speaker_id"],
            "speaker_name": job["speaker_name"],
            "voice_id": job["voice_id"],
            "kind": job["kind"],
            "backend": self._backend_label(job["voice_id"]),
            "created_at": time.time(),
        }
        target.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def _prune_cache(self):
        clips = sorted(self.cache_dir.glob("*.wav"), key=lambda path: path.stat().st_mtime, reverse=True)
        for old in clips[self.max_cache :]:
            try:
                old.unlink()
                old.with_suffix(".json").unlink()
            except OSError:
                pass

    def _backend_label(self, voice_id):
        if self.rvc_enabled and self.rvc_command and self._rvc_model_for_voice(voice_id):
            return "rvc"
        return self.tts_backend

    def _cache_key(self, *, cue_id, text, speaker_id, voice_id, kind):
        material = "\n".join(
            [
                str(cue_id),
                text,
                speaker_id,
                voice_id,
                kind,
                self.tts_backend,
                "rvc" if self.rvc_enabled and self.rvc_command else "tts",
                str(self.rvc_pitch),
            ]
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]

    def _ready_payload(self, key, voice_id, speaker_name):
        payload = self._status_payload("ready", key, voice_id, speaker_name)
        payload["audio_url"] = f"/voice/{key}.wav"
        return payload

    def _status_payload(self, status, key, voice_id, speaker_name):
        return {
            "audio_status": status,
            "audio_key": key,
            "audio_url": "",
            "voice_id": voice_id,
            "speaker_name": speaker_name,
            "voice_backend": self._backend_label(voice_id),
        }

    def _payload_for_job(self, key, voice_id, speaker_name, job):
        if job.get("status") == "ready":
            return self._ready_payload(key, voice_id, speaker_name)
        return self._status_payload(job.get("status", "pending"), key, voice_id, speaker_name)


def _safe_voice_id(value):
    text = re.sub(r"[^a-zA-Z0-9_.:-]", "_", str(value or "voice").strip())
    return text[:80] or "voice"


def _safe_voice_text(value, limit=220):
    text = re.sub(r"\s+", " ", str(value or "").strip())
    for forbidden in FORBIDDEN_VOICE_TEXT:
        text = re.sub(forbidden, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -Â·")
    text = text.strip(" -·")
    return text[: max(1, int(limit))]
