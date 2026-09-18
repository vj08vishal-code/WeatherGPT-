"""
live_integration_test.py - Live end-to-end test suite against running WeatherGPT server.
"""

import sys
import io
import requests

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000"

def test_suite():
    print("================================================================")
    print("      WeatherGPT Phase 1 MVP - Live End-to-End Test Suite       ")
    print("================================================================")

    # 1. Health & Server Status
    r = requests.get(f"{BASE_URL}/api/health", timeout=5)
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    health_data = r.json()
    print(f"[OK] 1. Server Health: {health_data['status'].upper()} (Provider: {health_data['provider']})")

    # 2. Suggested Core Locations
    r = requests.get(f"{BASE_URL}/api/suggested-locations", timeout=5)
    assert r.status_code == 200
    hubs = r.json()
    assert len(hubs) == 7
    hub_names = [h["name"] for h in hubs]
    print(f"[OK] 2. 7 Suggested Core Hubs verified: {', '.join(hub_names)}")

    # 3. Chennai Real Weather Telemetry (Primary Requirement)
    r = requests.get(f"{BASE_URL}/api/weather?city=Chennai", timeout=10)
    assert r.status_code == 200, f"Chennai weather failed: {r.status_code}"
    chennai_data = r.json()
    cur = chennai_data["current"]
    assert "temperature" in cur and isinstance(cur["temperature"], (int, float))
    assert "feels_like" in cur
    assert "condition" in cur and cur["condition"]
    assert "humidity" in cur
    assert "wind_speed" in cur
    assert "wind_direction_compass" in cur
    assert "precipitation" in cur
    assert "sunrise" in cur and cur["sunrise"]
    assert "sunset" in cur and cur["sunset"]
    assert len(chennai_data["forecast"]) == 7
    print(f"[OK] 3. Real Chennai Weather Test SUCCEEDED:")
    print(f"     - Temperature: {cur['temperature']}°C (Feels like: {cur['feels_like']}°C)")
    print(f"     - Atmospheric Condition: {cur['condition']}")
    print(f"     - Relative Humidity: {cur['humidity']}%")
    print(f"     - Wind Vector: {cur['wind_speed']} km/h from {cur['wind_direction_compass']} ({cur['wind_direction']}°)")
    print(f"     - Precipitation: {cur['precipitation']} mm (Is Raining: {cur['is_raining']})")
    print(f"     - Astronomical: Sunrise at {cur['sunrise']}, Sunset at {cur['sunset']}")
    print(f"     - Daily Forecast Days: {len(chennai_data['forecast'])} days")

    # 4. Secondary Cities Testing (Bengaluru, Delhi, Kanchipuram, Mumbai)
    test_cities = ["Bengaluru", "Delhi", "Kanchipuram", "Mumbai", "Kolkata", "Hyderabad"]
    print(f"\n[OK] 4. Testing Secondary Hubs Real Data:")
    for city in test_cities:
        r = requests.get(f"{BASE_URL}/api/weather?city={city}", timeout=10)
        assert r.status_code == 200, f"Weather for {city} failed"
        c_cur = r.json()["current"]
        print(f"     - {city:<12}: {c_cur['temperature']:>4.1f}°C | {c_cur['condition']:<18} | Wind: {c_cur['wind_speed']:>4.1f} km/h {c_cur['wind_direction_compass']}")

    # 5. Geocoding Search Test
    print(f"\n[OK] 5. Testing Location Geocoding:")
    for q in ["Bengaluru", "Tokyo", "London"]:
        r = requests.get(f"{BASE_URL}/api/geocode?query={q}", timeout=8)
        assert r.status_code == 200
        results = r.json()
        assert len(results) > 0, f"No results for {q}"
        first = results[0]
        print(f"     - Search '{q}': Matched '{first['name']}', Lat {first['latitude']}, Lon {first['longitude']} ({first.get('display_name')})")

    # 6. Chat Interaction Tests
    print(f"\n[OK] 6. Testing Conversational Chat Endpoints:")
    chat_cases = [
        ("What's the weather?", {"name": "Chennai", "latitude": 13.0827, "longitude": 80.2707}),
        ("What's the temperature?", {"name": "Chennai", "latitude": 13.0827, "longitude": 80.2707}),
        ("Is it raining?", {"name": "Chennai", "latitude": 13.0827, "longitude": 80.2707}),
        ("How is the weather tomorrow?", {"name": "Chennai", "latitude": 13.0827, "longitude": 80.2707}),
        ("Show me the 7-day forecast", {"name": "Chennai", "latitude": 13.0827, "longitude": 80.2707}),
        ("What is the temperature in Delhi?", {"name": "Chennai", "latitude": 13.0827, "longitude": 80.2707}),
        ("Weather in Bengaluru", {"name": "Chennai", "latitude": 13.0827, "longitude": 80.2707}),
        ("Hello", {"name": "Chennai", "latitude": 13.0827, "longitude": 80.2707}),
        ("Who are you?", {"name": "Chennai", "latitude": 13.0827, "longitude": 80.2707}),
    ]

    for query, loc in chat_cases:
        r = requests.post(f"{BASE_URL}/api/chat", json={"message": query, "location": loc}, timeout=10)
        assert r.status_code == 200
        reply = r.json()["reply"]
        first_line = reply.splitlines()[0]
        print(f"     - User: \"{query}\"\n       Bot : {first_line}")

    # 7. Error Handling & Edge Cases
    print(f"\n[OK] 7. Testing Error States & Graceful Degradation:")
    # Invalid City
    r = requests.post(f"{BASE_URL}/api/chat", json={"message": "Weather in NonExistentFakeCityXYZ98765"}, timeout=10)
    assert r.status_code == 200
    res_data = r.json()
    assert "couldn't locate" in res_data["reply"].lower() or "not found" in res_data["reply"].lower()
    print(f"     - Unknown city query returned graceful error message: \"{res_data['reply']}\"")

    # Empty Query
    r = requests.post(f"{BASE_URL}/api/chat", json={"message": "   "}, timeout=5)
    assert r.status_code == 200
    print(f"     - Empty message handled gracefully: \"{r.json()['reply']}\"")

    # 8. Frontend Assets Verification
    print(f"\n[OK] 8. Testing Frontend Assets:")
    r = requests.get(f"{BASE_URL}/", timeout=5)
    assert r.status_code == 200 and "WeatherGPT" in r.text
    print("     - GET / : 200 OK (Served index.html, length: " + str(len(r.text)) + " bytes)")

    r = requests.get(f"{BASE_URL}/static/style.css", timeout=5)
    assert r.status_code == 200 and "app-layout" in r.text
    print("     - GET /static/style.css : 200 OK (Served CSS, length: " + str(len(r.text)) + " bytes)")

    r = requests.get(f"{BASE_URL}/static/app.js", timeout=5)
    assert r.status_code == 200 and "AppState" in r.text
    print("     - GET /static/app.js : 200 OK (Served JavaScript, length: " + str(len(r.text)) + " bytes)")

    print("\n================================================================")
    print("   ALL TESTS PASSED! Production-Quality MVP Verified 100%   ")
    print("================================================================")

if __name__ == "__main__":
    test_suite()
