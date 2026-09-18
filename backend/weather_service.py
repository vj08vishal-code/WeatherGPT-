"""
weather_service.py - Real-Time Weather Service powered by Open-Meteo.

This module retrieves real-time weather data (temperature, condition, humidity,
wind speed, rainfall/precipitation) and a 5-day forecast using the Open-Meteo API.

Pre-configured with coordinates for initial core locations:
- Chennai
- Kanchipuram
- Bengaluru
- Delhi
- Mumbai
- Kolkata
- Hyderabad
Plus dynamic Open-Meteo Geocoding for any other requested location.
"""

import requests
from datetime import datetime
from typing import Dict, Any, List

# Standard WMO Weather Interpretation Codes to human-readable condition descriptions
WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

# Pre-mapped coordinates for initial required locations (ensures zero latency and no geocoding rate limits)
SUPPORTED_LOCATIONS: Dict[str, Dict[str, Any]] = {
    "chennai": {
        "name": "Chennai",
        "country": "IN",
        "latitude": 13.0827,
        "longitude": 80.2707
    },
    "kanchipuram": {
        "name": "Kanchipuram",
        "country": "IN",
        "latitude": 12.8342,
        "longitude": 79.7036
    },
    "bengaluru": {
        "name": "Bengaluru",
        "country": "IN",
        "latitude": 12.9716,
        "longitude": 77.5946
    },
    "bangalore": {
        "name": "Bengaluru",
        "country": "IN",
        "latitude": 12.9716,
        "longitude": 77.5946
    },
    "delhi": {
        "name": "Delhi",
        "country": "IN",
        "latitude": 28.6139,
        "longitude": 77.2090
    },
    "new delhi": {
        "name": "Delhi",
        "country": "IN",
        "latitude": 28.6139,
        "longitude": 77.2090
    },
    "mumbai": {
        "name": "Mumbai",
        "country": "IN",
        "latitude": 19.0760,
        "longitude": 72.8777
    },
    "bombay": {
        "name": "Mumbai",
        "country": "IN",
        "latitude": 19.0760,
        "longitude": 72.8777
    },
    "kolkata": {
        "name": "Kolkata",
        "country": "IN",
        "latitude": 22.5726,
        "longitude": 88.3639
    },
    "calcutta": {
        "name": "Kolkata",
        "country": "IN",
        "latitude": 22.5726,
        "longitude": 88.3639
    },
    "hyderabad": {
        "name": "Hyderabad",
        "country": "IN",
        "latitude": 17.3850,
        "longitude": 78.4867
    }
}


def get_weather(city_name: str) -> Dict[str, Any]:
    """
    Retrieves real-time weather conditions and a 5-day forecast for the given city
    using the Open-Meteo API.
    
    Returns structured JSON with:
    - Current temperature (°C)
    - Weather condition / description
    - Humidity (%)
    - Wind speed (km/h)
    - Rainfall/precipitation (mm)
    - 5-day forecast
    """
    clean_city = city_name.strip()
    if not clean_city:
        return {
            "success": False,
            "error": "City name cannot be empty."
        }

    normalized_key = clean_city.lower()

    # Step 1: Check pre-mapped coordinates for instant lookup
    if normalized_key in SUPPORTED_LOCATIONS:
        loc_info = SUPPORTED_LOCATIONS[normalized_key]
        return _fetch_forecast_by_coords(
            latitude=loc_info["latitude"],
            longitude=loc_info["longitude"],
            city_name=loc_info["name"],
            country_code=loc_info["country"]
        )

    # Step 2: Fallback to Open-Meteo Geocoding API for any other city
    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_params = {"name": clean_city, "count": 1, "language": "en", "format": "json"}
        geo_resp = requests.get(geo_url, params=geo_params, timeout=10)
        
        if geo_resp.status_code != 200:
            return {
                "success": False,
                "error": f"Open-Meteo geocoding error (status {geo_resp.status_code})."
            }
            
        geo_data = geo_resp.json()
        results = geo_data.get("results")
        if not results:
            return {
                "success": False,
                "error": f"Location '{clean_city}' was not found. Please check spelling."
            }

        first_match = results[0]
        return _fetch_forecast_by_coords(
            latitude=first_match["latitude"],
            longitude=first_match["longitude"],
            city_name=first_match.get("name", clean_city),
            country_code=first_match.get("country_code", "")
        )

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Weather service is currently unavailable: {str(e)}"
        }


def _fetch_forecast_by_coords(latitude: float, longitude: float, city_name: str, country_code: str) -> Dict[str, Any]:
    """
    Fetches real-time conditions and 5-day daily forecast from Open-Meteo.
    """
    forecast_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
        "timezone": "auto"
    }

    try:
        response = requests.get(forecast_url, params=params, timeout=10)
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Open-Meteo forecast API error (status {response.status_code})."
            }

        data = response.json()
        current = data.get("current", {})
        daily = data.get("daily", {})

        # Current weather metrics
        temp = current.get("temperature_2m", 0.0)
        feels_like = current.get("apparent_temperature", temp)
        humidity = current.get("relative_humidity_2m", 0)
        wind_speed = current.get("wind_speed_10m", 0.0)
        precipitation = current.get("precipitation", 0.0)
        rain = current.get("rain", 0.0)
        weather_code = current.get("weather_code", 0)

        condition_desc = WMO_WEATHER_CODES.get(weather_code, "Partly cloudy")
        is_raining = (rain > 0) or (precipitation > 0) or ("rain" in condition_desc.lower()) or ("drizzle" in condition_desc.lower())

        # 5-Day Forecast parsing
        times = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precip_sums = daily.get("precipitation_sum", [])
        precip_probs = daily.get("precipitation_probability_max", [])
        codes = daily.get("weather_code", [])

        forecast_list: List[Dict[str, Any]] = []
        days_to_include = min(5, len(times))  # Core requirement: 5-day forecast

        for i in range(days_to_include):
            date_str = times[i]
            try:
                dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
                day_str = dt_obj.strftime("%a, %b %d")
            except Exception:
                day_str = date_str

            code_i = codes[i] if i < len(codes) else 0
            cond_i = WMO_WEATHER_CODES.get(code_i, "Partly cloudy")

            forecast_list.append({
                "date": date_str,
                "day": day_str,
                "temp_max": round(max_temps[i], 1) if i < len(max_temps) else None,
                "temp_min": round(min_temps[i], 1) if i < len(min_temps) else None,
                "condition": cond_i,
                "description": cond_i,
                "precipitation": round(precip_sums[i], 1) if i < len(precip_sums) else 0.0,
                "precipitation_sum": round(precip_sums[i], 1) if i < len(precip_sums) else 0.0,
                "rain_prob": precip_probs[i] if i < len(precip_probs) else 0
            })

        return {
            "success": True,
            "city": city_name,
            "country": country_code,
            "temperature": round(temp, 1),
            "feels_like": round(feels_like, 1),
            "condition": condition_desc,
            "description": condition_desc,
            "humidity": humidity,
            "wind_speed": round(wind_speed, 1),
            "precipitation": round(precipitation, 2),
            "rainfall": round(precipitation, 2),
            "rain_amount": round(rain, 2),
            "is_raining": is_raining,
            "forecast": forecast_list,
            "alerts": [],
            "source": "Open-Meteo"
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Weather service is currently unavailable: {str(e)}"
        }
