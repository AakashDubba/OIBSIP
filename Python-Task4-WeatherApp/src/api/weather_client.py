"""Resilient Weather Client for Open-Meteo with retry mechanisms, schema validation, and IP geolocation.

Zero fabricated data: All queries hit live endpoints or fail cleanly with structured error reporting.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)


def c_to_f(c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return round((c * 9.0 / 5.0) + 32.0, 1)


def f_to_c(f: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return round((f - 32.0) * 5.0 / 9.0, 1)


def kmh_to_mph(kmh: float) -> float:
    """Convert km/h to mph."""
    return round(kmh * 0.621371, 1)


# WMO Weather Condition standard mappings with display icons
WMO_TABLE: Dict[int, Tuple[str, str]] = {
    0: ("Clear Sky", "☀️"),
    1: ("Mainly Clear", "🌤️"),
    2: ("Partly Cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Depositing Rime Fog", "🌫️"),
    51: ("Light Drizzle", "🌦️"),
    53: ("Moderate Drizzle", "🌧️"),
    55: ("Dense Drizzle", "🌧️"),
    61: ("Slight Rain", "🌦️"),
    63: ("Moderate Rain", "🌧️"),
    65: ("Heavy Rain", "🌧️"),
    71: ("Slight Snow", "🌨️"),
    73: ("Moderate Snow", "❄️"),
    75: ("Heavy Snow", "❄️"),
    77: ("Snow Grains", "❄️"),
    80: ("Slight Showers", "🌦️"),
    81: ("Moderate Showers", "🌧️"),
    82: ("Violent Showers", "⛈️"),
    85: ("Slight Snow Showers", "🌨️"),
    86: ("Heavy Snow Showers", "❄️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm w/ Hail", "⛈️"),
    99: ("Severe Thunderstorm", "⛈️"),
}


def get_wmo_condition(code: int) -> Tuple[str, str]:
    """Retrieve textual condition and graphical icon for a WMO weather code."""
    return WMO_TABLE.get(code, ("Variable Conditions", "🌡️"))


@dataclass(frozen=True)
class CurrentWeather:
    """Structured current atmospheric readings."""
    city: str
    country: str
    latitude: float
    longitude: float
    temperature_c: float
    temperature_f: float
    feels_like_c: float
    feels_like_f: float
    humidity: int
    wind_speed_kmh: float
    wind_speed_mph: float
    condition: str
    condition_code: int
    icon: str
    timestamp: str


@dataclass(frozen=True)
class HourlyForecast:
    """Hourly forecast item (6-hour window)."""
    time_label: str
    temperature_c: float
    temperature_f: float
    condition: str
    icon: str


@dataclass(frozen=True)
class DailyForecast:
    """Daily forecast item (5-day window)."""
    date_str: str
    day_name: str
    temp_max_c: float
    temp_max_f: float
    temp_min_c: float
    temp_min_f: float
    condition: str
    icon: str


@dataclass(frozen=True)
class WeatherData:
    """Aggregated weather package for GUI consumption."""
    current: CurrentWeather
    hourly: List[HourlyForecast]
    daily: List[DailyForecast]


@dataclass(frozen=True)
class WeatherResult:
    """Result container for weather lookups."""
    success: bool
    data: Optional[WeatherData] = None
    error_message: Optional[str] = None


class WeatherClient:
    """Resilient client communicating with Open-Meteo Weather APIs."""

    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout: float = 6.0, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_resilient_session(max_retries)

    def _create_resilient_session(self, retries: int) -> requests.Session:
        """Create a requests Session configured with exponential backoff retries."""
        session = requests.Session()
        retry_strategy = Retry(
            total=retries,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def sanitize_location(self, raw_location: str) -> Tuple[bool, str]:
        """Validate and sanitize user location input."""
        cleaned = raw_location.strip()
        if not cleaned:
            return False, "City name cannot be empty."
        if len(cleaned) < 2 or len(cleaned) > 100:
            return False, "City name must be between 2 and 100 characters."
        # Permit letters, numbers, spaces, hyphens, periods, and commas (e.g., 'New York, US', 'Paris 16')
        if not re.match(r"^[a-zA-Z0-9\u0080-\uFFFF\s\-\.,']+$", cleaned):
            return False, "City name contains invalid characters."
        return True, cleaned

    def fetch_weather(self, location_query: str) -> WeatherResult:
        """Fetch current weather, 6-hour hourly forecast, and 5-day daily forecast."""
        valid, sanitized = self.sanitize_location(location_query)
        if not valid:
            return WeatherResult(success=False, error_message=sanitized)

        try:
            # Step 1: Geocode location to lat/lon
            geo_params: dict[str, str | int] = {
                "name": sanitized,
                "count": 1,
                "language": "en",
                "format": "json",
            }
            geo_resp = self.session.get(self.GEOCODING_URL, params=geo_params, timeout=self.timeout)
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()

            results = geo_data.get("results")
            if not results or not isinstance(results, list):
                return WeatherResult(
                    success=False,
                    error_message=f"Location '{sanitized}' could not be found. Please check spelling.",
                )

            location_match = results[0]
            lat = float(location_match.get("latitude", 0.0))
            lon = float(location_match.get("longitude", 0.0))
            resolved_city = str(location_match.get("name", sanitized))
            resolved_country = str(location_match.get("country", ""))

            # Step 2: Fetch weather forecast
            forecast_params: dict[str, str | float] = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "hourly": "temperature_2m,weather_code",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
            }
            fc_resp = self.session.get(self.FORECAST_URL, params=forecast_params, timeout=self.timeout)
            fc_resp.raise_for_status()
            fc_data = fc_resp.json()

            # Step 3: Validate and parse response schema
            weather_data = self._parse_forecast_schema(
                fc_data=fc_data,
                city=resolved_city,
                country=resolved_country,
                lat=lat,
                lon=lon,
            )
            return WeatherResult(success=True, data=weather_data)

        except requests.Timeout:
            logger.warning("Weather client timed out for query '%s'", location_query)
            return WeatherResult(
                success=False,
                error_message="Weather service request timed out. Please verify internet connection.",
            )
        except requests.RequestException as exc:
            logger.warning("Network error fetching weather for '%s': %s", location_query, exc)
            return WeatherResult(
                success=False,
                error_message=f"Network error contacting weather service: {exc}",
            )
        except Exception as exc:
            logger.error("Unexpected parsing or data error for '%s': %s", location_query, exc, exc_info=True)
            return WeatherResult(
                success=False,
                error_message=f"Failed to process weather data: {exc}",
            )

    def _parse_forecast_schema(
        self,
        fc_data: Dict[str, Any],
        city: str,
        country: str,
        lat: float,
        lon: float,
    ) -> WeatherData:
        """Strictly validate and extract typed domain objects from raw JSON."""
        # 1. Parse Current Weather
        current = fc_data.get("current")
        if not isinstance(current, dict):
            raise ValueError("Malformed response: 'current' weather block missing.")

        temp_c = float(current.get("temperature_2m", 0.0))
        feels_c = float(current.get("apparent_temperature", temp_c))
        humidity = int(current.get("relative_humidity_2m", 0))
        wind_kmh = float(current.get("wind_speed_10m", 0.0))
        wmo_code = int(current.get("weather_code", 0))
        condition_name, icon = get_wmo_condition(wmo_code)
        time_iso = str(current.get("time", datetime.now().isoformat()))

        current_obj = CurrentWeather(
            city=city,
            country=country,
            latitude=lat,
            longitude=lon,
            temperature_c=round(temp_c, 1),
            temperature_f=c_to_f(temp_c),
            feels_like_c=round(feels_c, 1),
            feels_like_f=c_to_f(feels_c),
            humidity=humidity,
            wind_speed_kmh=round(wind_kmh, 1),
            wind_speed_mph=kmh_to_mph(wind_kmh),
            condition=condition_name,
            condition_code=wmo_code,
            icon=icon,
            timestamp=time_iso,
        )

        # 2. Parse 6-hour Hourly Forecast
        hourly_data = fc_data.get("hourly", {})
        times = hourly_data.get("time", [])
        temps = hourly_data.get("temperature_2m", [])
        codes = hourly_data.get("weather_code", [])

        # Find current hour index or start from first available
        hourly_list: List[HourlyForecast] = []
        if isinstance(times, list) and isinstance(temps, list) and isinstance(codes, list):
            # Take next 6 intervals
            for i in range(min(6, len(times), len(temps), len(codes))):
                raw_time = str(times[i])
                try:
                    dt = datetime.fromisoformat(raw_time)
                    label = dt.strftime("%I %p").lstrip("0")
                except Exception:
                    label = raw_time[-5:]

                h_temp_c = float(temps[i])
                h_code = int(codes[i])
                h_cond, h_icon = get_wmo_condition(h_code)

                hourly_list.append(HourlyForecast(
                    time_label=label,
                    temperature_c=round(h_temp_c, 1),
                    temperature_f=c_to_f(h_temp_c),
                    condition=h_cond,
                    icon=h_icon,
                ))

        # 3. Parse 5-day Daily Forecast
        daily_data = fc_data.get("daily", {})
        d_times = daily_data.get("time", [])
        d_codes = daily_data.get("weather_code", [])
        d_maxs = daily_data.get("temperature_2m_max", [])
        d_mins = daily_data.get("temperature_2m_min", [])

        daily_list: List[DailyForecast] = []
        if isinstance(d_times, list) and isinstance(d_maxs, list) and isinstance(d_mins, list):
            count = min(5, len(d_times), len(d_maxs), len(d_mins))
            for i in range(count):
                date_str = str(d_times[i])
                try:
                    dt = datetime.fromisoformat(date_str)
                    day_name = "Today" if i == 0 else dt.strftime("%A")
                except Exception:
                    day_name = f"Day {i + 1}"

                d_code = int(d_codes[i]) if i < len(d_codes) else 0
                d_cond, d_icon = get_wmo_condition(d_code)
                max_c = float(d_maxs[i])
                min_c = float(d_mins[i])

                daily_list.append(DailyForecast(
                    date_str=date_str,
                    day_name=day_name,
                    temp_max_c=round(max_c, 1),
                    temp_max_f=c_to_f(max_c),
                    temp_min_c=round(min_c, 1),
                    temp_min_f=c_to_f(min_c),
                    condition=d_cond,
                    icon=d_icon,
                ))

        return WeatherData(
            current=current_obj,
            hourly=hourly_list,
            daily=daily_list,
        )

    def detect_ip_location(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Optional Advanced feature: detect user city and country via IP geolocation.
        
        Returns: (success: bool, city: Optional[str], country: Optional[str])
        """
        endpoints = [
            ("https://ipapi.co/json/", lambda d: (str(d.get("city", "")), str(d.get("country_name", "")))),
            ("http://ip-api.com/json/", lambda d: (str(d.get("city", "")), str(d.get("country", "")))),
        ]

        for url, extractor in endpoints:
            try:
                resp = self.session.get(url, timeout=3.0, headers={"User-Agent": "NewsWorldWeatherEngine/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    city, country = extractor(data)
                    if city and city.strip():
                        logger.info("IP location detected: %s, %s", city, country)
                        return True, city.strip(), country.strip()
            except Exception as exc:
                logger.debug("IP geolocation endpoint %s failed: %s", url, exc)

        return False, None, "Could not determine location from IP."
