"""Non-blocking threaded audio capture and TTS engine.

Features:
- Separate background daemon worker thread consuming from a queue.Queue for TTS.
- Audio playback never blocks listening/command input.
- Text-fallback mode when microphone or TTS hardware/driver is unavailable.
- Thread-safe lifecycle management.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class TTSBackend(ABC):
    """Abstract interface for Text-To-Speech backends."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """Render speech synchronously within worker thread."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Release TTS resources."""
        pass


class ConsoleTTSBackend(TTSBackend):
    """Text-only fallback TTS backend for headless or test environments."""

    def __init__(self, output_sink: Optional[Callable[[str], None]] = None) -> None:
        self.output_sink = output_sink or (lambda msg: logger.info("ASSISTANT: %s", msg))

    def speak(self, text: str) -> None:
        self.output_sink(text)

    def close(self) -> None:
        pass


class Pyttsx3TTSBackend(TTSBackend):
    """Real pyttsx3 SAPI5/eSpeak TTS backend."""

    def __init__(self, rate: int = 180, volume: float = 0.9) -> None:
        self.rate = rate
        self.volume = volume
        self._engine = None
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            import pyttsx3  # type: ignore[import-untyped]
            self._engine = pyttsx3.init()
            if self._engine is not None:
                self._engine.setProperty("rate", self.rate)
                self._engine.setProperty("volume", self.volume)
            logger.info("Initialized pyttsx3 TTS backend successfully.")
        except Exception as exc:
            logger.warning("Failed to initialize pyttsx3: %s. Falling back to console TTS.", exc)
            self._engine = None

    def speak(self, text: str) -> None:
        if self._engine is not None:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
                return
            except Exception as exc:
                logger.error("Error during pyttsx3 playback: %s", exc)
        # Fallback to logger if engine fails
        logger.info("ASSISTANT [Voice Fallback]: %s", text)

    def close(self) -> None:
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass
            self._engine = None


class InputBackend(ABC):
    """Abstract interface for audio/text input capture."""

    @abstractmethod
    def listen(self, timeout: Optional[float] = None) -> Optional[str]:
        """Capture user utterance or text command."""
        pass


class TextInputBackend(InputBackend):
    """Keyboard/console fallback input backend."""

    def __init__(self, input_provider: Optional[Callable[[], Optional[str]]] = None) -> None:
        self.input_provider = input_provider

    def listen(self, timeout: Optional[float] = None) -> Optional[str]:
        if self.input_provider is not None:
            return self.input_provider()
        try:
            val = input("USER > ").strip()
            return val if val else None
        except (EOFError, KeyboardInterrupt):
            return None


class MicrophoneInputBackend(InputBackend):
    """Microphone speech capture using SpeechRecognition."""

    def __init__(self) -> None:
        self._recognizer = None
        self._mic = None
        self._init_speech()

    def _init_speech(self) -> None:
        try:
            import speech_recognition as sr  # type: ignore[import-untyped]
            self._recognizer = sr.Recognizer()
            self._mic = sr.Microphone()
            logger.info("Microphone input backend initialized successfully.")
        except Exception as exc:
            logger.warning("Microphone hardware or speech_recognition unavailable: %s", exc)
            self._recognizer = None
            self._mic = None

    def listen(self, timeout: Optional[float] = None) -> Optional[str]:
        if self._recognizer is None or self._mic is None:
            logger.warning("Microphone unavailable, switching to fallback.")
            return None

        import speech_recognition as sr  # type: ignore[import-untyped]
        try:
            with self._mic as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                logger.debug("Listening for voice input...")
                audio = self._recognizer.listen(source, timeout=timeout or 5.0, phrase_time_limit=10.0)
                text = self._recognizer.recognize_google(audio)
                return str(text).strip()
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            logger.debug("Speech was unintelligible.")
            return None
        except Exception as exc:
            logger.warning("Voice capture error: %s", exc)
            return None


class AudioEngine:
    """Non-blocking Audio Engine managing concurrent TTS playback and command capture."""

    def __init__(
        self,
        tts_backend: Optional[TTSBackend] = None,
        input_backend: Optional[InputBackend] = None,
    ) -> None:
        self.tts_backend: TTSBackend = tts_backend or ConsoleTTSBackend()
        self.input_backend: InputBackend = input_backend or TextInputBackend()
        
        self._tts_queue: queue.Queue[Optional[str]] = queue.Queue()
        self._stop_event = threading.Event()
        self._tts_thread: Optional[threading.Thread] = None
        self._start_tts_worker()

    def _start_tts_worker(self) -> None:
        """Start the background worker thread for TTS."""
        self._tts_thread = threading.Thread(
            target=self._tts_worker_loop,
            name="AudioEngine-TTSWorker",
            daemon=True,
        )
        self._tts_thread.start()

    def _tts_worker_loop(self) -> None:
        """Background loop draining the TTS queue without blocking caller."""
        logger.debug("TTS worker thread started.")
        while not self._stop_event.is_set():
            try:
                item = self._tts_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:  # Sentinel value to exit
                self._tts_queue.task_done()
                break

            try:
                self.tts_backend.speak(item)
            except Exception as exc:
                logger.error("Unexpected error in TTS worker: %s", exc)
            finally:
                self._tts_queue.task_done()
        logger.debug("TTS worker thread stopped.")

    def speak(self, text: str, non_blocking: bool = True) -> None:
        """Enqueue speech output.
        
        If non_blocking is True, returns immediately.
        If non_blocking is False, waits until speech playback has completed.
        """
        if not text:
            return
        self._tts_queue.put(text)
        if not non_blocking:
            self._tts_queue.join()

    def listen(self, timeout: Optional[float] = None) -> Optional[str]:
        """Capture user input via the active input backend."""
        return self.input_backend.listen(timeout=timeout)

    def flush(self) -> None:
        """Wait for all pending speech queue items to finish."""
        self._tts_queue.join()

    def shutdown(self) -> None:
        """Stop background worker and release resources."""
        self._stop_event.set()
        self._tts_queue.put(None)  # Sentinel to wake thread
        if self._tts_thread is not None and self._tts_thread.is_alive():
            self._tts_thread.join(timeout=2.0)
        self.tts_backend.close()
        logger.info("AudioEngine shut down cleanly.")
