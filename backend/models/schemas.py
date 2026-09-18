"""
schemas.py - Pydantic data schemas for WeatherGPT.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Location(BaseModel):
    name: str = Field(..., description="Name of the city or locality")
    country: Optional[str] = Field(default="", description="Country code or country name")
    latitude: float = Field(..., description="Latitude in decimal degrees")
    longitude: float = Field(..., description="Longitude in decimal degrees")
    admin1: Optional[str] = Field(default=None, description="State, province, or primary administrative division")
    display_name: Optional[str] = Field(default=None, description="Formatted location label e.g. Chennai, Tamil Nadu, India")


class CurrentWeather(BaseModel):
    temperature: float = Field(..., description="Current temperature in degrees Celsius")
    feels_like: float = Field(..., description="Apparent temperature in degrees Celsius")
    condition: str = Field(..., description="Human-readable weather condition")
    weather_code: int = Field(..., description="WMO weather code")
    humidity: int = Field(..., description="Relative humidity percentage")
    wind_speed: float = Field(..., description="Wind speed in km/h")
    wind_direction: int = Field(..., description="Wind direction in degrees")
    wind_direction_compass: str = Field(..., description="Cardinal wind direction compass abbreviation (e.g., N, ENE)")
    precipitation: float = Field(default=0.0, description="Current precipitation rate in mm")
    precipitation_probability: int = Field(default=0, description="Precipitation probability percentage")
    sunrise: Optional[str] = Field(default=None, description="Sunrise time string")
    sunset: Optional[str] = Field(default=None, description="Sunset time string")
    uv_index: Optional[float] = Field(default=None, description="Current UV index when available")
    is_day: bool = Field(default=True, description="Whether current time is daylight")
    is_raining: bool = Field(default=False, description="Whether rain is currently occurring")
    updated_at: str = Field(..., description="Timestamp of the weather reading")


class DailyForecastItem(BaseModel):
    date: str = Field(..., description="Date formatted as YYYY-MM-DD")
    day: str = Field(..., description="Formatted day label e.g., Mon, Sep 18")
    temp_max: float = Field(..., description="Maximum temperature in degrees Celsius")
    temp_min: float = Field(..., description="Minimum temperature in degrees Celsius")
    condition: str = Field(..., description="Weather condition description")
    weather_code: int = Field(..., description="WMO weather code")
    precipitation_sum: float = Field(default=0.0, description="Expected precipitation sum in mm")
    precipitation_probability_max: int = Field(default=0, description="Maximum precipitation probability percentage")
    sunrise: Optional[str] = Field(default=None, description="Sunrise time string")
    sunset: Optional[str] = Field(default=None, description="Sunset time string")
    uv_index_max: Optional[float] = Field(default=None, description="Maximum daily UV index")


class HourlyForecastItem(BaseModel):
    time: str = Field(..., description="ISO timestamp string (e.g. 2026-09-18T18:00)")
    date: str = Field(..., description="Date YYYY-MM-DD")
    hour: int = Field(..., description="Hour of day (0-23)")
    temperature: float = Field(..., description="Temperature in degrees Celsius")
    feels_like: float = Field(..., description="Apparent temperature in degrees Celsius")
    precipitation_probability: int = Field(default=0, description="Precipitation probability percentage")
    precipitation: float = Field(default=0.0, description="Precipitation amount in mm")
    weather_code: int = Field(..., description="WMO weather code")
    condition: str = Field(..., description="Condition description")
    wind_speed: float = Field(default=0.0, description="Wind speed in km/h")
    humidity: int = Field(default=0, description="Relative humidity percentage")


class WeatherReport(BaseModel):
    location: Location
    current: CurrentWeather
    forecast: List[DailyForecastItem] = Field(default_factory=list, description="7-day daily forecast")
    hourly: List[HourlyForecastItem] = Field(default_factory=list, description="Hourly forecast items")
    source: str = Field(default="Open-Meteo", description="Data source provider name")


class ParsedQuery(BaseModel):
    intent: str = Field(..., description="Identified user weather intent")
    target_date: Optional[str] = Field(default=None, description="Target date (e.g. 'today', 'tomorrow', day name)")
    time_of_day: Optional[str] = Field(default=None, description="Part of day (e.g. 'morning', 'afternoon', 'evening', 'night')")
    location_name: Optional[str] = Field(default=None, description="Explicit city/location extracted from query")
    is_followup: bool = Field(default=False, description="Whether query relies on conversation context")
    raw_message: str = Field(default="", description="Original query message")
    language: str = Field(default="en", description="Detected response language code")


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's query or message")
    location: Optional[Location] = Field(default=None, description="Current selected location context")
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation tracking")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Conversational text reply")
    weather_data: Optional[WeatherReport] = Field(default=None, description="Associated real weather telemetry")
    location: Optional[Location] = Field(default=None, description="Location corresponding to this answer")
    intent: Optional[str] = Field(default=None, description="Detected query intent")
    card_type: Optional[str] = Field(default=None, description="Type of visual card to render: None (text-only), 'forecast', or 'overview'")
    verification: Optional[Dict[str, Any]] = Field(default=None, description="Cross-provider verification and source-agreement confidence for weather answers")
