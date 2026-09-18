"""
chatbot.py - Natural Language Query Understanding and Weather Response Generator.

This module processes user questions (like "What is the weather in Chennai?",
"What is the temperature in Delhi?", or "Will it rain in Mumbai?"), extracts
the target city and user's intent, fetches live weather data, and composes a
friendly, natural conversational answer.
"""

import re
from typing import Dict, Any, Optional, Tuple
from .weather_service import get_weather

# Common question words / filler words to strip when extracting city names
FILLER_WORDS = {
    "today", "now", "currently", "please", "tomorrow", "tonight", "right now",
    "the", "a", "an", "city", "tell", "me", "about", "like"
}

def extract_city_and_intent(message: str) -> Tuple[Optional[str], str]:
    """
    Analyzes the user's message to extract:
    1. The city name (or None if not found)
    2. The intent: 'temperature', 'rain', 'wind', 'humidity', or 'general'
    """
    clean_text = message.strip().rstrip("?.!").lower()
    
    # 1. Determine the intent of the question
    if any(keyword in clean_text for keyword in ["temp", "temperature", "how hot", "how cold", "warm", "degrees"]):
        intent = "temperature"
    elif any(keyword in clean_text for keyword in ["rain", "raining", "rainy", "umbrella", "shower", "precipitation"]):
        intent = "rain"
    elif any(keyword in clean_text for keyword in ["wind", "windy", "breeze"]):
        intent = "wind"
    elif any(keyword in clean_text for keyword in ["humidity", "humid"]):
        intent = "humidity"
    else:
        intent = "general"

    # 2. Extract city name using regular expression patterns
    city = None

    patterns = [
        # "weather in chennai", "temperature in delhi", "will it rain in mumbai"
        r"(?:weather|temperature|temp|rain|raining|forecast|wind|humidity|condition)\s+(?:in|for|at|of)\s+([a-zA-Z\s]+)",
        # "in chennai will it rain", "for delhi what is the weather"
        r"^(?:in|for|at)\s+([a-zA-Z\s]+?)(?:\s+(?:what|will|how|is|tell)|$)",
        # "what is the weather like in chennai"
        r"(?:what|how)\s+is(?:\s+the)?\s+(?:weather|temperature|temp)\s+(?:like\s+)?(?:in|for|at)\s+([a-zA-Z\s]+)",
        # "will it rain in chennai"
        r"will\s+it\s+rain\s+(?:in|for|at)\s+([a-zA-Z\s]+)",
        # "is it raining in chennai"
        r"is\s+it\s+raining\s+(?:in|for|at)\s+([a-zA-Z\s]+)",
        # "tell me the weather in chennai"
        r"(?:tell\s+me|show\s+me|get)\s+(?:the\s+)?(?:weather|temperature|temp|forecast)\s+(?:in|for|at|of)\s+([a-zA-Z\s]+)",
        # "chennai weather", "delhi temperature"
        r"^([a-zA-Z\s]+)\s+(?:weather|temperature|temp|forecast)$"
    ]

    for pattern in patterns:
        match = re.search(pattern, clean_text)
        if match:
            city = match.group(1).strip()
            break

    # If no pattern matched, check if user simply typed a city name (1 to 3 words)
    if not city and clean_text:
        words = clean_text.split()
        if len(words) <= 3 and not any(w in words for w in ["hi", "hello", "hey", "help", "who"]):
            city = clean_text

    # Clean up any trailing filler words from the extracted city
    if city:
        city_tokens = [w for w in city.split() if w not in FILLER_WORDS]
        city = " ".join(city_tokens).strip()

    return (city if city else None, intent)


def handle_user_query(message: str) -> Dict[str, Any]:
    """
    Main entry point for processing chat queries.
    Returns a dictionary with conversational text and structured weather data.
    """
    trimmed = message.strip()
    if not trimmed:
        return {
            "reply": "Hello! Ask me any weather question, for example: *'What is the weather in Chennai?'*",
            "weather_data": None
        }

    lower_msg = trimmed.lower()

    # Handle basic greetings
    if lower_msg in ["hi", "hello", "hey", "good morning", "good evening", "greetings"]:
        return {
            "reply": "👋 Hello! I'm **WeatherGPT**, your personal weather assistant. You can ask me questions like:\n\n"
                     "• *'What is the weather in Chennai?'*\n"
                     "• *'What is the temperature in Delhi?'*\n"
                     "• *'Will it rain in Mumbai?'*",
            "weather_data": None
        }

    # Handle help or about questions
    if "who are you" in lower_msg or "help" in lower_msg:
        return {
            "reply": "I am **WeatherGPT**! I can check real-time temperatures, rain conditions, wind speed, and general forecasts for any city worldwide. Try asking: *'What is the temperature in Delhi?'*",
            "weather_data": None
        }

    # Extract city and intent
    city, intent = extract_city_and_intent(trimmed)

    if not city:
        return {
            "reply": "I'd love to help with the weather! Could you please mention the city? For example: *'What is the weather in Chennai?'* or *'Will it rain in Mumbai?'*",
            "weather_data": None
        }

    # Fetch live weather data
    weather = get_weather(city)

    if not weather.get("success"):
        error_msg = weather.get("error", f"Could not find weather data for '{city}'.")
        return {
            "reply": f"❌ Sorry, I couldn't get the weather for **{city.title()}**. {error_msg}",
            "weather_data": None
        }

    # Generate friendly conversational reply based on the user's intent
    city_name = weather["city"]
    temp = weather["temperature"]
    feels_like = weather["feels_like"]
    description = weather["description"]
    humidity = weather["humidity"]
    wind_speed = weather["wind_speed"]
    is_raining = weather["is_raining"]
    rain_amount = weather["rain_amount"]

    if intent == "temperature":
        reply = (
            f"🌡️ The current temperature in **{city_name}** is **{temp}°C** "
            f"(feels like **{feels_like}°C**) with **{description}**."
        )
    elif intent == "rain":
        if is_raining:
            reply = (
                f"🌧️ **Yes, it is currently raining in {city_name}!**\n\n"
                f"Current condition is **{description}** with approximately **{rain_amount} mm** of precipitation. "
                f"Temperature is **{temp}°C**. Don't forget your umbrella! ☔"
            )
        else:
            reply = (
                f"☀️ **No, it is not raining in {city_name} right now.**\n\n"
                f"The current condition is **{description}** with a temperature of **{temp}°C** "
                f"and humidity at **{humidity}%**."
            )
    elif intent == "wind":
        reply = (
            f"💨 In **{city_name}**, the wind is blowing at **{wind_speed} km/h** "
            f"with a temperature of **{temp}°C** ({description})."
        )
    elif intent == "humidity":
        reply = (
            f"💧 The humidity in **{city_name}** is currently at **{humidity}%** "
            f"with a temperature of **{temp}°C** ({description})."
        )
    else:
        # General weather overview
        rain_phrase = "🌧️ It is currently raining." if is_raining else "🌤️ No rain reported right now."
        reply = (
            f"📍 **Weather in {city_name}:**\n\n"
            f"• **Condition:** {description}\n"
            f"• **Temperature:** {temp}°C (feels like {feels_like}°C)\n"
            f"• **Humidity:** {humidity}%\n"
            f"• **Wind Speed:** {wind_speed} km/h\n"
            f"• {rain_phrase}"
        )

    return {
        "reply": reply,
        "weather_data": weather
    }
