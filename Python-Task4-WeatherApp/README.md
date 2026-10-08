# NewsWorld Contextual Weather Engine (Oasis Infobyte Task 4)

An Advanced-tier, modern desktop meteorological application developed as part of the Oasis Infobyte Internship Program. Built with **CustomTkinter**, this engine delivers a responsive dark-mode GUI, non-blocking multithreaded network I/O, comprehensive current atmospheric metrics, 6-hour hourly trend forecasts, 5-day daily outlooks, dynamic Celsius/Fahrenheit toggling, resilient API retry mechanisms, and a decoupled regional breaking news integration bridge.

---

## 🎯 Architecture Overview

```
Python-Task4-WeatherApp/
├── src/
│   ├── api/
│   │   ├── weather_client.py    # Resilient Open-Meteo client (retries, timeouts, schemas, IP geolocation)
│   │   └── news_bridge.py       # Decoupled regional breaking news integration bridge
│   ├── ui/
│   │   └── app_window.py        # Dark-mode CustomTkinter desktop interface & metric cards
│   ├── config.py                # Persistent JSON preferences (last city, unit) & env config
│   └── main.py                  # Desktop application entrypoint
├── tests/
│   ├── test_weather_client.py   # Client resilience, geocoding, and conversion test suite
│   ├── test_news_bridge.py      # Regional news RSS parsing and error handling
│   ├── test_config.py           # Preferences persistence and corruption recovery
│   └── test_ui_logic.py         # GUI initialization and C/F dynamic switching tests
├── requirements.txt             # Independent dependency manifest
└── README.md                    # Documentation & demo talking points
```

---

## ✨ Features & Oasis Infobyte Requirements

| Requirement | Implementation Details | Status |
| :--- | :--- | :---: |
| **CustomTkinter GUI** | Modern dark-mode interface featuring elevated metric cards and clean typography. | ✅ Complete |
| **Non-blocking Network I/O** | All network requests run in background daemon threads (`WeatherWorker`). The main GUI thread never freezes or hangs. | ✅ Complete |
| **Atmospheric Metrics** | Real temperature, humidity, wind velocity, feels-like, and condition icons. | ✅ Complete |
| **6-Hour Hourly Forecast** | 6-hour trend cards displaying timestamp, graphical icon, and hourly temperature. | ✅ Complete |
| **5-Day Daily Forecast** | 5-day outlook displaying day names, conditions, and High/Low temperature ranges. | ✅ Complete |
| **Celsius / Fahrenheit Toggle** | Segmented button (`°C` / `°F`) with instantaneous dynamic conversion and metric card refresh. | ✅ Complete |
| **Input Sanitization** | Regex sanitization, boundary checks, and descriptive inline error messages. | ✅ Complete |
| **Resilient Weather Client** | Open-Meteo integration with `urllib3.util.Retry` exponential backoff, timeouts, and strict schema validation. Zero fabricated data. | ✅ Complete |
| **Regional News Bridge** | Decoupled adapter surfacing local breaking headlines for the queried city without fabricating articles. | ✅ Complete |
| **Persistent Preferences** | Atomic JSON storage for user's last queried city and preferred temperature unit. | ✅ Complete |
| **IP-based Location Detection** | Optional Advanced Feature: auto-detects user city and country via IP geolocation. | ✅ **IMPLEMENTED AND TESTED** |

---

## 🔒 Privacy & Architecture Integrity

1. **Zero Fake Production Data**: All meteorological data is retrieved from live Open-Meteo endpoints. If an API is unreachable or offline, the engine cleanly reports the error to the user rather than fabricating simulated data.
2. **Decoupled News Bridge**: The regional news bridge operates as an independent adapter. It does not depend on or modify external portfolio repositories.
3. **Thread Safety**: All background worker results are marshaled back to the GUI main loop using `self.after(0, ...)`, avoiding GUI thread race conditions.

---

## 🚀 Setup & Execution

### Tested Python Version
- **Python 3.11.9+** (Windows, Linux, macOS)

### 1. Installation
Navigate to the Task 4 directory and install requirements:
```bash
cd D:\College\Resume\VW\OASIS\OIBSIP\Python-Task4-WeatherApp
pip install -r requirements.txt
```

### 2. Configuration (Optional)
Create an optional `.env` file in the project folder to customize settings:
```env
WEATHER_TIMEOUT_SECONDS=6.0
WEATHER_MAX_RETRIES=3
NEWS_RSS_URL=https://feeds.bbci.co.uk/news/world/rss.xml
```

### 3. Launching the Desktop Application
```bash
python -m src.main
```
Or specify an initial city directly via CLI:
```bash
python -m src.main --city "Tokyo"
```

---

## 🧪 Automated Testing & Static Verification

### Running Pytest
```bash
pytest -v
```

### Running Static Type Checking (mypy)
```bash
mypy src
```

---
