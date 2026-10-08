"""Fast unit test verifying non-blocking thread decoupling and Tkinter callback handoff."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock
import pytest

from src.api.news_bridge import RegionalNewsBridge, RegionalNewsResult
from src.api.weather_client import (
    CurrentWeather,
    WeatherClient,
    WeatherData,
    WeatherResult,
)
from src.config import UserPreferences
from src.ui.app_window import WeatherAppWindow


@pytest.fixture
def mock_payload() -> WeatherData:
    curr = CurrentWeather(
        city="Oslo",
        country="Norway",
        latitude=59.91,
        longitude=10.75,
        temperature_c=12.0,
        temperature_f=53.6,
        feels_like_c=11.0,
        feels_like_f=51.8,
        humidity=68,
        wind_speed_kmh=10.0,
        wind_speed_mph=6.2,
        condition="Clear Sky",
        condition_code=0,
        icon="☀️",
        timestamp="2026-10-08T01:00",
    )
    return WeatherData(current=curr, hourly=[], daily=[])


def test_network_runs_off_gui_thread(mock_payload: WeatherData) -> None:
    main_thread_id = threading.get_ident()
    worker_thread_id: int | None = None
    callback_thread_id: int | None = None

    worker_executed = threading.Event()
    callback_finished = threading.Event()

    # 1. Mock weather client returning payload immediately
    mock_weather_client = MagicMock(spec=WeatherClient)

    def worker_fetch(location: str) -> WeatherResult:
        nonlocal worker_thread_id
        worker_thread_id = threading.get_ident()
        worker_executed.set()
        return WeatherResult(success=True, data=mock_payload)

    mock_weather_client.fetch_weather.side_effect = worker_fetch

    mock_news_bridge = MagicMock(spec=RegionalNewsBridge)
    mock_news_bridge.fetch_regional_news.return_value = RegionalNewsResult(
        success=True,
        headlines=[],
        region="Oslo",
        message="OK",
    )

    prefs = UserPreferences(last_city="Oslo", temperature_unit="C")
    app = WeatherAppWindow(
        weather_client=mock_weather_client,
        news_bridge=mock_news_bridge,
        preferences=prefs,
    )

    # 2. Wrap _handle_query_results to record callback thread
    orig_handle = app._handle_query_results

    def wrapped_handle(weather_res: WeatherResult, news_res: RegionalNewsResult | None) -> None:
        nonlocal callback_thread_id
        callback_thread_id = threading.get_ident()
        orig_handle(weather_res, news_res)
        callback_finished.set()

    app._handle_query_results = wrapped_handle  # type: ignore[assignment]

    try:
        # Start background query
        t0 = time.time()
        app.start_weather_query("Oslo")

        # Verify main thread was not blocked (returned in < 0.05s)
        assert time.time() - t0 < 0.05, "start_weather_query must not block main thread"
        assert app._is_loading is True

        # Wait for worker thread to signal
        assert worker_executed.wait(timeout=0.3), "Worker thread did not execute"

        # Verify network function executed on a background thread
        assert worker_thread_id is not None
        assert worker_thread_id != main_thread_id, (
            f"Worker ({worker_thread_id}) must run on a background thread distinct from main thread ({main_thread_id})"
        )

        # Pump Tkinter event loop briefly on main thread to process the scheduled after() callback
        wait_deadline = time.time() + 0.3
        while not callback_finished.is_set() and time.time() < wait_deadline:
            app.update_idletasks()
            app.update()
            time.sleep(0.005)

        assert callback_finished.is_set(), "GUI callback was not dispatched via self.after()"

        # Verify callback executed strictly on the main GUI thread
        assert callback_thread_id is not None
        assert callback_thread_id == main_thread_id, (
            f"Callback ({callback_thread_id}) must execute on the main GUI thread ({main_thread_id})"
        )

        # Verify state and UI content updated cleanly without exceptions
        assert app._is_loading is False
        assert app.temperature_label.cget("text") == "12.0°C"
        assert app.location_title.cget("text") == "Oslo, Norway"

    finally:
        app.destroy()
