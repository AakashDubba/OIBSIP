"""Main entrypoint for NewsWorld Contextual Weather Engine."""

from __future__ import annotations

import argparse
import logging
import sys

from src.api.news_bridge import RegionalNewsBridge
from src.api.weather_client import WeatherClient
from src.config import get_app_config, load_preferences
from src.ui.app_window import WeatherAppWindow

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("NewsWorldWeatherApp")


def main() -> None:
    """Run desktop application."""
    parser = argparse.ArgumentParser(description="NewsWorld Contextual Weather Engine")
    parser.add_argument("--city", type=str, default=None, help="Initial city to load")
    args = parser.parse_args()

    app_config = get_app_config()
    prefs = load_preferences(app_config.preferences_path)

    if args.city:
        prefs.last_city = args.city

    weather_client = WeatherClient(
        timeout=app_config.timeout_seconds,
        max_retries=app_config.max_retries,
    )
    news_bridge = RegionalNewsBridge(
        default_rss_url=app_config.news_rss_url,
        timeout=app_config.timeout_seconds,
    )

    logger.info("Initializing NewsWorld Contextual Weather Engine GUI...")
    app = WeatherAppWindow(
        weather_client=weather_client,
        news_bridge=news_bridge,
        preferences=prefs,
    )
    app.mainloop()


if __name__ == "__main__":
    main()
