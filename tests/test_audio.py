from pathlib import Path
from threading import Event
import tempfile
import wave

from audio import AudioService


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
