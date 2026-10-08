"""Tests for UI logic, rendering formatting, and unit conversion responsiveness."""

from __future__ import annotations

import pytest
from src.api.weather_client import (
    CurrentWeather,
    DailyForecast,
    HourlyForecast,
    WeatherData,
)
from src.ui.app_window import WeatherAppWindow


@pytest.fixture
def sample_weather_data() -> WeatherData:
    curr = CurrentWeather(
        city="Paris",
        country="France",
        latitude=48.8566,
        longitude=2.3522,
        temperature_c=20.0,
        temperature_f=68.0,
        feels_like_c=19.5,
        feels_like_f=67.1,
        humidity=65,
        wind_speed_kmh=15.0,
        wind_speed_mph=9.3,
        condition="Clear Sky",
        condition_code=0,
        icon="☀️",
        timestamp="2026-10-08T12:00",
    )
    hourly = [
        HourlyForecast("1 PM", 21.0, 69.8, "Clear Sky", "☀️"),
        HourlyForecast("2 PM", 22.0, 71.6, "Mainly Clear", "🌤️"),
    ]
    daily = [
        DailyForecast("2026-10-08", "Today", 23.0, 73.4, 14.0, 57.2, "Clear Sky", "☀️"),
        DailyForecast("2026-10-09", "Friday", 21.0, 69.8, 13.0, 55.4, "Partly Cloudy", "⛅"),
    ]
    return WeatherData(current=curr, hourly=hourly, daily=daily)


def test_ui_render_weather_celsius_and_fahrenheit(sample_weather_data: WeatherData) -> None:
    # Initialize window without showing mainloop
    app = WeatherAppWindow()
    try:
        # 1. Render in Celsius
        app.current_unit = "C"
        app.render_weather(sample_weather_data)
        assert app.temperature_label.cget("text") == "20.0°C"
        assert app.feels_card["value"].cget("text") == "19.5°C"
        assert app.wind_card["value"].cget("text") == "15.0 km/h"

        # 2. Switch to Fahrenheit dynamically
        app.on_unit_toggled("°F")
        assert app.current_unit == "F"
        assert app.temperature_label.cget("text") == "68.0°F"
        assert app.feels_card["value"].cget("text") == "67.1°F"
        assert app.wind_card["value"].cget("text") == "9.3 mph"

    finally:
        app.destroy()
