"""
open_meteo.py - Real-Time Open-Meteo Weather API Integration.
Fetches real current atmospheric telemetry and 7-day forecast.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from typing import List, Optional
from .base import BaseWeatherClient
from ..models.schemas import Location, CurrentWeather, DailyForecastItem, HourlyForecastItem, WeatherReport

# Standard WMO Weather Interpretation Codes
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

COMPASS_POINTS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
]


def degrees_to_compass(degrees: float) -> str:
    """Converts wind degree (0-360) into 16-point cardinal compass direction."""
    normalized = (degrees % 360 + 360) % 360
    index = int((normalized + 11.25) / 22.5) % 16
    return COMPASS_POINTS[index]


def format_iso_time(iso_str: Optional[str]) -> Optional[str]:
    """Formats ISO datetime string (e.g. 2026-09-18T06:04) to friendly time (e.g. 06:04 AM)."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%I:%M %p")
    except Exception:
        # Fallback to substring if fromisoformat fails
        if "T" in iso_str:
            return iso_str.split("T")[1]
        return iso_str


class OpenMeteoClient(BaseWeatherClient):
    """
    Production-ready client for Open-Meteo Weather API.
    """
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _fetch_api_data(self, latitude: float, longitude: float, days: int = 7) -> dict:
        """Internal helper to query Open-Meteo."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m,uv_index",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,sunrise,sunset,uv_index_max",
            "hourly": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation_probability,precipitation,rain,weather_code,wind_speed_10m",
            "timezone": "auto",
            "forecast_days": max(1, min(days, 14))
        }
        resp = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Open-Meteo API returned HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def get_weather_report(self, location: Location) -> WeatherReport:
        data = self._fetch_api_data(location.latitude, location.longitude, days=7)
        current = self._parse_current(data.get("current", {}), data.get("daily", {}))
        forecast = self._parse_forecast(data.get("daily", {}))
        hourly = self._parse_hourly(data.get("hourly", {}))
        return WeatherReport(
            location=location,
            current=current,
            forecast=forecast,
            hourly=hourly,
            source="Open-Meteo"
        )

    def get_current_weather(self, latitude: float, longitude: float) -> CurrentWeather:
        data = self._fetch_api_data(latitude, longitude, days=1)
        return self._parse_current(data.get("current", {}), data.get("daily", {}))

    def get_forecast(self, latitude: float, longitude: float, days: int = 7) -> List[DailyForecastItem]:
        data = self._fetch_api_data(latitude, longitude, days=days)
        return self._parse_forecast(data.get("daily", {}))

    def _parse_current(self, current_data: dict, daily_data: dict) -> CurrentWeather:
        weather_code = current_data.get("weather_code", 0)
        condition = WMO_WEATHER_CODES.get(weather_code, "Partly cloudy")
        temp = float(current_data.get("temperature_2m", 0.0))
        feels_like = float(current_data.get("apparent_temperature", temp))
        humidity = int(current_data.get("relative_humidity_2m", 0))
        wind_speed = float(current_data.get("wind_speed_10m", 0.0))
        wind_dir = int(current_data.get("wind_direction_10m", 0))
        wind_compass = degrees_to_compass(wind_dir)
        precipitation = float(current_data.get("precipitation", 0.0))
        rain = float(current_data.get("rain", 0.0))
        is_day = bool(current_data.get("is_day", 1))
        uv_value = current_data.get("uv_index")
        if uv_value is None:
            daily_uv = daily_data.get("uv_index_max", [])
            uv_value = daily_uv[0] if daily_uv else None
        uv_index = round(float(uv_value), 1) if uv_value is not None else None

        # Precipitation probability from today's daily stats
        daily_probs = daily_data.get("precipitation_probability_max", [])
        precip_prob = daily_probs[0] if daily_probs else 0

        # Sunrise and Sunset for today
        sunrises = daily_data.get("sunrise", [])
        sunsets = daily_data.get("sunset", [])
        sunrise_fmt = format_iso_time(sunrises[0]) if sunrises else None
        sunset_fmt = format_iso_time(sunsets[0]) if sunsets else None

        is_raining = (rain > 0) or (precipitation > 0) or ("rain" in condition.lower()) or ("drizzle" in condition.lower()) or ("thunderstorm" in condition.lower())

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return CurrentWeather(
            temperature=round(temp, 1),
            feels_like=round(feels_like, 1),
            condition=condition,
            weather_code=weather_code,
            humidity=humidity,
            wind_speed=round(wind_speed, 1),
            wind_direction=wind_dir,
            wind_direction_compass=wind_compass,
            precipitation=round(precipitation, 2),
            precipitation_probability=precip_prob or 0,
            sunrise=sunrise_fmt,
            sunset=sunset_fmt,
            uv_index=uv_index,
            is_day=is_day,
            is_raining=is_raining,
            updated_at=now_str
        )

    def _parse_forecast(self, daily_data: dict) -> List[DailyForecastItem]:
        times = daily_data.get("time", [])
        max_temps = daily_data.get("temperature_2m_max", [])
        min_temps = daily_data.get("temperature_2m_min", [])
        precip_sums = daily_data.get("precipitation_sum", [])
        precip_probs = daily_data.get("precipitation_probability_max", [])
        codes = daily_data.get("weather_code", [])
        sunrises = daily_data.get("sunrise", [])
        sunsets = daily_data.get("sunset", [])
        uv_indices = daily_data.get("uv_index_max", [])

        forecast_list: List[DailyForecastItem] = []
        count = min(len(times), 7)

        for i in range(count):
            date_str = times[i]
            try:
                dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
                day_str = dt_obj.strftime("%a, %b %d")
            except Exception:
                day_str = date_str

            code = codes[i] if i < len(codes) else 0
            cond = WMO_WEATHER_CODES.get(code, "Clear")
            max_t = round(float(max_temps[i]), 1) if i < len(max_temps) else 0.0
            min_t = round(float(min_temps[i]), 1) if i < len(min_temps) else 0.0
            p_sum = round(float(precip_sums[i]), 2) if i < len(precip_sums) else 0.0
            p_prob = int(precip_probs[i]) if i < len(precip_probs) else 0
            sunrise_i = format_iso_time(sunrises[i]) if i < len(sunrises) else None
            sunset_i = format_iso_time(sunsets[i]) if i < len(sunsets) else None
            uv_i = round(float(uv_indices[i]), 1) if i < len(uv_indices) and uv_indices[i] is not None else None

            forecast_list.append(DailyForecastItem(
                date=date_str,
                day=day_str,
                temp_max=max_t,
                temp_min=min_t,
                condition=cond,
                weather_code=code,
                precipitation_sum=p_sum,
                precipitation_probability_max=p_prob,
                sunrise=sunrise_i,
                sunset=sunset_i,
                uv_index_max=uv_i
            ))

        return forecast_list

    def _parse_hourly(self, hourly_data: dict) -> List[HourlyForecastItem]:
        times = hourly_data.get("time", [])
        temps = hourly_data.get("temperature_2m", [])
        feels = hourly_data.get("apparent_temperature", [])
        probs = hourly_data.get("precipitation_probability", [])
        precips = hourly_data.get("precipitation", [])
        codes = hourly_data.get("weather_code", [])
        winds = hourly_data.get("wind_speed_10m", [])
        humidities = hourly_data.get("relative_humidity_2m", [])

        hourly_list: List[HourlyForecastItem] = []
        for i in range(len(times)):
            t_str = times[i]
            # parse date and hour: format "2026-09-18T18:00"
            date_part = t_str.split("T")[0] if "T" in t_str else t_str
            hour_part = 0
            if "T" in t_str:
                try:
                    hour_part = int(t_str.split("T")[1].split(":")[0])
                except Exception:
                    hour_part = 0

            code_i = codes[i] if i < len(codes) else 0
            cond_i = WMO_WEATHER_CODES.get(code_i, "Partly cloudy")
            temp_i = round(float(temps[i]), 1) if i < len(temps) else 0.0
            feel_i = round(float(feels[i]), 1) if i < len(feels) else temp_i
            prob_i = int(probs[i]) if i < len(probs) and probs[i] is not None else 0
            precip_i = round(float(precips[i]), 2) if i < len(precips) and precips[i] is not None else 0.0
            wind_i = round(float(winds[i]), 1) if i < len(winds) and winds[i] is not None else 0.0
            hum_i = int(humidities[i]) if i < len(humidities) and humidities[i] is not None else 0

            hourly_list.append(HourlyForecastItem(
                time=t_str,
                date=date_part,
                hour=hour_part,
                temperature=temp_i,
                feels_like=feel_i,
                precipitation_probability=prob_i,
                precipitation=precip_i,
                weather_code=code_i,
                condition=cond_i,
                wind_speed=wind_i,
                humidity=hum_i
            ))

        return hourly_list

