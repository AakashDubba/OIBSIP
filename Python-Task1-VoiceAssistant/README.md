# NewsWorld AI Voice Assistant (Oasis Infobyte Task 1)

An Advanced-tier, modular AI Voice Assistant developed as part of the Oasis Infobyte Internship Program. Designed with a non-blocking threaded architecture, robust regex/NLP intent classification, live RSS feed ingestion with TTL caching, real weather lookup, web search integration, two-stage email confirmation, and thread-safe reminder scheduling.

---

## 🎯 Architecture Overview

```
Python-Task1-VoiceAssistant/
├── src/
│   ├── core/
│   │   ├── audio_engine.py       # Non-blocking threaded audio capture & TTS queue (with text fallback)
│   │   ├── dispatcher.py         # Regex/NLP intent classification engine
│   │   ├── email_service.py      # Two-stage email drafting with explicit user confirmation
│   │   └── reminder_service.py   # Thread-safe background reminder and timer scheduler
│   ├── services/
│   │   ├── news_service.py       # Live RSS ingestion with thread-safe in-memory TTL caching
│   │   ├── weather_service.py    # Resilient Open-Meteo current weather integration
│   │   └── search_service.py     # DuckDuckGo instant answer and browser search bridge
│   ├── config.py                 # Safe environment configuration loader
│   └── main.py                   # CLI entrypoint with graceful SIGINT handling
├── tests/
│   ├── test_dispatcher.py        # Intent dispatching test suite
│   ├── test_audio_engine.py      # Audio queue and backend tests
│   ├── test_news_service.py      # Live RSS parsing and TTL cache tests
│   └── test_reminder_and_email.py# Timer and email security tests
├── requirements.txt              # Independent dependency manifest
└── README.md                     # Documentation & demo talking points
```

---

## ✨ Features & Oasis Infobyte Requirements

| Requirement | Implementation Details | Status |
| :--- | :--- | :---: |
| **Non-blocking Audio & TTS** | Separate daemon worker consuming a `queue.Queue[str]`. TTS playback never blocks the command listening pipeline. | ✅ Complete |
| **Microphone & Text Fallback** | Pluggable input backends (`MicrophoneInputBackend` via SpeechRecognition + `TextInputBackend` for text console mode). | ✅ Complete |
| **Intent Dispatcher** | Extensible regex/NLP intent parser with named capture groups and structured routing. | ✅ Complete |
| **Live News & TTL Cache** | Real RSS parsing (`xml.etree.ElementTree`) across world/technology/business categories with thread-safe in-memory TTL caching. | ✅ Complete |
| **Weather Queries** | Real Open-Meteo geocoding and weather API queries with zero fabricated data. | ✅ Complete |
| **Web Search Integration** | Configurable DuckDuckGo instant answer lookups with automatic browser fallback. | ✅ Complete |
| **Safe Email Workflow** | Strict two-stage workflow: default creates a safe draft preview; actual sending requires explicit user confirmation. | ✅ Complete |
| **Reminders & Alarms** | Non-blocking background `threading.Timer` daemon scheduler with audible/visual alert notifications. | ✅ Complete |
| **Graceful Shutdown** | Handled via `signal.SIGINT` and clean component disposal. | ✅ Complete |

---

## 🔒 Privacy & Security Guarantees

1. **Zero Secret Logging**: SMTP passwords, user credentials, and email message bodies are strictly excluded from logs and audit trails.
2. **Explicit Confirmation**: The assistant will never automatically send an email upon voice command. A unique Draft ID is generated, and transmission strictly requires a secondary confirmation command (`confirm draft <ID>`).
3. **No Fabricated Production Data**: When external APIs or internet connections are offline, the assistant reports that the service is unavailable rather than fabricating fake news or weather readings.
4. **Environment Isolation**: All credentials (`NEWS_API_KEY`, `WEATHER_API_KEY`, `EMAIL_SENDER_PASSWORD`) are loaded strictly from environment variables or `.env`.

---

## 🚀 Setup & Execution

### Tested Python Version
- **Python 3.11.9+** (Windows, Linux, macOS)

### 1. Installation
Navigate to the Task 1 directory and install dependencies:
```bash
cd D:\College\Resume\VW\OASIS\OIBSIP\Python-Task1-VoiceAssistant
pip install -r requirements.txt
```

### 2. Configuration (Optional)
Create an optional `.env` file in the project folder to configure external credentials:
```env
VOICE_INPUT_MODE=text             # "text" for console input, "voice" for microphone
NEWS_CACHE_TTL_SECONDS=300        # In-memory news cache duration in seconds
EMAIL_SMTP_SERVER=smtp.gmail.com  # Optional: SMTP host for real emails
EMAIL_SMTP_PORT=587
EMAIL_SENDER_ADDRESS=user@gmail.com
EMAIL_SENDER_PASSWORD=your_app_password
```

### 3. Running the Assistant

#### Text Fallback Mode (Recommended for testing without microphone hardware):
```bash
python -m src.main --mode text
```

#### Voice Mode (Requires working microphone and speakers):
```bash
python -m src.main --mode voice
```

---

## 💬 Example Utterances

- **Greeting**: `"hello assistant"`, `"who are you"`
- **Date & Time**: `"what time is it"`, `"what is today's date"`
- **News**: `"news in technology"`, `"what are the latest headlines"`
- **Weather**: `"what is the weather in London"`, `"weather in Tokyo"`
- **Search**: `"search for quantum computing"`, `"who is Alan Turing"`
- **Reminders**: `"remind me in 10 seconds to stretch"`, `"list reminders"`
- **Email Draft**: `"draft email to alex@example.com subject Project Review body The drafts are ready"`
- **Email Confirm**: `"confirm draft <DRAFT_ID>"`
- **Exit**: `"exit"`, `"quit"`, `"goodbye"`

---

## 🧪 Automated Testing & Type Checking

### Running Pytest
```bash
pytest -v
```

### Running Static Type Checking (mypy)
```bash
mypy src
```

---

## 🎥 Demo Video Talking Points

1. **Architecture Overview**: Highlight the decoupled architecture separating audio capture, background TTS queuing, and intent dispatching.
2. **Non-blocking Concurrency**: Demonstrate queuing multiple commands and speech alerts simultaneously without thread deadlocks or blocked I/O.
3. **Live External Integrations**: Showcase real-time RSS feed parsing with in-memory TTL caching and live weather geocoding.
4. **Security & Human-in-the-Loop**: Walk through the two-stage email draft preview and explicit confirmation command, explaining why voice assistants must never send emails automatically.
5. **Hardware Resilience**: Explain how the text fallback mode ensures complete testability in headless CI/CD environments.
