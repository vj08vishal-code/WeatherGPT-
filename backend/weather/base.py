"""
base.py - Abstract base client for weather data providers.
Allows future weather sources (GFS, WRF, IMD, etc.) to be plugged in seamlessly.
"""

from abc import ABC, abstractmethod
from typing import List
from ..models.schemas import Location, CurrentWeather, DailyForecastItem, WeatherReport


class BaseWeatherClient(ABC):
    """
    Abstract interface for retrieving weather and forecast information.
    """

    @abstractmethod
    def get_weather_report(self, location: Location) -> WeatherReport:
        """
        Retrieves a full weather report (current + 7-day forecast) for a given location.
        """
        pass

    @abstractmethod
    def get_current_weather(self, latitude: float, longitude: float) -> CurrentWeather:
        """
        Retrieves current real-time atmospheric metrics.
        """
        pass

    @abstractmethod
    def get_forecast(self, latitude: float, longitude: float, days: int = 7) -> List[DailyForecastItem]:
        """
        Retrieves multi-day daily weather forecast.
        """
        pass
