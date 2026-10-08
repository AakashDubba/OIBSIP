"""Runtime Smoke Test for NewsWorld Contextual Weather Engine."""

import sys
import io

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from src.ui.app_window import WeatherAppWindow
from src.api.weather_client import WeatherClient
from src.api.news_bridge import RegionalNewsBridge
from src.config import UserPreferences


def run_smoke_test() -> None:
    print("=== 1. Starting WeatherApp Runtime Smoke Test ===")

    # Initialize GUI Window
    app = WeatherAppWindow(preferences=UserPreferences(last_city="Paris", temperature_unit="C"))
    print("[OK] GUI initialized successfully.")

    # Test Input Validation
    valid_city, clean_city = app.weather_client.sanitize_location("  Tokyo  ")
    assert valid_city and clean_city == "Tokyo"
    invalid_empty, _ = app.weather_client.sanitize_location("   ")
    assert not invalid_empty
    print("[OK] City input sanitization validated.")

    # Test Real Live Weather Client Fetch
    print("Fetching real meteorological data for Tokyo...")
    w_result = app.weather_client.fetch_weather("Tokyo")
    assert w_result.success and w_result.data is not None
    curr = w_result.data.current
    print(f"[OK] Weather fetched: {curr.city}, {curr.country} -> {curr.temperature_c}C / {curr.temperature_f}F, {curr.condition} {curr.icon}")

    # Test Real Live Regional News Bridge
    print("Fetching regional breaking headlines...")
    n_result = app.news_bridge.fetch_regional_news("Tokyo", country="Japan", limit=2)
    print(f"[OK] Regional news bridge executed: success={n_result.success}, {len(n_result.headlines)} headlines.")

    # Render Weather and News into GUI
    app.render_weather(w_result.data)
    app.render_news(n_result)
    temp_text = app.temperature_label.cget("text")
    feels_text = app.feels_card["value"].cget("text")
    print(f"[OK] Rendered Celsius: Temp Label = {temp_text}, Feels Like = {feels_text}")
    assert "C" in temp_text

    # Test Dynamic Celsius / Fahrenheit Toggle
    app.on_unit_toggled("°F")
    temp_text_f = app.temperature_label.cget("text")
    feels_text_f = app.feels_card["value"].cget("text")
    print(f"[OK] Rendered Fahrenheit: Temp Label = {temp_text_f}, Feels Like = {feels_text_f}")
    assert "F" in temp_text_f

    # Test Graceful News Bridge Degradation
    graceful_news = app.news_bridge.fetch_regional_news("   ")
    assert not graceful_news.success
    app.render_news(graceful_news)
    print("[OK] Graceful degradation rendered when news unavailable.")

    # Test IP Geolocation
    ip_ok, ip_city, ip_country = app.weather_client.detect_ip_location()
    print(f"[OK] Optional IP Geolocation: success={ip_ok}, city={ip_city}, country={ip_country}")

    # Destroy window cleanly
    app.destroy()
    print("=== SMOKE TEST COMPLETED SUCCESSFULLY WITH ZERO ERRORS ===")


if __name__ == "__main__":
    run_smoke_test()
