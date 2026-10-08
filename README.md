# Oasis Infobyte Python Internship — Master Portfolio Repository (OIBSIP)

A production-grade, Advanced-tier portfolio repository developed for the **Oasis Infobyte Internship Program (OIBSIP)**. This repository houses three decoupled, high-caliber software systems engineered with strict modularity, non-blocking asynchronous architectures, robust cryptographic security, and zero fabricated production data:

1. **Task 1: NewsWorld AI Voice Assistant** — Non-blocking threaded audio capture and background TTS queue, regex/NLP intent classification, live RSS feed ingestion with TTL caching, real-time weather, web search, two-stage email confirmation, and thread-safe reminder alarms.
2. **Task 4: NewsWorld Contextual Weather Engine** — Modern dark-mode CustomTkinter desktop meteorological application, non-blocking multithreaded network I/O, comprehensive atmospheric metric cards, 6-hour hourly trend forecasts, 5-day daily outlooks, dynamic Celsius/Fahrenheit toggle, resilient Open-Meteo client with exponential backoff retries, and decoupled regional breaking news integration.
3. **Task 5: ClinicFlow AI Secure Clinical Messaging Hub** — High-concurrency multi-client TCP socket messaging server, 4-byte length-prefixed binary JSON framing, PBKDF2-HMAC-SHA256 authentication with per-user cryptographic salts, departmental room segregation (`#triage`, `#physician-consult`, `#general`), role-based access control (`DOCTOR`, `NURSE`, `ADMIN`), SQLite message replay, security audit logging, and a dark-mode Tkinter desktop GUI.

---

## 🏛️ Master Portfolio Architecture

```
OIBSIP/
├── .gitignore                               # Comprehensive exclusion list (.env, *.db, caches)
├── README.md                                # Master ecosystem architecture and verification guide
│
├── Python-Task1-VoiceAssistant/             # Task 1: NewsWorld AI Voice Assistant
│   ├── src/
│   │   ├── core/
│   │   │   ├── audio_engine.py              # Non-blocking threaded audio capture & TTS queue (with text fallback)
│   │   │   ├── dispatcher.py                # Regex/NLP intent classification engine
│   │   │   ├── email_service.py             # Two-stage email drafting with explicit user confirmation
│   │   │   └── reminder_service.py          # Thread-safe background reminder timer scheduler
│   │   ├── services/
│   │   │   ├── news_service.py              # Live RSS ingestion with in-memory TTL caching
│   │   │   ├── weather_service.py           # Resilient Open-Meteo current weather integration
│   │   │   └── search_service.py            # DuckDuckGo instant answers & browser search bridge
│   │   ├── config.py                        # Safe environment configuration loader
│   │   └── main.py                          # CLI entrypoint with SIGINT handling & text/voice routing
│   ├── tests/
│   │   ├── test_audio_engine.py             # Audio queue and backend tests
│   │   ├── test_dispatcher.py               # Intent routing test suite
│   │   ├── test_news_service.py             # RSS parsing and TTL cache tests
│   │   └── test_reminder_and_email.py       # Timer and email security tests
│   ├── requirements.txt                     # Independent dependency manifest
│   └── README.md                            # Task 1 documentation & demo guide
│
├── Python-Task4-WeatherApp/                 # Task 4: NewsWorld Contextual Weather Engine
│   ├── src/
│   │   ├── api/
│   │   │   ├── weather_client.py            # Resilient Open-Meteo client (retries, timeouts, schemas, IP geolocation)
│   │   │   └── news_bridge.py               # Decoupled regional breaking news integration adapter
│   │   ├── ui/
│   │   │   └── app_window.py                # Dark-mode CustomTkinter desktop interface & metric cards
│   │   ├── config.py                        # Persistent JSON user preferences (last city, unit) & env config
│   │   └── main.py                          # Desktop application entrypoint
│   ├── tests/
│   │   ├── test_weather_client.py           # Unit conversions, schema validation, resilience, IP detection
│   │   ├── test_news_bridge.py              # Regional RSS feed parsing and error handling
│   │   ├── test_config.py                   # Atomic JSON persistence and corruption recovery
│   │   ├── test_ui_logic.py                 # GUI initialization and dynamic °C/°F conversion tests
│   │   └── test_responsiveness.py           # Non-blocking thread decoupling and Tkinter callback handoff
│   ├── smoke_test.py                        # Automated runtime GUI & pipeline verification harness
│   ├── requirements.txt                     # Independent dependency manifest
│   └── README.md                            # Task 4 documentation & demo guide
│
└── Python-Task5-ChatApplication/            # Task 5: ClinicFlow AI Secure Clinical Messaging Hub
    ├── src/
    │   ├── protocol/
    │   │   ├── schemas.py                   # Typed dataclass schemas (packet_id, type, role, room, payload)
    │   │   └── serializer.py                # 4-byte length-prefixed binary framing engine
    │   ├── server/
    │   │   ├── db.py                        # SQLite audit logging, replay store, PBKDF2 salt/hashing
    │   │   ├── connection_manager.py        # Thread-safe client session, room, and role manager
    │   │   └── server.py                    # Concurrent multi-client TCP socket server
    │   ├── client/
    │   │   ├── client.py                    # Dual-threaded socket client engine
    │   │   ├── gui.py                       # Modern Tkinter desktop GUI client
    │   │   └── cli.py                       # Lightweight terminal CLI client
    │   └── main.py                          # Multi-mode CLI launcher (--server, --gui, --cli)
    ├── tests/
    │   ├── test_protocol.py                 # Framing, schema validation, and Unicode transit tests
    │   ├── test_security_db.py              # PBKDF2 verification, per-user salt isolation, replay tests
    │   └── test_server.py                   # Room segregation, role-based access, and cleanup tests
    ├── smoke_test.py                        # End-to-end multi-client runtime smoke test
    ├── requirements.txt                     # Independent dependency manifest
    └── README.md                            # Task 5 documentation & demo guide
```

