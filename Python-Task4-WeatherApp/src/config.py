"""Persistent configuration and user preferences manager for NewsWorld Weather Engine."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "weather_preferences.json"


@dataclass
class UserPreferences:
    """Persistent user preferences model."""
    last_city: str = "London"
    temperature_unit: str = "C"  # "C" or "F"
    enable_regional_news: bool = True
    auto_locate_on_startup: bool = False

    def sanitize(self) -> None:
        """Ensure preference values conform to supported domains."""
        self.last_city = self.last_city.strip() if self.last_city else "London"
        if self.temperature_unit.upper() not in ("C", "F"):
            self.temperature_unit = "C"
        else:
            self.temperature_unit = self.temperature_unit.upper()


@dataclass(frozen=True)
class AppConfig:
    """Runtime environmental configuration."""
    api_key: Optional[str]
    timeout_seconds: float
    max_retries: int
    news_rss_url: str
    preferences_path: Path


def load_preferences(file_path: Optional[Path] = None) -> UserPreferences:
    """Load user preferences from JSON file with resilient fallbacks."""
    target_path = file_path or DEFAULT_CONFIG_PATH
    if not target_path.exists():
        logger.info("Preferences file not found. Initializing with defaults.")
        prefs = UserPreferences()
        save_preferences(prefs, target_path)
        return prefs

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            prefs = UserPreferences(
                last_city=str(data.get("last_city", "London")),
                temperature_unit=str(data.get("temperature_unit", "C")),
                enable_regional_news=bool(data.get("enable_regional_news", True)),
                auto_locate_on_startup=bool(data.get("auto_locate_on_startup", False)),
            )
            prefs.sanitize()
            return prefs
    except Exception as exc:
        logger.warning("Failed to load preferences from %s: %s. Using defaults.", target_path, exc)
        return UserPreferences()


def save_preferences(prefs: UserPreferences, file_path: Optional[Path] = None) -> bool:
    """Persist user preferences atomically to JSON file."""
    target_path = file_path or DEFAULT_CONFIG_PATH
    prefs.sanitize()
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = target_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(asdict(prefs), f, indent=2)
        temp_file.replace(target_path)
        logger.debug("Successfully saved user preferences to %s", target_path)
        return True
    except Exception as exc:
        logger.error("Failed to save user preferences to %s: %s", target_path, exc)
        return False


def get_app_config() -> AppConfig:
    """Retrieve runtime environment configuration."""
    return AppConfig(
        api_key=os.getenv("WEATHER_API_KEY"),
        timeout_seconds=float(os.getenv("WEATHER_TIMEOUT_SECONDS", "6.0")),
        max_retries=int(os.getenv("WEATHER_MAX_RETRIES", "3")),
        news_rss_url=os.getenv("NEWS_RSS_URL", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        preferences_path=DEFAULT_CONFIG_PATH,
    )
