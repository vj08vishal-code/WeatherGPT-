"""
verification_service.py - Cross-provider weather verification and confidence.
Uses Open-Meteo as the primary source and OpenWeather as an independent
secondary provider when OPENWEATHER_API_KEY is configured.

Important: confidence is NOT historical forecast accuracy. It is a
source-agreement signal for the current request.
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import requests

from ..config import PRIMARY_PROVIDER
from ..models.schemas import Location, WeatherReport


class VerificationService:
    OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
    OPENWEATHER_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
    MET_FORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()

    @staticmethod
    def _category(condition: str) -> str:
        c = (condition or "").lower()
        if any(x in c for x in ("thunderstorm", "lightning", "hail", "storm")):
            return "storm"
        if any(x in c for x in ("rain", "drizzle", "shower")):
            return "rain"
        if any(x in c for x in ("snow", "sleet", "ice")):
            return "snow"
        if any(x in c for x in ("fog", "mist", "haze")):
            return "reduced_visibility"
        if any(x in c for x in ("clear", "sun")):
            return "clear"
        if any(x in c for x in ("cloud", "overcast")):
            return "cloud"
        return "other"

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _fetch_openweather_forecast(self, location: Location) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        params = {
            "lat": location.latitude,
            "lon": location.longitude,
            "appid": self.api_key,
            "units": "metric",
        }
        response = requests.get(self.OPENWEATHER_FORECAST_URL, params=params, timeout=self.timeout)
        if response.status_code != 200:
            return None
        return response.json()

    def _fetch_openweather_current(self, location: Location) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        params = {
            "lat": location.latitude,
            "lon": location.longitude,
            "appid": self.api_key,
            "units": "metric",
        }
        response = requests.get(self.OPENWEATHER_CURRENT_URL, params=params, timeout=self.timeout)
        if response.status_code != 200:
            return None
        return response.json()

    def _fetch_met_forecast(self, location: Location) -> Optional[Dict[str, Any]]:
        """Secondary global forecast fallback; no API key required."""
        params = {
            "lat": round(location.latitude, 4),
            "lon": round(location.longitude, 4),
        }
        headers = {
            "User-Agent": "WeatherGPT-SIH/1.0 (weather intelligence prototype)"
        }
        try:
            response = requests.get(
                self.MET_FORECAST_URL,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            if response.status_code != 200:
                return None
            return response.json()
        except requests.RequestException:
            return None

    @staticmethod
    def _met_symbol_category(symbol_code: str) -> str:
        code = (symbol_code or "").lower()
        if "thunder" in code:
            return "storm"
        if any(x in code for x in ("rain", "shower", "sleet")):
            return "rain"
        if "snow" in code:
            return "snow"
        if any(x in code for x in ("fog", "mist")):
            return "reduced_visibility"
        if "cloud" in code:
            return "cloud"
        if "clear" in code or "fair" in code:
            return "clear"
        return "other"

    def _met_forecast_summary(
        self, data: Dict[str, Any], target_date: str
    ) -> Optional[Dict[str, Any]]:
        timeseries = ((data.get("properties") or {}).get("timeseries") or [])
        rows = []

        for item in timeseries:
            timestamp = item.get("time", "")
            if not timestamp.startswith(target_date):
                continue

            details = ((item.get("data") or {}).get("instant") or {}).get("details") or {}
            temp = self._safe_float(details.get("air_temperature"))

            period = (item.get("data") or {}).get("next_6_hours") or (item.get("data") or {}).get("next_1_hours") or {}
            pdetails = period.get("details") or {}
            psummary = period.get("summary") or {}

            pop = self._safe_float(pdetails.get("probability_of_precipitation"))
            amount = self._safe_float(pdetails.get("precipitation_amount"))
            symbol = psummary.get("symbol_code") or ""

            rows.append({
                "temp": temp,
                "pop": pop,
                "amount": amount,
                "category": self._met_symbol_category(symbol),
                "symbol": symbol,
            })

        if not rows:
            return None

        temps = [r["temp"] for r in rows if r["temp"] is not None]
        pops = [r["pop"] for r in rows if r["pop"] is not None]
        amounts = [r["amount"] for r in rows if r["amount"] is not None]
        categories = [r["category"] for r in rows]
        category = max(set(categories), key=categories.count) if categories else "other"

        return {
            "provider": "MET Norway",
            "temp_max": round(max(temps), 1) if temps else None,
            "temp_min": round(min(temps), 1) if temps else None,
            "rain_probability": round(max(pops)) if pops else None,
            "condition": category,
            "precipitation_3h_max": round(max(amounts), 2) if amounts else 0.0,
            "symbol": max((r["symbol"] for r in rows), key=lambda x: x.count("rain") + x.count("thunder")) if rows else "",
        }

    def _current_met_summary(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        timeseries = ((data.get("properties") or {}).get("timeseries") or [])
        if not timeseries:
            return None
        item = timeseries[0]
        details = ((item.get("data") or {}).get("instant") or {}).get("details") or {}
        period = (item.get("data") or {}).get("next_1_hours") or {}
        symbol = ((period.get("summary") or {}).get("symbol_code")) or ""
        return {
            "provider": "MET Norway",
            "temperature": self._safe_float(details.get("air_temperature")),
            "condition": self._met_symbol_category(symbol),
            "rain_now": "rain" in symbol or "shower" in symbol or "thunder" in symbol,
        }

    def _tomorrow_openweather_summary(
        self, data: Dict[str, Any], target_date: str
    ) -> Optional[Dict[str, Any]]:
        entries = data.get("list") or []
        city = data.get("city") or {}
        timezone_offset = int(city.get("timezone", 0) or 0)
        target_entries = []

        for item in entries:
            dt = item.get("dt")
            if dt is None:
                continue
            local_dt = datetime.fromtimestamp(int(dt), tz=timezone.utc) + timedelta(seconds=timezone_offset)
            if local_dt.date().isoformat() == target_date:
                target_entries.append(item)

        if not target_entries:
            return None

        temps = []
        pops = []
        conditions = []
        rain_amounts = []

        for item in target_entries:
            main = item.get("main") or {}
            temp = self._safe_float(main.get("temp"))
            if temp is not None:
                temps.append(temp)

            pop = self._safe_float(item.get("pop"))
            if pop is not None:
                pops.append(pop * 100.0)

            weather = (item.get("weather") or [{}])[0]
            conditions.append(weather.get("description") or weather.get("main") or "Unknown")

            rain = item.get("rain") or {}
            amount = self._safe_float(rain.get("3h"))
            if amount is not None:
                rain_amounts.append(amount)

        return {
            "provider": "OpenWeather",
            "temp_max": round(max(temps), 1) if temps else None,
            "temp_min": round(min(temps), 1) if temps else None,
            "rain_probability": round(max(pops)) if pops else None,
            "condition": max(set(conditions), key=conditions.count) if conditions else "Unknown",
            "precipitation_3h_max": round(max(rain_amounts), 2) if rain_amounts else 0.0,
        }

    def _current_openweather_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        main = data.get("main") or {}
        weather = (data.get("weather") or [{}])[0]
        rain = data.get("rain") or {}
        return {
            "provider": "OpenWeather",
            "temperature": self._safe_float(main.get("temp")),
            "condition": weather.get("description") or weather.get("main") or "Unknown",
            "rain_now": bool(rain),
        }

    def _confidence(
        self,
        primary: Dict[str, Any],
        secondary: Optional[Dict[str, Any]],
        mode: str,
    ) -> Dict[str, Any]:
        if not secondary:
            return {
                "level": "UNVERIFIED",
                "agreement_count": 0,
                "agreement_total": 0,
                "summary": "Only the primary provider was available, so a cross-provider confidence check could not be completed.",
                "reasons": ["Secondary provider is unavailable. OpenWeather can be used when an API key is configured; MET Norway is the no-key fallback."],
            }

        reasons: List[str] = []
        agreements = 0
        total = 0

        if mode == "forecast":
            p_prob = primary.get("rain_probability")
            s_prob = secondary.get("rain_probability")
            if p_prob is not None and s_prob is not None:
                total += 1
                p_rain = p_prob >= 50
                s_rain = s_prob >= 50
                if p_rain == s_rain:
                    agreements += 1
                    reasons.append(f"Both providers agree on the rain/no-rain signal ({p_prob}% vs {round(s_prob)}%).")
                else:
                    reasons.append(f"Providers disagree on the rain/no-rain signal ({p_prob}% vs {round(s_prob)}%).")

            p_max = primary.get("temp_max")
            s_max = secondary.get("temp_max")
            if p_max is not None and s_max is not None:
                total += 1
                diff = abs(p_max - s_max)
                if diff <= 3:
                    agreements += 1
                    reasons.append(f"Forecast high temperatures are close ({p_max}°C vs {s_max}°C).")
                else:
                    reasons.append(f"Forecast high temperatures differ by {round(diff, 1)}°C.")

            p_cat = self._category(primary.get("condition", ""))
            s_cat = self._category(secondary.get("condition", ""))
            total += 1
            if p_cat == s_cat:
                agreements += 1
                reasons.append(f"Both providers describe the same broad weather category ({p_cat}).")
            else:
                reasons.append(f"Weather categories differ ({p_cat} vs {s_cat}).")
        else:
            p_temp = primary.get("temperature")
            s_temp = secondary.get("temperature")
            if p_temp is not None and s_temp is not None:
                total += 1
                diff = abs(p_temp - s_temp)
                if diff <= 3:
                    agreements += 1
                    reasons.append(f"Current temperatures are close ({p_temp}°C vs {round(s_temp, 1)}°C).")
                else:
                    reasons.append(f"Current temperatures differ by {round(diff, 1)}°C.")

            p_cat = self._category(primary.get("condition", ""))
            s_cat = self._category(secondary.get("condition", ""))
            total += 1
            if p_cat == s_cat:
                agreements += 1
                reasons.append(f"Both providers report the same broad current condition ({p_cat}).")
            else:
                reasons.append(f"Current weather categories differ ({p_cat} vs {s_cat}).")

        ratio = agreements / total if total else 0
        if total == 0:
            level = "UNVERIFIED"
        elif ratio >= 0.80:
            level = "HIGH"
        elif ratio >= 0.50:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            "level": level,
            "agreement_count": agreements,
            "agreement_total": total,
            "summary": f"{agreements}/{total} comparison signals agree across the available providers.",
            "reasons": reasons,
        }

    def verify(
        self,
        location: Location,
        report: WeatherReport,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns a UI/API-safe verification object. Never exposes API keys.
        """
        is_forecast = bool(target_date and target_date not in ("today", "now"))
        mode = "forecast" if is_forecast else "current"

        if mode == "forecast":
            target = next((d for d in report.forecast if d.date == target_date), None)
            if target is None:
                # For natural language "tomorrow", callers pass the actual date.
                target = report.forecast[1] if len(report.forecast) > 1 else None

            if not target:
                return {
                    "available": False,
                    "mode": "forecast",
                    "primary_provider": report.source,
                    "secondary_provider": "OpenWeather / MET Norway",
                    "level": "UNVERIFIED",
                    "agreement_count": 0,
                    "agreement_total": 0,
                    "summary": "The requested forecast date is not available for cross-checking.",
                    "reasons": [],
                    "sources": [report.source],
                }

            primary = {
                "rain_probability": target.precipitation_probability_max,
                "temp_max": target.temp_max,
                "temp_min": target.temp_min,
                "condition": target.condition,
            }
            secondary_data = self._fetch_openweather_forecast(location)
            if secondary_data:
                secondary = self._tomorrow_openweather_summary(secondary_data, target.date)
            else:
                met_data = self._fetch_met_forecast(location)
                secondary = self._met_forecast_summary(met_data, target.date) if met_data else None
        else:
            primary = {
                "temperature": report.current.temperature,
                "condition": report.current.condition,
            }
            secondary_data = self._fetch_openweather_current(location)
            if secondary_data:
                secondary = self._current_openweather_summary(secondary_data)
            else:
                met_data = self._fetch_met_forecast(location)
                secondary = self._current_met_summary(met_data) if met_data else None

        confidence = self._confidence(primary, secondary, mode)
        sources = [report.source]
        if secondary:
            sources.append(secondary.get("provider", "OpenWeather"))

        result = {
            "available": bool(secondary),
            "mode": mode,
            "primary_provider": report.source,
            "secondary_provider": secondary.get("provider", "OpenWeather / MET Norway") if secondary else "OpenWeather / MET Norway",
            "sources": sources,
            **confidence,
            "is_historical_accuracy": False,
            "accuracy_note": (
                "This is a source-agreement confidence signal, not a measured forecast accuracy percentage. "
                "True accuracy requires comparing stored forecasts with later observations over many cases."
            ),
        }
        if secondary:
            result["secondary_snapshot"] = secondary
        return result