---

## 📋 Comprehensive Requirements Audit

| Project | Oasis Requirement | Implementation Details | Verified Status |
| :--- | :--- | :--- | :---: |
| **Task 1: Voice Assistant** | Non-blocking Audio Capture & TTS | Separate background daemon worker draining a `queue.Queue[Optional[str]]`. Audio playback never blocks listening. | ✅ **PASSED** |
| | Text Fallback Mode | Headless/microphone-free operation with `TextInputBackend` and `--mode text`. | ✅ **PASSED** |
| | Extensible Regex/NLP Dispatcher | Intent pattern matching with named regex groups and typed parameter routing. | ✅ **PASSED** |
| | Live RSS News & TTL Caching | BBC RSS ingestion with thread-safe in-memory TTL caching. Zero fake headlines. | ✅ **PASSED** |
| | Live Weather Queries | Resilient Open-Meteo geocoding and forecast queries. Zero fake data. | ✅ **PASSED** |
| | Web Search Integration | DuckDuckGo instant answer queries with default browser fallback. | ✅ **PASSED** |
| | Safe Email Workflow | Two-stage flow: generates preview draft; sending strictly requires explicit secondary confirmation. Zero credential logging. | ✅ **PASSED** |
| | Reminders & Alarm Scheduling | Thread-safe background `threading.Timer` daemon scheduler with audible/visual alerts. | ✅ **PASSED** |
| | Graceful Shutdown | Clean `signal.SIGINT` and resource teardown. | ✅ **PASSED** |
| **Task 4: Weather Engine** | Dark-Mode CustomTkinter GUI | Modern dark interface (`set_appearance_mode("Dark")`) with elevated metric cards. | ✅ **PASSED** |
| | Non-blocking Network Operations | Asynchronous worker threads (`_query_worker`) with thread-safe queue dispatch via `self.after()`. GUI never freezes. | ✅ **PASSED** |
| | Atmospheric Metrics | Current temperature, humidity, wind velocity, feels-like, and graphical condition icons. | ✅ **PASSED** |
| | 6-Hour Hourly Trend | 6-hour forecast cards displaying hour, graphical icon, and temperature. | ✅ **PASSED** |
| | 5-Day Daily Outlook | 5-day daily cards displaying day name, condition, and High/Low temperature ranges. | ✅ **PASSED** |
| | Dynamic °C / °F Toggle | Segmented control with instantaneous client-side recalculation without network re-fetching. | ✅ **PASSED** |
| | Resilient Weather Client | Open-Meteo API with `urllib3.util.Retry` exponential backoff and schema validation. | ✅ **PASSED** |
| | Regional News Bridge | Decoupled adapter surfacing local breaking headlines for queried locations. | ✅ **PASSED** |
| | Persistent User Preferences | Atomic JSON persistence (`weather_preferences.json`) for cached last city and unit preference. | ✅ **PASSED** |
| | IP-based Location Detection | Optional Advanced Feature: resolves current city and country via IP geolocation. | ✅ **IMPLEMENTED AND TESTED** |
| **Task 5: Chat Application** | Binary Length-Prefixed Framing | 4-byte big-endian unsigned integer prefix (`>I`) eliminating TCP packet fragmentation. | ✅ **PASSED** |
| | Concurrent TCP Server | Threaded multi-client listener with thread-safe session and room management. | ✅ **PASSED** |
| | Departmental Room Segregation | Broadcasts strictly isolated to members of `#triage`, `#physician-consult`, and `#general`. | ✅ **PASSED** |
| | Role-Based Access Control | Enforced access policies for `DOCTOR`, `NURSE`, and `ADMIN`. | ✅ **PASSED** |
| | PBKDF2-HMAC-SHA256 Auth | Per-user 16-byte random salt (`os.urandom(16)`) and 100,000 PBKDF2 iterations. Never stores plaintext. | ✅ **PASSED** |
| | SQLite Audit Trail & Replay | Persistent SQLite store with automatic history replay on room join and audit event logging. | ✅ **PASSED** |
| | Dual Client Interfaces | Full Tkinter desktop GUI client + lightweight terminal CLI client. | ✅ **PASSED** |
| | Unicode & Emoji Transit | Full Unicode and clinical emoji message transit without byte corruption. | ✅ **PASSED** |
| | Clean Disconnection | Graceful client and server socket termination on exit. | ✅ **PASSED** |

