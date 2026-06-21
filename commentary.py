"""Non-blocking optional text-to-speech narration."""

from queue import Empty, Queue
from threading import Event, Thread


class CommentaryService:
    SPOKEN_EVENTS = {"action", "community", "winner"}

    def __init__(self, enabled=False, volume=0.9, rate=175, voice=""):
        self.enabled = enabled
        self.volume = volume
        self.rate = rate
        self.voice = voice
        self._queue = Queue()
        self._stop = Event()
        self._thread = None
        if enabled:
            self._thread = Thread(target=self._run, name="poker-tts", daemon=True)
            self._thread.start()

    def handle_event(self, event):
        if self.enabled and event.get("type") in self.SPOKEN_EVENTS:
            self._queue.put(event.get("message", ""))

    def _run(self):
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("volume", self.volume)
            engine.setProperty("rate", self.rate)
            if self.voice:
                for installed in engine.getProperty("voices"):
                    if self.voice.lower() in installed.name.lower():
                        engine.setProperty("voice", installed.id)
                        break
        except (ImportError, RuntimeError):
            self.enabled = False
            return

        while not self._stop.is_set():
            try:
                text = self._queue.get(timeout=0.25)
            except Empty:
                continue
            if text:
                engine.say(text)
                engine.runAndWait()

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
