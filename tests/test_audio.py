from pathlib import Path
from threading import Event
import tempfile
import wave

from audio import AudioService


def write_tiny_wave(path, samples=(0, 12000, -12000, 0), frame_rate=8000):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(frame_rate)
        for sample in samples:
            output.writeframesraw(int(sample).to_bytes(2, "little", signed=True))


def test_audio_service_generates_and_plays_event_cues_off_thread():
    played = []
    heard = Event()

    def playback(path):
        played.append(Path(path))
        heard.set()

    with tempfile.TemporaryDirectory() as directory:
        service = AudioService(enabled=True, volume=0.25, cache_dir=directory, playback=playback)
        service.handle_event({"type": "community", "message": "Flop reveals cards"})
        assert heard.wait(timeout=2)
        service.close()

        assert played[0].name.startswith("reveal-")
        with wave.open(str(played[0]), "rb") as cue:
            assert cue.getnchannels() == 1
            assert cue.getsampwidth() == 2
            assert cue.getframerate() == 22050
            assert cue.getnframes() > 0


def test_audio_service_maps_poker_events_to_distinct_cues():
    assert AudioService._cue_for_event({"type": "deal"}) == "card"
    assert AudioService._cue_for_event({"type": "action", "message": "P1 raises 50"}) == "chips"
    assert AudioService._cue_for_event({"type": "action", "message": "P1 checks"}) == "action"
    assert AudioService._cue_for_event({"type": "action", "message": "P1 moves all-in"}) == "all_in"
    assert AudioService._cue_for_event({"type": "winner"}) == "winner"
    assert AudioService._cue_for_event({"type": "error"}) == "error"


def test_audio_can_be_muted_without_restarting_service():
    heard = Event()
    with tempfile.TemporaryDirectory() as directory:
        service = AudioService(enabled=True, cache_dir=directory, playback=lambda _path: heard.set())
        service.set_enabled(False)
        service.handle_event({"type": "winner", "message": "P1 wins"})
        assert not heard.wait(timeout=0.15)
        service.close()


def test_audio_service_discovers_and_scales_music_playlist(tmp_path):
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    source = music_dir / "Neon Test.wav"
    write_tiny_wave(source)

    played = []
    heard = Event()

    def playback(path):
        played.append(Path(path))
        heard.set()

    service = AudioService(
        enabled=True,
        volume=0.5,
        cache_dir=tmp_path / "cache",
        playback=playback,
        music_enabled=True,
        music_dir=music_dir,
        music_volume=0.5,
        music_shuffle=False,
    )
    assert service.music_tracks == (source,)
    assert heard.wait(timeout=2)
    service.close()

    music_cache = next(path for path in played if path.name.startswith("music-Neon-Test-"))
    with wave.open(str(music_cache), "rb") as cached:
        frames = cached.readframes(cached.getnframes())
    first_loud_sample = int.from_bytes(frames[2:4], "little", signed=True)
    assert 2500 < first_loud_sample < 3500


def test_audio_service_uses_custom_wav_card_flip_when_available(tmp_path):
    sound_dir = tmp_path / "sound_effects"
    sound_dir.mkdir()
    source = sound_dir / "card_flip.wav"
    write_tiny_wave(source, samples=(0, 16000, -16000, 0))

    service = AudioService(
        enabled=True,
        volume=0.5,
        effects_volume=0.5,
        cache_dir=tmp_path / "cache",
        playback=lambda _path: None,
        sound_effects_dir=sound_dir,
    )
    try:
        assert service.sound_effects["card_flip"] == source
        assert service._cues["card"].name.startswith("effect-card-")
        with wave.open(str(service._cues["card"]), "rb") as cached:
            frames = cached.readframes(cached.getnframes())
        first_loud_sample = int.from_bytes(frames[2:4], "little", signed=True)
        assert 3500 < first_loud_sample < 4500
    finally:
        service.close()
