"""Main CLI entrypoint for NewsWorld AI Voice Assistant.

Features:
- Seamless switching between Voice (Microphone + TTS) and Text-fallback modes.
- Robust SIGINT (Ctrl+C) handling and graceful shutdown.
- Non-blocking audio pipeline: TTS speech queue never blocks listening.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from typing import Any

from src.config import load_config, setup_logging
from src.core.audio_engine import (
    AudioEngine,
    ConsoleTTSBackend,
    InputBackend,
    MicrophoneInputBackend,
    Pyttsx3TTSBackend,
    TextInputBackend,
    TTSBackend,
)
from src.core.dispatcher import CommandDispatcher
from src.core.email_service import EmailService
from src.core.reminder_service import Reminder, ReminderService
from src.services.news_service import NewsService
from src.services.search_service import SearchService
from src.services.weather_service import WeatherService

logger = logging.getLogger("NewsWorldAssistant")


class VoiceAssistantApp:
    """Manages the full lifecycle and event loop of the Voice Assistant."""

    def __init__(self, mode: str = "text") -> None:
        self.config = load_config()
        self.mode = mode.lower()
        self._running = False

        # 1. Initialize Audio Engine with appropriate backends
        tts_backend: TTSBackend
        input_backend: InputBackend
        if self.mode == "voice":
            try:
                tts_backend = Pyttsx3TTSBackend(
                    rate=self.config.tts_speech_rate,
                    volume=self.config.tts_volume,
                )
                input_backend = MicrophoneInputBackend()
                logger.info("Initializing Assistant in VOICE mode.")
            except Exception as exc:
                logger.warning("Failed to initialize voice hardware (%s). Falling back to text mode.", exc)
                tts_backend = ConsoleTTSBackend()
                input_backend = TextInputBackend()
                self.mode = "text"
        else:
            tts_backend = ConsoleTTSBackend()
            input_backend = TextInputBackend()
            logger.info("Initializing Assistant in TEXT FALLBACK mode.")

        self.audio_engine = AudioEngine(
            tts_backend=tts_backend,
            input_backend=input_backend,
        )

        # 2. Initialize Reminder Alert Hook
        def on_reminder_trigger(rem: Reminder) -> None:
            alert_msg = f"Reminder Alert: {rem.message}!"
            print(f"\n[ALERT] {alert_msg}")
            self.audio_engine.speak(alert_msg)

        self.reminder_service = ReminderService(on_trigger=on_reminder_trigger)

        # 3. Initialize Services
        self.news_service = NewsService(
            default_rss_url=self.config.news_rss_url,
            api_key=self.config.news_api_key,
            ttl_seconds=self.config.news_cache_ttl_seconds,
        )
        self.weather_service = WeatherService(
            api_key=self.config.weather_api_key,
        )
        self.search_service = SearchService(
            provider=self.config.search_provider,
        )
        self.email_service = EmailService(
            smtp_server=self.config.smtp_server,
            smtp_port=self.config.smtp_port,
            sender_address=self.config.smtp_sender,
            sender_password=self.config.smtp_password,
        )

        # 4. Initialize Command Dispatcher
        self.dispatcher = CommandDispatcher(
            news_service=self.news_service,
            weather_service=self.weather_service,
            search_service=self.search_service,
            email_service=self.email_service,
            reminder_service=self.reminder_service,
        )

        # 5. Signal Handlers
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, signum: int, frame: Any) -> None:
        """Handle SIGINT gracefully."""
        print("\n\n[SYSTEM] Received shutdown interrupt. Exiting safely...")
        self.stop()
        sys.exit(0)

    def start(self) -> None:
        """Run the main assistant loop."""
        self._running = True
        welcome_banner = (
            "=====================================================\n"
            "   NewsWorld AI Voice Assistant (OASIS Advanced)     \n"
            f"   Operating Mode: {self.mode.upper()}               \n"
            "   Type 'help' for commands, 'exit' to quit          \n"
            "====================================================="
        )
        print(welcome_banner)
        self.audio_engine.speak("NewsWorld AI Voice Assistant is online.")

        while self._running:
            try:
                # Capture next command (non-blocking TTS allows continuous interaction)
                utterance = self.audio_engine.listen()
                if utterance is None:
                    # In text mode, EOF/None indicates exit
                    if self.mode == "text":
                        break
                    time.sleep(0.1)
                    continue

                if not utterance.strip():
                    continue

                print(f"[YOU]: {utterance}")
                result = self.dispatcher.dispatch(utterance)

                print(f"[ASSISTANT]: {result.response_text}\n")
                self.audio_engine.speak(result.response_text)

                if result.should_exit:
                    self._running = False
                    break

            except (KeyboardInterrupt, EOFError):
                break
            except Exception as exc:
                logger.error("Unhandled error in assistant loop: %s", exc, exc_info=True)
                print(f"[ERROR]: An unexpected error occurred: {exc}")

        self.stop()

    def stop(self) -> None:
        """Shutdown all services cleanly."""
        if not self._running:
            return
        self._running = False
        self.audio_engine.shutdown()
        self.reminder_service.shutdown()
        print("[SYSTEM] NewsWorld Voice Assistant terminated cleanly.")


def main() -> None:
    """CLI execution parser."""
    parser = argparse.ArgumentParser(description="NewsWorld AI Voice Assistant")
    parser.add_argument(
        "--mode",
        choices=["text", "voice"],
        default="text",
        help="Interaction mode: 'voice' (mic + pyttsx3) or 'text' (console fallback)",
    )
    args = parser.parse_args()

    setup_logging()
    app = VoiceAssistantApp(mode=args.mode)
    app.start()


if __name__ == "__main__":
    main()
