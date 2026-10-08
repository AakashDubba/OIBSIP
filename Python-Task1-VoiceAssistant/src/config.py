"""Configuration manager for NewsWorld AI Voice Assistant.

Loads configuration strictly from environment variables or .env files.
Never hardcodes secrets or credentials.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class AppConfig:
    """Application runtime configuration."""
    
    # Audio & Interaction
    input_mode: str  # "voice" or "text"
    tts_engine: str  # "pyttsx3" or "console"
    tts_speech_rate: int
    tts_volume: float
    
    # News & Services
    news_rss_url: str
    news_api_key: Optional[str]
    news_cache_ttl_seconds: int
    
    # Weather
    weather_api_key: Optional[str]
    weather_default_city: str
    
    # Search
    search_provider: str  # "browser" or "duckduckgo"
    
    # Email SMTP
    smtp_server: str
    smtp_port: int
    smtp_sender: Optional[str]
    smtp_password: Optional[str]
    
    # Logging
    log_level: str


def load_config() -> AppConfig:
    """Load configuration from environment variables with safe defaults."""
    return AppConfig(
        input_mode=os.getenv("VOICE_INPUT_MODE", "text").lower(),
        tts_engine=os.getenv("VOICE_TTS_ENGINE", "pyttsx3").lower(),
        tts_speech_rate=int(os.getenv("VOICE_TTS_RATE", "180")),
        tts_volume=float(os.getenv("VOICE_TTS_VOLUME", "0.9")),
        news_rss_url=os.getenv(
            "NEWS_RSS_URL",
            "https://feeds.bbci.co.uk/news/world/rss.xml",
        ),
        news_api_key=os.getenv("NEWS_API_KEY"),
        news_cache_ttl_seconds=int(os.getenv("NEWS_CACHE_TTL_SECONDS", "300")),
        weather_api_key=os.getenv("WEATHER_API_KEY"),
        weather_default_city=os.getenv("WEATHER_DEFAULT_CITY", "New York"),
        search_provider=os.getenv("SEARCH_PROVIDER", "duckduckgo").lower(),
        smtp_server=os.getenv("EMAIL_SMTP_SERVER", "smtp.example.com"),
        smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "587")),
        smtp_sender=os.getenv("EMAIL_SENDER_ADDRESS"),
        smtp_password=os.getenv("EMAIL_SENDER_PASSWORD"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    numeric_level = getattr(logging, log_level, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
