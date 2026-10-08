"""Weather query service with live API integration and resilient error handling.

Uses Open-Meteo open weather API by default (free, public, no private key needed),
or OpenWeatherMap when WEATHER_API_KEY is configured.
Never fabricates fake weather readings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeatherInfo:
    """Structured weather report data."""
    city: str
    country: str
    temperature_c: float
    temperature_f: float
    condition: str
    humidity: Optional[int]
    wind_speed_kmh: float

    @property
    def summary(self) -> str:
        hum_text = f", humidity {self.humidity}%" if self.humidity is not None else ""
        return (
            f"The weather in {self.city}, {self.country} is currently {self.condition} "
            f"at {self.temperature_c:.1f}°C ({self.temperature_f:.1f}°F) "
            f"with winds at {self.wind_speed_kmh:.1f} km/h{hum_text}."
        )


@dataclass(frozen=True)
class WeatherResponse:
    """Response returned by weather query service."""
    success: bool
    data: Optional[WeatherInfo]
    message: str


# WMO Weather interpretation codes (WW) standard
WMO_CODE_MAP: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherService:
    """Queries real weather information from external weather APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 6.0,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def get_weather(self, city: str) -> WeatherResponse:
        """Fetch real current weather for a specified location."""
        sanitized_city = city.strip()
        if not sanitized_city:
            return WeatherResponse(
                success=False,
                data=None,
                message="City name must not be empty.",
            )

        try:
            # 1. Geocode city name to lat/lon using Open-Meteo geocoding API
            geo_url = "https://geocoding-api.open-meteo.com/v1/search"
            geo_params: dict[str, str | int] = {"name": sanitized_city, "count": 1, "language": "en", "format": "json"}
            geo_resp = requests.get(geo_url, params=geo_params, timeout=self.timeout)
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()

            results = geo_data.get("results")
            if not results:
                return WeatherResponse(
                    success=False,
                    data=None,
                    message=f"Location '{sanitized_city}' was not found by geocoding service.",
                )

            location = results[0]
            lat = float(location.get("latitude", 0.0))
            lon = float(location.get("longitude", 0.0))
            resolved_city = location.get("name", sanitized_city)
            country = location.get("country", "")

            # 2. Fetch current weather conditions
            forecast_url = "https://api.open-meteo.com/v1/forecast"
            forecast_params: dict[str, str | float] = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            }
            fc_resp = requests.get(forecast_url, params=forecast_params, timeout=self.timeout)
            fc_resp.raise_for_status()
            fc_data = fc_resp.json()

            current = fc_data.get("current", {})
            temp_c = float(current.get("temperature_2m", 0.0))
            temp_f = (temp_c * 9.0 / 5.0) + 32.0
            humidity = int(current.get("relative_humidity_2m")) if "relative_humidity_2m" in current else None
            wind_kmh = float(current.get("wind_speed_10m", 0.0))
            wmo_code = int(current.get("weather_code", 0))
            condition = WMO_CODE_MAP.get(wmo_code, "Variable conditions")

            info = WeatherInfo(
                city=resolved_city,
                country=country,
                temperature_c=temp_c,
                temperature_f=temp_f,
                condition=condition,
                humidity=humidity,
                wind_speed_kmh=wind_kmh,
            )

            return WeatherResponse(
                success=True,
                data=info,
                message=info.summary,
            )

        except requests.Timeout:
            logger.warning("Weather API request timed out for city: %s", sanitized_city)
            return WeatherResponse(
                success=False,
                data=None,
                message="External weather service timed out. Please verify network connectivity.",
            )
        except requests.RequestException as exc:
            logger.warning("Network error contacting weather service: %s", exc)
            return WeatherResponse(
                success=False,
                data=None,
                message=f"Network error querying weather service: {exc}",
            )
        except Exception as exc:
            logger.error("Unexpected error in weather service: %s", exc)
            return WeatherResponse(
                success=False,
                data=None,
                message=f"External weather service is currently unavailable: {exc}",
            )
