"""
location_service.py - Geocoding and Location Resolution Service.
Includes instant support for required initial locations and Open-Meteo geocoding.
"""

import requests
from typing import List, Optional, Dict
from ..models.schemas import Location

# Required initial suggested locations with exact coordinates
SUGGESTED_LOCATIONS: Dict[str, Dict] = {
    "chennai": {
        "name": "Chennai",
        "country": "IN",
        "admin1": "Tamil Nadu",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "display_name": "Chennai, Tamil Nadu, India"
    },
    "kanchipuram": {
        "name": "Kanchipuram",
        "country": "IN",
        "admin1": "Tamil Nadu",
        "latitude": 12.8342,
        "longitude": 79.7036,
        "display_name": "Kanchipuram, Tamil Nadu, India"
    },
    "bengaluru": {
        "name": "Bengaluru",
        "country": "IN",
        "admin1": "Karnataka",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "display_name": "Bengaluru, Karnataka, India"
    },
    "bangalore": {
        "name": "Bengaluru",
        "country": "IN",
        "admin1": "Karnataka",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "display_name": "Bengaluru, Karnataka, India"
    },
    "delhi": {
        "name": "Delhi",
        "country": "IN",
        "admin1": "Delhi",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "display_name": "Delhi, India"
    },
    "new delhi": {
        "name": "Delhi",
        "country": "IN",
        "admin1": "Delhi",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "display_name": "New Delhi, Delhi, India"
    },
    "mumbai": {
        "name": "Mumbai",
        "country": "IN",
        "admin1": "Maharashtra",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "display_name": "Mumbai, Maharashtra, India"
    },
    "bombay": {
        "name": "Mumbai",
        "country": "IN",
        "admin1": "Maharashtra",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "display_name": "Mumbai, Maharashtra, India"
    },
    "kolkata": {
        "name": "Kolkata",
        "country": "IN",
        "admin1": "West Bengal",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "display_name": "Kolkata, West Bengal, India"
    },
    "calcutta": {
        "name": "Kolkata",
        "country": "IN",
        "admin1": "West Bengal",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "display_name": "Kolkata, West Bengal, India"
    },
    "hyderabad": {
        "name": "Hyderabad",
        "country": "IN",
        "admin1": "Telangana",
        "latitude": 17.3850,
        "longitude": 78.4867,
        "display_name": "Hyderabad, Telangana, India"
    }
}

CORE_CITIES_LIST = ["Chennai", "Kanchipuram", "Bengaluru", "Delhi", "Mumbai", "Kolkata", "Hyderabad"]


class LocationService:
    """Service to handle geocoding, coordinates lookup, and suggested locations."""

    GEOCODE_API_URL = "https://geocoding-api.open-meteo.com/v1/search"

    @classmethod
    def get_default_location(cls) -> Location:
        """Returns Chennai as the default initial location."""
        d = SUGGESTED_LOCATIONS["chennai"]
        return Location(
            name=d["name"],
            country=d["country"],
            latitude=d["latitude"],
            longitude=d["longitude"],
            admin1=d["admin1"],
            display_name=d["display_name"]
        )

    @classmethod
    def get_suggested_locations(cls) -> List[Location]:
        """Returns the list of core suggested Indian cities."""
        res = []
        for city_name in CORE_CITIES_LIST:
            d = SUGGESTED_LOCATIONS[city_name.lower()]
            res.append(Location(
                name=d["name"],
                country=d["country"],
                latitude=d["latitude"],
                longitude=d["longitude"],
                admin1=d["admin1"],
                display_name=d["display_name"]
            ))
        return res

    @classmethod
    def resolve_location(cls, query: str) -> Optional[Location]:
        """
        Quickly resolves a query to a single best match Location.
        Checks known locations first, then falls back to Open-Meteo Geocoding.
        """
        results = cls.search_locations(query, limit=1)
        return results[0] if results else None

    @classmethod
    def search_locations(cls, query: str, limit: int = 5) -> List[Location]:
        """
        Searches locations by name using Open-Meteo Geocoding API with local cache optimization.
        """
        clean_q = query.strip()
        if not clean_q:
            return []

        lower_q = clean_q.lower()
        results: List[Location] = []

        # Check local exact match
        if lower_q in SUGGESTED_LOCATIONS:
            d = SUGGESTED_LOCATIONS[lower_q]
            matched_loc = Location(
                name=d["name"],
                country=d["country"],
                latitude=d["latitude"],
                longitude=d["longitude"],
                admin1=d["admin1"],
                display_name=d["display_name"]
            )
            # If we only need 1 result or exact query, return immediately without network latency
            if limit <= 1 or lower_q in ["chennai", "kanchipuram", "bengaluru", "bangalore", "delhi", "new delhi", "mumbai", "bombay", "kolkata", "calcutta", "hyderabad"]:
                return [matched_loc]
            results.append(matched_loc)

        # Query Open-Meteo Geocoding API
        try:
            params = {
                "name": clean_q,
                "count": max(1, min(limit, 10)),
                "language": "en",
                "format": "json"
            }
            resp = requests.get(cls.GEOCODE_API_URL, params=params, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("results", [])
                for item in items:
                    name = item.get("name")
                    lat = item.get("latitude")
                    lon = item.get("longitude")
                    country = item.get("country_code", "")
                    admin1 = item.get("admin1", "")
                    
                    parts = [name]
                    if admin1 and admin1 != name:
                        parts.append(admin1)
                    if country:
                        parts.append(country)
                    display = ", ".join(parts)

                    loc = Location(
                        name=name,
                        country=country,
                        latitude=round(lat, 4),
                        longitude=round(lon, 4),
                        admin1=admin1 or None,
                        display_name=display
                    )
                    # Avoid duplicate if already added via local match
                    if not any(abs(r.latitude - loc.latitude) < 0.01 and abs(r.longitude - loc.longitude) < 0.01 for r in results):
                        results.append(loc)
        except Exception:
            pass

        return results[:limit]
    @classmethod
    def reverse_geocode(cls, latitude: float, longitude: float) -> Optional[Location]:
        """Turn GPS coordinates into a human-friendly city/locality name."""
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": latitude, "lon": longitude, "format": "json", "zoom": 10, "addressdetails": 1},
                headers={"User-Agent": "WeatherGPT-SIH-MVP/1.0"},
                timeout=8,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            addr = data.get("address", {})
            name = (addr.get("city") or addr.get("town") or addr.get("municipality") or
                    addr.get("village") or addr.get("county") or addr.get("state_district") or "My Location")
            state = addr.get("state") or addr.get("state_district") or ""
            country_code = (addr.get("country_code") or "").upper()
            display_parts = [name]
            if state and state != name:
                display_parts.append(state)
            if addr.get("country"):
                display_parts.append(addr["country"])
            return Location(name=name, country=country_code, admin1=state or None, latitude=round(latitude, 4), longitude=round(longitude, 4), display_name=", ".join(display_parts))
        except Exception:
            return None

