"""
weather_service.py - Real Weather Orchestration & Aggregation Service (Phase 2).
Intermediary between Query Understanding and Open-Meteo Client.
Extracts targeted metrics, aggregates hourly part-of-day stats, and evaluates suitability.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from ..models.schemas import Location, WeatherReport, HourlyForecastItem, DailyForecastItem
from ..weather.open_meteo import OpenMeteoClient

# Mapping time-of-day labels to hourly ranges
PART_OF_DAY_HOURS = {
    "morning": range(6, 12),      # 06:00 to 11:00
    "afternoon": range(12, 18),   # 12:00 to 17:00
    "evening": range(18, 22),     # 18:00 to 21:00
    "night": [22, 23, 0, 1, 2, 3, 4, 5]
}


class WeatherService:
    """Service to query Open-Meteo and compute targeted atmospheric aggregates."""

    def __init__(self, weather_client: Optional[OpenMeteoClient] = None):
        self.client = weather_client or OpenMeteoClient()

    def get_weather_report(self, location: Location) -> WeatherReport:
        """Fetches full real-time telemetry (current, daily, hourly)."""
        return self.client.get_weather_report(location)

    def extract_part_of_day_summary(
        self,
        report: WeatherReport,
        target_date: str = "today",
        time_of_day: str = "evening"
    ) -> Optional[Dict[str, Any]]:
        """
        Filters hourly data for the requested day and time-of-day window (e.g. tomorrow evening),
        aggregating real temperature, rain probability, condition, and wind.
        """
        hourly_items = report.hourly
        if not hourly_items:
            return None

        # Determine target date string (YYYY-MM-DD)
        target_date_str = None
        if target_date == "tomorrow" and len(report.forecast) > 1:
            target_date_str = report.forecast[1].date
            day_label = report.forecast[1].day
        elif target_date == "day_after_tomorrow" and len(report.forecast) > 2:
            target_date_str = report.forecast[2].date
            day_label = report.forecast[2].day
        else:
            target_date_str = report.forecast[0].date if report.forecast else None
            day_label = "Today"

        if not target_date_str:
            return None

        # Filter hours in matching window
        allowed_hours = PART_OF_DAY_HOURS.get(time_of_day.lower(), range(18, 22))
        matching_hours = [
            h for h in hourly_items
            if h.date == target_date_str and h.hour in allowed_hours
        ]

        if not matching_hours:
            return None

        temps = [h.temperature for h in matching_hours]
        feels = [h.feels_like for h in matching_hours]
        probs = [h.precipitation_probability for h in matching_hours]
        precips = [h.precipitation for h in matching_hours]
        winds = [h.wind_speed for h in matching_hours]
        conditions = [h.condition for h in matching_hours]

        avg_temp = round(sum(temps) / len(temps), 1)
        avg_feels = round(sum(feels) / len(feels), 1)
        max_prob = max(probs) if probs else 0
        sum_precip = round(sum(precips), 2)
        avg_wind = round(sum(winds) / len(winds), 1)

        # Most frequent condition
        predominant_cond = max(set(conditions), key=conditions.count) if conditions else "Partly cloudy"

        return {
            "target_date": target_date,
            "day_label": day_label,
            "time_of_day": time_of_day,
            "temperature": avg_temp,
            "feels_like": avg_feels,
            "precipitation_probability": max_prob,
            "precipitation_sum": sum_precip,
            "condition": predominant_cond,
            "wind_speed": avg_wind,
            "hours_sampled": len(matching_hours)
        }

    def evaluate_outdoor_suitability(self, report: WeatherReport) -> Dict[str, Any]:
        """
        Evaluates current and upcoming atmospheric metrics to give an objective outdoor rating.
        """
        cur = report.current
        temp = cur.temperature
        precip_prob = cur.precipitation_probability
        wind = cur.wind_speed
        is_raining = cur.is_raining
        condition = cur.condition

        # Check factors
        reasons = []
        is_suitable = True

        if is_raining or cur.precipitation > 0:
            reasons.append("rain is currently occurring")
            is_suitable = False
        elif precip_prob >= 60:
            reasons.append(f"high chance of rain ({precip_prob}%)")
            is_suitable = False
        elif precip_prob >= 35:
            reasons.append(f"moderate rain chance ({precip_prob}%)")

        if temp > 36:
            reasons.append(f"high temperature of {temp}°C (feels like {cur.feels_like}°C)")
            is_suitable = False
        elif temp < 10:
            reasons.append(f"chilly temperature of {temp}°C")

        if wind > 30:
            reasons.append(f"strong winds reaching {wind} km/h")
            is_suitable = False

        if "thunderstorm" in condition.lower():
            reasons.append("thunderstorm activity")
            is_suitable = False

        if not reasons:
            rating = "Good"
            summary = f"Conditions in {report.location.name} are pleasant for outdoor activities ({temp}°C, {condition})."
        elif is_suitable:
            rating = "Moderate"
            summary = f"Generally fine for outdoors in {report.location.name} ({temp}°C), but note that {', and '.join(reasons)}."
        else:
            rating = "Unfavorable"
            summary = f"Not ideal for extended outdoor activities in {report.location.name} right now due to {', and '.join(reasons)}."

        return {
            "rating": rating,
            "summary": summary,
            "is_suitable": is_suitable,
            "temperature": temp,
            "feels_like": cur.feels_like,
            "condition": condition,
            "rain_probability": precip_prob,
            "wind_speed": wind
        }
