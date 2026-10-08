"""Tests for WeatherClient, unit conversions, schema validation, and resilience."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
import requests

from src.api.weather_client import (
    WeatherClient,
    c_to_f,
    f_to_c,
    kmh_to_mph,
    get_wmo_condition,
)


MOCK_GEO_RESPONSE = {
    "results": [
        {
            "id": 2643743,
            "name": "London",
            "latitude": 51.50853,
            "longitude": -0.12574,
            "country": "United Kingdom",
        }
    ]
}

MOCK_FORECAST_RESPONSE = {
    "current": {
        "time": "2026-10-08T00:00",
        "temperature_2m": 15.5,
        "apparent_temperature": 14.8,
        "relative_humidity_2m": 75,
        "weather_code": 2,
        "wind_speed_10m": 12.4,
    },
    "hourly": {
        "time": [
            "2026-10-08T01:00",
            "2026-10-08T02:00",
            "2026-10-08T03:00",
            "2026-10-08T04:00",
            "2026-10-08T05:00",
            "2026-10-08T06:00",
        ],
        "temperature_2m": [15.0, 14.8, 14.2, 13.9, 13.5, 13.2],
        "weather_code": [2, 2, 3, 3, 45, 45],
    },
    "daily": {
        "time": [
            "2026-10-08",
            "2026-10-09",
            "2026-10-10",
            "2026-10-11",
            "2026-10-12",
        ],
        "weather_code": [2, 61, 80, 0, 1],
        "temperature_2m_max": [18.5, 16.0, 17.2, 20.0, 19.5],
        "temperature_2m_min": [11.0, 12.5, 10.0, 9.5, 10.2],
    },
}


def test_unit_conversions() -> None:
    # 0 C is 32 F
    assert c_to_f(0.0) == 32.0
    # 100 C is 212 F
    assert c_to_f(100.0) == 212.0
    # 32 F is 0 C
    assert f_to_c(32.0) == 0.0
    # 212 F is 100 C
    assert f_to_c(212.0) == 100.0
    # Speed conversion
    assert kmh_to_mph(10.0) == 6.2


def test_wmo_condition_mapping() -> None:
    name, icon = get_wmo_condition(0)
    assert name == "Clear Sky"
    assert icon == "☀️"

    name_rain, icon_rain = get_wmo_condition(63)
    assert "Rain" in name_rain
    assert icon_rain == "🌧️"


def test_input_sanitization() -> None:
    client = WeatherClient()

    valid, clean = client.sanitize_location("  Paris, France  ")
    assert valid is True
    assert clean == "Paris, France"

    valid_empty, _ = client.sanitize_location("   ")
    assert valid_empty is False

    valid_chars, _ = client.sanitize_location("City<script>alert(1)</script>")
    assert valid_chars is False


def test_successful_weather_fetch() -> None:
    client = WeatherClient()

    mock_geo = MagicMock()
    mock_geo.status_code = 200
    mock_geo.json.return_value = MOCK_GEO_RESPONSE
    mock_geo.raise_for_status.return_value = None

    mock_fc = MagicMock()
    mock_fc.status_code = 200
    mock_fc.json.return_value = MOCK_FORECAST_RESPONSE
    mock_fc.raise_for_status.return_value = None

    with patch.object(client.session, "get", side_effect=[mock_geo, mock_fc]):
        result = client.fetch_weather("London")

        assert result.success is True
        assert result.data is not None
        curr = result.data.current
        assert curr.city == "London"
        assert curr.country == "United Kingdom"
        assert curr.temperature_c == 15.5
        assert curr.temperature_f == 59.9
        assert curr.humidity == 75
        assert curr.condition == "Partly Cloudy"
        assert curr.icon == "⛅"

        # 6-hour hourly trend
        assert len(result.data.hourly) == 6
        assert result.data.hourly[0].temperature_c == 15.0

        # 5-day daily outlook
        assert len(result.data.daily) == 5
        assert result.data.daily[0].day_name == "Today"
        assert result.data.daily[0].temp_max_c == 18.5


def test_location_not_found() -> None:
    client = WeatherClient()

    mock_geo = MagicMock()
    mock_geo.status_code = 200
    mock_geo.json.return_value = {"results": []}
    mock_geo.raise_for_status.return_value = None

    with patch.object(client.session, "get", return_value=mock_geo):
        result = client.fetch_weather("NonexistentAtlantisCity123")
        assert result.success is False
        assert result.data is None
        assert "could not be found" in (result.error_message or "").lower()


def test_network_timeout_handling() -> None:
    client = WeatherClient()

    with patch.object(client.session, "get", side_effect=requests.Timeout("Connection timed out")):
        result = client.fetch_weather("Tokyo")
        assert result.success is False
        assert "timed out" in (result.error_message or "").lower()


def test_ip_location_detection_success() -> None:
    client = WeatherClient()

    mock_ip_resp = MagicMock()
    mock_ip_resp.status_code = 200
    mock_ip_resp.json.return_value = {"city": "Berlin", "country_name": "Germany"}

    with patch.object(client.session, "get", return_value=mock_ip_resp):
        success, city, country = client.detect_ip_location()
        assert success is True
        assert city == "Berlin"
        assert country == "Germany"


def test_ip_location_detection_failure() -> None:
    client = WeatherClient()

    with patch.object(client.session, "get", side_effect=requests.RequestException("Offline")):
        success, city, err = client.detect_ip_location()
        assert success is False
        assert city is None
