"""Tests for AudioEngine non-blocking queue and backend abstractions."""

from __future__ import annotations

import time
from typing import List
from src.core.audio_engine import AudioEngine, ConsoleTTSBackend, TextInputBackend


def test_audio_engine_non_blocking_tts() -> None:
    captured: List[str] = []

    def mock_sink(msg: str) -> None:
        captured.append(msg)

    tts = ConsoleTTSBackend(output_sink=mock_sink)
    engine = AudioEngine(tts_backend=tts)

    start_time = time.time()
    # Queue multiple messages: speak() should return immediately (< 0.05s)
    engine.speak("Hello 1")
    engine.speak("Hello 2")
    engine.speak("Hello 3")
    elapsed = time.time() - start_time

    assert elapsed < 0.1, "speak() must not block the caller"

    # Wait for queue to drain
    engine.flush()
    assert captured == ["Hello 1", "Hello 2", "Hello 3"]

    engine.shutdown()


def test_text_input_backend() -> None:
    inputs = iter(["hello", "weather in London", "exit"])
    backend = TextInputBackend(input_provider=lambda: next(inputs, None))

    assert backend.listen() == "hello"
    assert backend.listen() == "weather in London"
    assert backend.listen() == "exit"
    assert backend.listen() is None


def test_audio_engine_graceful_shutdown() -> None:
    engine = AudioEngine()
    engine.speak("Testing shutdown")
    engine.shutdown()
    # Further calls to speak should not crash
    engine.speak("After shutdown")
