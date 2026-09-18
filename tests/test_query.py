"""Focused tests for WeatherGPT conversational parsing."""

from backend.services.query_service import QueryService


def parse(message: str):
    return QueryService.parse_query(message, None, f"test-{message}")


def test_global_city_extraction():
    cases = {
        "Weather in Tokyo": "Tokyo",
        "weather in New York tomorrow": "New York",
        "temperature for São Paulo": "São Paulo",
        "Tokyo weather": "Tokyo",
        "What's the weather in Washington, D.C.?": "Washington, D.C",
    }
    for message, expected_city in cases.items():
        assert parse(message).location_name == expected_city


def test_temporal_intents():
    assert parse("weather tomorrow morning in London").intent == "part_of_day"
    assert parse("will it rain tomorrow in Paris").intent == "rain_tomorrow"
    assert parse("tomorrow in Mumbai").intent == "weather_tomorrow"
    assert parse("will it rain tonight in Paris").intent == "part_of_day"


def test_agriculture_intent():
    result = parse("Can I spray pesticide tomorrow in Chennai?")
    assert result.intent == "agriculture_advisory"
    assert result.location_name == "Chennai"


def test_action_and_romanized_tamil_intents():
    q = parse("should i use sunscreen tomorrow")
    assert q.intent == "sunscreen_recommendation"
    assert q.target_date == "tomorrow"
    assert q.location_name is None

    q = parse("should i wear sunglasses tomorrow")
    assert q.intent == "sunglasses_recommendation"
    assert q.location_name is None

    q = parse("should i take an umbrella tomorrow")
    assert q.intent == "umbrella_recommendation"
    assert q.location_name is None

    q = parse("nalaiku malai iruka")
    assert q.intent == "rain_tomorrow"
    assert q.target_date == "tomorrow"
    assert q.location_name is None
    assert q.language == "ta"

    q = parse("நாளைக்கு மழை இருக்கா")
    assert q.intent == "rain_tomorrow"
    assert q.target_date == "tomorrow"
    assert q.location_name is None
    assert q.language == "ta"
