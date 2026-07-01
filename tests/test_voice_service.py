import sys
import time
import wave

from voice_service import VoiceService


def write_tiny_wave(path):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\x00\x00\x20\x03\xe0\xfc\x00\x00")


def wait_ready(service, cue, **kwargs):
    result = service.prepare_voice_cue(cue, **kwargs)
    deadline = time.time() + 3
    while result["audio_status"] != "ready" and time.time() < deadline:
        time.sleep(0.05)
        result = service.prepare_voice_cue(cue, **kwargs)
    return result


def test_voice_service_generates_and_serves_cached_clip(tmp_path):
    calls = []

    def synth(text, output, voice_id):
        calls.append((text, voice_id))
        write_tiny_wave(output)

    service = VoiceService(enabled=True, cache_dir=tmp_path, synthesizer=synth)
    try:
        cue = {"id": "decision-1", "line": "Decision point. Nova faces a call."}
        result = wait_ready(service, cue, speaker_id="nova", speaker_name="Nova", voice="nova_rvc", kind="table_talk")

        assert result["audio_status"] == "ready"
        assert result["audio_url"].startswith("/voice/")
        assert result["voice_id"] == "nova_rvc"
        assert calls == [("Decision point. Nova faces a call.", "nova_rvc")]
        assert service.voice_clip_path(result["audio_url"].rsplit("/", 1)[-1]).exists()

        cached = service.prepare_voice_cue(cue, speaker_id="nova", speaker_name="Nova", voice="nova_rvc", kind="table_talk")
        assert cached["audio_status"] == "ready"
        assert len(calls) == 1
    finally:
        service.close()


def test_voice_service_runs_operator_rvc_command_template(tmp_path):
    script = tmp_path / "fake_rvc.py"
    script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path(sys.argv[2]).write_bytes(Path(sys.argv[1]).read_bytes() + b'RVC')\n",
        encoding="utf-8",
    )
    models = tmp_path / "models"
    models.mkdir()
    (models / "atlas_rvc.pth").write_bytes(b"model")

    def synth(_text, output, _voice_id):
        write_tiny_wave(output)

    service = VoiceService(
        enabled=True,
        cache_dir=tmp_path / "cache",
        synthesizer=synth,
        rvc_enabled=True,
        rvc_command=[sys.executable, str(script), "{input}", "{output}", "{model}", "{voice}", "{pitch}"],
        rvc_models_path=models,
        rvc_pitch=2,
    )
    try:
        result = wait_ready(
            service,
            {"id": "host-1", "line": "The Night City host speaks."},
            speaker_id="host",
            speaker_name="Host",
            voice="atlas_rvc",
            kind="host",
        )

        path = service.voice_clip_path(result["audio_url"].rsplit("/", 1)[-1])
        assert result["audio_status"] == "ready"
        assert result["voice_backend"] == "rvc"
        assert path.read_bytes().endswith(b"RVC")
    finally:
        service.close()
