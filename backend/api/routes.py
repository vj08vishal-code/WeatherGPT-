"""
routes.py - FastAPI REST Endpoints for WeatherGPT.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from ..models.schemas import Location, WeatherReport, DailyForecastItem, ChatRequest, ChatResponse
from ..services.location_service import LocationService
from ..services.chat_service import ChatService
from ..weather.open_meteo import OpenMeteoClient

router = APIRouter(prefix="/api", tags=["WeatherGPT"])

weather_client = OpenMeteoClient()
chat_service = ChatService(weather_client=weather_client)


@router.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "WeatherGPT",
        "phase": 1,
        "provider": "Open-Meteo"
    }


@router.get("/suggested-locations", response_model=List[Location])
def get_suggested_locations():
    """
    Returns initial required locations:
    Chennai, Kanchipuram, Bengaluru, Delhi, Mumbai, Kolkata, Hyderabad.
    """
    return LocationService.get_suggested_locations()


@router.get("/geocode", response_model=List[Location])
def geocode_endpoint(
    query: Optional[str] = Query(None, description="City name or query text"),
    q: Optional[str] = Query(None, description="Alternative alias for query"),
    limit: int = Query(5, ge=1, le=10, description="Max results")
):
    """
    Geocodes city name into latitude/longitude using Open-Meteo Geocoding.
    """
    search_term = query or q
    if not search_term or not search_term.strip():
        return []
    
    results = LocationService.search_locations(search_term.strip(), limit=limit)
    return results


@router.get("/weather", response_model=WeatherReport)
def get_weather_endpoint(
    city: Optional[str] = Query(None, description="City name to fetch weather for"),
    latitude: Optional[float] = Query(None, description="Latitude"),
    longitude: Optional[float] = Query(None, description="Longitude"),
    name: Optional[str] = Query(None, description="Location display label")
):
    """
    Fetches real-time weather and 7-day forecast for the specified location or coordinates.
    """
    target_loc: Optional[Location] = None

    if city and city.strip():
        target_loc = LocationService.resolve_location(city.strip())
        if not target_loc:
            raise HTTPException(status_code=404, detail=f"Location '{city}' could not be resolved.")
    elif latitude is not None and longitude is not None:
        target_loc = Location(
            name=name or "Custom Location",
            country="",
            latitude=latitude,
            longitude=longitude,
            display_name=name or f"{latitude:.2f}, {longitude:.2f}"
        )
    else:
        # Default to Chennai
        target_loc = LocationService.get_default_location()

    try:
        report = weather_client.get_weather_report(target_loc)
        return report
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch weather from provider: {str(e)}")


@router.get("/forecast", response_model=List[DailyForecastItem])
def get_forecast_endpoint(
    city: Optional[str] = Query(None, description="City name"),
    latitude: Optional[float] = Query(None, description="Latitude"),
    longitude: Optional[float] = Query(None, description="Longitude"),
    days: int = Query(7, ge=1, le=14, description="Forecast days")
):
    """
    Retrieves multi-day daily forecast for specified location.
    """
    lat = latitude
    lon = longitude

    if city and city.strip():
        loc = LocationService.resolve_location(city.strip())
        if not loc:
            raise HTTPException(status_code=404, detail=f"City '{city}' not found.")
        lat = loc.latitude
        lon = loc.longitude

    if lat is None or lon is None:
        default_loc = LocationService.get_default_location()
        lat = default_loc.latitude
        lon = default_loc.longitude

    try:
        forecast = weather_client.get_forecast(latitude=lat, longitude=lon, days=days)
        return forecast
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch forecast: {str(e)}")


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Main conversational endpoint.
    Accepts user message and location context, returns structured response with real data.
    """
    return chat_service.process_message(request)

@router.get("/reverse-geocode", response_model=Optional[Location])
def reverse_geocode_endpoint(
    latitude: float = Query(..., description="GPS latitude"),
    longitude: float = Query(..., description="GPS longitude"),
):
    """Resolves browser GPS coordinates to a city/locality name."""
    return LocationService.reverse_geocode(latitude, longitude)