---

## ⚡ Quickstart & Execution Guide

### Target Environment
- **Python 3.11+** (Tested on Python 3.11.9, Windows 11)

### 1. Task 1: NewsWorld AI Voice Assistant
```bash
cd Python-Task1-VoiceAssistant
pip install -r requirements.txt

# Run in Text Fallback Mode (No microphone required):
python -m src.main --mode text

# Run in Voice Mode (Requires microphone and speakers):
python -m src.main --mode voice

# Run automated tests:
pytest -v
```

### 2. Task 4: NewsWorld Contextual Weather Engine
```bash
cd Python-Task4-WeatherApp
pip install -r requirements.txt

# Launch Desktop GUI:
python -m src.main

# Launch with custom initial location:
python -m src.main --city "Tokyo"

# Run automated tests & smoke test:
pytest -v
python smoke_test.py
```

### 3. Task 5: ClinicFlow AI Secure Clinical Messaging Hub
```bash
cd Python-Task5-ChatApplication
pip install -r requirements.txt

# 1. Start the TCP Server:
python -m src.main --server --port 8443

# 2. Launch the Desktop GUI Client (in separate terminal):
python -m src.main --gui --port 8443

# 3. Launch the Terminal CLI Client (optional):
python -m src.main --cli --port 8443

# Run automated tests & multi-client smoke test:
pytest -v
python smoke_test.py
```

---


## 🛡️ Security & Privacy Disclosures

- **No Real PHI / PII**: All clinical references, usernames, and test fixtures use synthetic, generic placeholders. No real patient data exists in this repository.
- **Credential Protection**: All sensitive tokens and credentials load strictly via environment variables. Credentials, plaintext passwords, salts, and tokens are never written to logs.
- **Git Cleanliness**: `.env`, `*.db`, `*.sqlite*`, local preference files (`*preferences.json`), and virtual environment caches are strictly excluded via `.gitignore`.
