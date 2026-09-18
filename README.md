# 🌤️ WeatherGPT - Atmospheric Intelligence Web MVP (Phase 2)

A production-quality conversational weather web application built for the **Smart India Hackathon (SIH)** WeatherGPT problem statement.

WeatherGPT delivers real-time atmospheric telemetry and 7-day weather forecasts through a modern ChatGPT-inspired user interface. It is powered strictly by real-time data from **Open-Meteo**, guaranteeing **zero synthetic data or hallucinated metrics**.

---

## 🏗️ Architecture & Technology Stack

```text
WeatherGPT/
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py            # REST endpoints (/api/geocode, /api/weather, /api/forecast, /api/chat)
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # Pydantic schemas (Location, CurrentWeather, DailyForecastItem, ChatRequest/Response)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── location_service.py   # Geocoding & coordinate resolution (Predefined hubs + Open-Meteo)
│   │   └── chat_service.py      # Rules-based conversational weather query processor (Phase 1 MVP)
│   ├── weather/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseWeatherClient abstract interface (pluggable provider layer)
│   │   └── open_meteo.py        # OpenMeteoClient with persistent session & retry pooling
│   ├── config.py                # Server configuration and environment variable loader
│   └── main.py                  # FastAPI application entrypoint and static file server
├── frontend/
│   ├── index.html               # ChatGPT-style semantic HTML layout with dark theme
│   ├── style.css                # Polished modern dark CSS (responsive, zero browser defaults)
│   └── app.js                   # Modular vanilla ES6 JS (State, ApiClient, Weather Cards, Location)
├── requirements.txt             # Python production dependencies
└── README.md                    # Project documentation
```

### Key Technical Pillars:
- **Backend**: Python 3.11+ with **FastAPI** and **Uvicorn**
- **Frontend**: Vanilla **HTML5 + Modern CSS + JavaScript (ES6)**
- **Weather Data**: **Open-Meteo API** (Current Atmospheric Telemetry + 7-Day Daily Forecast)
- **Geocoding**: Open-Meteo Geocoding API + Instant resolution for core Indian hubs

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.10+ installed
- PowerShell or Terminal

### 2. Setup Virtual Environment & Install Dependencies
```powershell
# Navigate into the project folder
cd "C:\Users\Admin\OneDrive\Desktop\WeatherGPT"

# Activate the existing virtual environment (or create one with: python -m venv venv)
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 3. Run the Application
```powershell
# Start the FastAPI server
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Open in Browser
Visit:
👉 **http://127.0.0.1:8000**

---

## 📡 REST API Endpoints

| Method | Endpoint | Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | None | Service health status and provider verification |
| `GET` | `/api/suggested-locations` | None | Returns 7 core hubs (Chennai, Kanchipuram, Bengaluru, Delhi, Mumbai, Kolkata, Hyderabad) |
| `GET` | `/api/geocode` | `query` (string), `limit` (int) | Geocodes any city worldwide into latitude/longitude |
| `GET` | `/api/weather` | `city` or `latitude`, `longitude` | Returns live current conditions & 7-day forecast |
| `GET` | `/api/forecast` | `city` or `latitude`, `longitude`, `days` | Returns 7-day daily forecast breakdown |
| `POST` | `/api/chat` | `{"message": str, "location": {...}}` | Conversational atmospheric intelligence query |

---

## 🧪 Verification & Automated Tests

A dedicated end-to-end integration test suite is included in the project:
```powershell
.\venv\Scripts\python tests/test_live.py
```
This tests:
1. Server health and Open-Meteo connectivity
2. Predefined hubs (Chennai, Kanchipuram, Bengaluru, Delhi, Mumbai, Kolkata, Hyderabad)
3. Real-time Chennai telemetry (temperature, feels-like, wind vector, humidity, sunrise, sunset, 7-day forecast)
4. Geocoding resolution across global cities
5. Conversational natural language queries
6. Error handling and unknown city recovery
7. Static file serving

---

## 🧭 Current Prototype Status

The prototype is intentionally modular. The current build includes the Phase 1 data layer plus the Phase 2 conversational query pipeline and ChatGPT-style interface:

- **Pluggable Weather Client (`backend/weather/base.py`)**: Future numerical weather models (GFS, WRF, IMD radar, and satellite imagery) can implement `BaseWeatherClient` alongside `OpenMeteoClient`.
- **Conversational Intelligence Layer (`backend/services/chat_service.py`)**: Deterministic intent parsing and multi-turn context keep weather facts grounded in live provider data; an LLM can be added later as an optional explanation layer.
- **Multilingual & Localization**: Architecture is prepared to receive language parameters for English and Tamil localization.
