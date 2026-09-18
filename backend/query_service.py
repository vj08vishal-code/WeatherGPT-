"""
query_service.py - Query Understanding & Conversational Context Service (Phase 2).
Identifies weather intent, target dates, time-of-day, locations, and manages multi-turn follow-ups.
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from .models.schemas import Location, ParsedQuery
from .services.language_service import LanguageService


class SessionContext:
    """Stores conversation state for a specific session."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.last_location: Optional[Location] = None
        self.last_target_date: Optional[str] = None  # e.g. "today", "tomorrow"
        self.last_time_of_day: Optional[str] = None  # e.g. "morning", "afternoon", "evening", "night"
        self.last_intent: Optional[str] = None
        self.last_verification: Optional[Dict] = None
        self.last_verification_target_date: Optional[str] = None
        self.last_forecast_anchor_date: Optional[str] = None
        self.updated_at = datetime.now()

    def update(
        self,
        location: Optional[Location] = None,
        target_date: Optional[str] = None,
        time_of_day: Optional[str] = None,
        intent: Optional[str] = None
    ):
        if location:
            self.last_location = location
        if target_date is not None:
            self.last_target_date = target_date
        if time_of_day is not None:
            self.last_time_of_day = time_of_day
        if intent:
            self.last_intent = intent
        self.updated_at = datetime.now()


class QueryService:
    """
    NLP parser for extracting weather intents, temporal parameters, and resolving conversational follow-ups.
    """
    _sessions: Dict[str, SessionContext] = {}

    @classmethod
    def get_session(cls, session_id: Optional[str]) -> SessionContext:
        sid = session_id or "default_session"
        if sid not in cls._sessions:
            cls._sessions[sid] = SessionContext(sid)
        return cls._sessions[sid]

    @classmethod
    def parse_query(cls, raw_message: str, current_location: Optional[Location], session_id: Optional[str]) -> ParsedQuery:
        session = cls.get_session(session_id)
        clean = raw_message.strip()
        lower = re.sub(r"\s+", " ", clean.lower().rstrip("?.!"))
        language = LanguageService.detect(clean)

        # 1. Greetings & Help
        if lower in ["hi", "hello", "hey", "good morning", "good evening", "greetings", "yo"]:
            return ParsedQuery(intent="greeting", raw_message=clean)

        if any(w in lower for w in ["who are you", "what can you do", "help me", "how does this work"]):
            return ParsedQuery(intent="help", raw_message=clean)

        # 2. Extract explicitly mentioned location
        extracted_city = cls._extract_city_name(clean)

        # 3. Extract temporal parameters (date & time of day)
        target_date, time_of_day = cls._extract_temporal_params(lower)

        # 4. Detect if this is a follow-up query
        is_followup = False
        is_what_about = bool(re.search(r"^(?:what|how)\s+about\b", lower))

        # Check for omitted date or time-of-day in follow-up queries
        if is_what_about or (not target_date and time_of_day) or (target_date and not extracted_city and not any(w in lower for w in ["rain", "temp", "wind", "humid", "weather"])):
            is_followup = True
            if not target_date and session.last_target_date:
                target_date = session.last_target_date
            if not time_of_day and session.last_time_of_day:
                time_of_day = session.last_time_of_day

        # Default date if time_of_day specified but no date
        if time_of_day and not target_date:
            target_date = session.last_target_date or "today"

        # 5. Classify Intent
        intent = cls._classify_intent(lower, target_date, time_of_day, is_followup, session.last_intent)

        # Confidence/proof questions are conversational follow-ups. If the user
        # does not repeat the date, keep the exact date from the forecast they
        # just asked about instead of silently switching to current weather.
        if intent == "forecast_confidence" and not target_date:
            if session.last_target_date:
                target_date = session.last_target_date
                is_followup = True
            elif session.last_forecast_anchor_date:
                target_date = session.last_forecast_anchor_date
                is_followup = True

        # Update session memory
        session.update(
            target_date=target_date,
            time_of_day=time_of_day,
            intent=intent if intent not in ["greeting", "help", "unknown"] else None
        )

        return ParsedQuery(
            intent=intent,
            target_date=target_date,
            time_of_day=time_of_day,
            location_name=extracted_city,
            is_followup=is_followup,
            raw_message=clean,
            language=language
        )

    @classmethod
    def _extract_temporal_params(cls, lower: str) -> Tuple[Optional[str], Optional[str]]:
        target_date = None
        time_of_day = None

        # Time of day detection
        if any(w in lower for w in ["evening", "eve"]):
            time_of_day = "evening"
        elif any(w in lower for w in ["morning", "morn"]):
            time_of_day = "morning"
        elif any(w in lower for w in ["afternoon", "noon"]):
            time_of_day = "afternoon"
        elif any(w in lower for w in ["tonight", "night"]):
            time_of_day = "night"

        # Date detection (English + common Indian-language terms).
        if "day after tomorrow" in lower or "परसों" in lower:
            target_date = "day_after_tomorrow"
        elif any(w in lower for w in [
            "tomorrow", "कल", "उद्या", "naalai", "naalaiku", "nalaiku", "naliku",
            "நாளை", "நாளைக்கு", "రేపు", "రేపటి", "ನಾಳೆ", "ನಾಳೆಗೆ",
            "আগামীকাল", "নাল", "നാളെ", "നാളേക്ക്"
        ]):
            target_date = "tomorrow"
        elif "tonight" in lower or "आज रात" in lower:
            target_date = "today"
            time_of_day = "night"
        elif any(w in lower for w in ["today", "now", "currently", "right now", "आज", "आजच", "aaj", "indru", "இன்று", "ఈరోజు", "ಇಂದು", "আজ", "ഇന്ന്"]):
            target_date = "today"
        elif any(d in lower for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
            for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                if d in lower:
                    target_date = d
                    break

        return target_date, time_of_day

    @classmethod
    def _classify_intent(
        cls,
        lower: str,
        target_date: Optional[str],
        time_of_day: Optional[str],
        is_followup: bool,
        last_intent: Optional[str]
    ) -> str:
        # Normalize punctuation/hyphens so natural variations such as
        # "7-day", "7 day", "7 days", and "why-is-the-forecast-accurate"
        # are understood the same way.
        lower = re.sub(r"[-_/]+", " ", lower)
        lower = re.sub(r"\s+", " ", lower).strip()

        # 1. Forecast confidence / verification
        if any(w in lower for w in [
            "accuracy", "accurate", "confidence", "confident", "reliable", "reliability",
            "verify", "verification", "verified", "trust", "proof", "proof of confidence",
            "compare sources", "compare providers", "other source", "other sources",
            "other site", "other sites", "source agreement", "how sure", "how certain",
            "can i trust", "why trust", "why this confidence", "why the confidence",
            "why is the confidence", "why is this accurate", "why is the forecast accurate",
            "why is this forecast accurate", "why is the forecast high", "why high confidence",
            "why high accuracy", "is this accurate", "is this reliable", "is this forecast reliable"
        ]):
            return "forecast_confidence"

        # 2. Umbrella
        if any(w in lower for w in ["umbrella", "need an umbrella", "carry an umbrella", "bring an umbrella", "छाता", "छत्री", "कुडी", "குடை", "గొడుగు", "ಛತ್ರಿ", "ছাতা", "കുട"]):
            return "umbrella_recommendation"

        if any(w in lower for w in [
            "sunscreen", "sun screen", "sunburn", "uv index", "uv",
            "सनस्क्रीन", "सन्स्क्रीन", "सनबर्न", "uv सूचकांक",
            "சன்ஸ்கிரீன்", "சன் ஸ்கிரீன்", "சூரிய பாதுகாப்பு",
            "సన్‌స్క్రీన్", "సన్ స్క్రీన్", "సన్‌బర్న",
            "ಸನ್‌ಸ್ಕ್ರೀನ್", "ಸನ್ ಸ್ಕ್ರೀನ್", "ಸನ್ ಬರ್ನ",
            "সানস্ক্রিন", "সানবার্ন", "സൺസ്ക്രീൻ", "സൺബേൺ"
        ]):
            return "sunscreen_recommendation"

        if any(w in lower for w in ["sunglasses", "sun glasses", "sunlight", "धूप का चश्मा", "चष्मा", "கண்ணாடி", "సన్ గ్లాసెస్", "sunglass", "ಸನ್ ಗ್ಲಾಸ್", "সানগ্লাস", "സൺഗ്ലാസ്"]):
            return "sunglasses_recommendation"

        # 2. Outdoor Activities
        if any(w in lower for w in ["outdoor", "outdoors", "outside", "go out", "play outside", "picnic", "hiking", "walk outside", "बाहर", "बाहेर", "வெளியே", "బయట", "ಹೊರಗೆ", "বাইরে", "പുറത്ത്"]):
            return "outdoor_suitability"

        # 3. Agriculture / farm advisory
        if any(w in lower for w in [
            "farmer", "farm", "farming", "crop", "crops", "pesticide", "किसान", "खेती", "फसल", "पाऊस", "शेती", "பயிர்", "விவசாயம்", "పంట", "వ్యవసాయం", "ಬೆಳೆ", "ಕೃಷಿ", "ফসল", "চাষ", "വിള", "കൃഷി",
            "spray pesticide", "spraying", "irrigation", "sowing", "harvest"
        ]):
            return "agriculture_advisory"

        # 4. Travel
        if any(w in lower for w in ["travel", "trip", "driving", "commute", "road trip", "flight"]):
            return "travel_suitability"

        # 5. 7-Day / Weekly Forecast
        # Accept natural variations instead of requiring one exact sentence.
        weekly_patterns = [
            r"\b(?:next|coming|upcoming)\s+(?:7|seven)\s+days?\b",
            r"\b(?:weather|forecast)\s+(?:for|over|during)\s+(?:the\s+)?(?:next|coming|upcoming)\s+(?:7|seven)\s+days?\b",
            r"\b(?:weather|forecast)\s+(?:for|over)\s+(?:the\s+)?(?:7|seven)\s+days?\b",
            r"\b(?:next|coming|upcoming)\s+week(?:'s|s)?\s+(?:weather|forecast|outlook)\b",
            r"\b(?:weather|forecast|outlook)\s+(?:for|this|next|over)\s+(?:the\s+)?week\b",
            r"\bweekly\s+(?:weather|forecast|outlook)\b",
        ]
        if any(re.search(p, lower) for p in weekly_patterns):
            return "forecast_7day"
        if any(w in lower for w in [
            "7 day", "7-day", "7day", "7 days", "seven days", "seven-day",
            "next 7 days", "next seven days", "forecast for 7 days",
            "forecast for seven days", "weather for 7 days", "weather for seven days",
            "week forecast", "weekly forecast", "forecast this week",
            "forecast for this week", "this week's forecast", "this weeks forecast",
            "week's forecast", "weather this week", "weather for this week",
            "weather next week", "weather for next week", "next week's weather",
            "next weeks weather", "coming week", "coming week's weather",
            "coming weeks weather", "weather for the coming week",
            "weather outlook for the week", "weekly outlook"
        ]):
            return "forecast_7day"

        # 5. Humidity
        if any(w in lower for w in ["humidity", "how humid", "humid", "muggy", "moisture"]):
            return "humidity"

        # 6. Wind
        if any(w in lower for w in ["wind", "windy", "breeze", "wind speed", "gust", "gusts"]):
            return "wind"

        # 7. Feels Like
        if any(w in lower for w in ["feels like", "feel like", "real feel", "apparent temp"]):
            return "feels_like"

        # 8. Rain / Precipitation
        rain_keywords = [
            "rain", "raining", "rainy", "precipitation", "drizzle", "shower", "बारिश", "वर्षा", "पाऊस",
            "mazhai", "mazha", "malai", "malay", "mazhai iruka", "malai iruka",
            "மழை", "மழை இருக்கா", "వర్షం", "ಮಳೆ", "বৃষ্টি", "മഴ",
            "showers", "chance of rain", "probability of rain", "will it rain",
            "is it going to rain", "expect rain", "any rain"
        ]
        if any(w in lower for w in rain_keywords):
            if time_of_day:
                return "part_of_day"
            if target_date == "tomorrow":
                return "rain_tomorrow"
            return "rain"

        # 9. Temperature
        temp_keywords = [
            "temperature", "temp", "how hot", "how cold", "how warm", "degrees", "celsius", "तापमान", "हवामान", "तापमान", "வெப்பநிலை", "ఉష్ణోగ్రత", "ತಾಪಮಾನ", "তাপমাত্রা", "താപനില"
        ]
        if any(w in lower for w in temp_keywords):
            return "temperature"

        # 10. Specific part-of-day query
        if time_of_day:
            return "part_of_day"

        # 11. Tomorrow / weekday weather
        if target_date == "tomorrow":
            return "weather_tomorrow"
        if target_date in {
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"
        }:
            return "weather_tomorrow"

        # 12. Follow-up resolution
        if is_followup and last_intent:
            return last_intent

        # 13. General Forecast
        if "forecast" in lower:
            return "forecast_7day" if "week" in lower else "current_weather"

        # 14. Current Weather
        if any(w in lower for w in ["weather", "condition", "sky", "climate", "status", "मौसम", "हवामान", "வானிலை", "వాతావరణం", "ಹವಾಮಾನ", "আবহাওয়া", "കാലാവസ്ഥ"]):
            return "current_weather"

        # Default fallback
        return "current_weather"

    @classmethod
    def _extract_city_name(cls, text: str) -> Optional[str]:
        """
        Extract a likely location from natural-language weather questions.

        The old parser depended heavily on one exact word order. This version
        handles common variations such as:
          - weather in Tokyo
          - weather in New York tomorrow
          - will it rain in Paris tonight
          - temperature for São Paulo
          - Tokyo weather
          - what about London?
        """
        clean = re.sub(r"\s+", " ", text.strip())
        if not clean:
            return None

        # Common Indian-language city names/transliterations. Return canonical English
        # names so the existing geocoder can resolve them reliably.
        native_cities = {
            "मुंबई": "Mumbai", "मुम्बई": "Mumbai", "दिल्ली": "Delhi", "चेन्नई": "Chennai",
            "बेंगलुरु": "Bengaluru", "बंगलौर": "Bengaluru", "कोलकाता": "Kolkata", "हैदराबाद": "Hyderabad",
            "மும்பை": "Mumbai", "சென்னை": "Chennai", "பெங்களூரு": "Bengaluru", "டெல்லி": "Delhi",
            "హైదరాబాద్": "Hyderabad", "ముంబై": "Mumbai", "చెన్నై": "Chennai", "ఢిల్లీ": "Delhi",
            "ಬೆಂಗಳೂರು": "Bengaluru", "ಮುಂಬೈ": "Mumbai", "ಚೆನ್ನೈ": "Chennai", "ದೆಹಲಿ": "Delhi",
            "কলকাতা": "Kolkata", "মুম্বাই": "Mumbai", "চেন্নাই": "Chennai", "দিল্লি": "Delhi",
            "മുംബൈ": "Mumbai", "ചെന്നൈ": "Chennai", "ഡൽഹി": "Delhi",
            "टोक्यो": "Tokyo", "लंदन": "London", "न्यूयॉर्क": "New York", "पेरिस": "Paris", "सिंगापुर": "Singapore", "दुबई": "Dubai",
            "டோக்கியோ": "Tokyo", "லண்டன்": "London", "நியூயார்க்": "New York",
            "టోక్యో": "Tokyo", "లండన్": "London", "న్యూయార్క్": "New York",
            "ಟೋಕಿಯೋ": "Tokyo", "ಲಂಡನ್": "London", "ನ್ಯೂಯಾರ್ಕ್": "New York",
            "টোকিও": "Tokyo", "লন্ডন": "London", "নিউ ইয়র্ক": "New York",
            "ടോക്കിയോ": "Tokyo", "ലണ്ടൻ": "London", "ന്യൂയോർക്ക്": "New York",
        }
        for native, canonical in native_cities.items():
            if native in clean:
                return canonical

        # Romanized common city names.
        roman_cities = {"mumbai":"Mumbai", "bombay":"Mumbai", "delhi":"Delhi", "new delhi":"Delhi", "chennai":"Chennai", "madras":"Chennai", "bengaluru":"Bengaluru", "bangalore":"Bengaluru", "kolkata":"Kolkata", "calcutta":"Kolkata", "hyderabad":"Hyderabad"}
        low_clean = clean.lower()
        for alias, canonical in sorted(roman_cities.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", low_clean):
                return canonical

        # Forecast-window phrases are never locations. This guard is deliberately
        # broad so conversational variants such as "7 days", "7-day", "7day",
        # "seven days", "next week", and "this week" cannot become fake cities.
        # Explicit city names are handled first by the city-name dictionaries above.
        forecast_window_phrases = [
            r"\b7\s*[- ]?days?\b",
            r"\bseven\s*[- ]?days?\b",
            r"\bnext\s+7\s+days?\b",
            r"\bnext\s+seven\s+days?\b",
            r"\b(?:this|next|coming)\s+week\b",
            r"\bweekly\b",
            r"\bweek(?:ly)?\s+forecast\b",
        ]
        if any(re.search(p, low_clean) for p in forecast_window_phrases):
            return None

        # Remove question punctuation and normalize common temporal/filler words.
        candidate = clean.rstrip(" ?!.")
        temporal_words = {
            "today", "tomorrow", "tonight", "now", "currently", "right now",
            "this morning", "this afternoon", "this evening", "this night",
            "morning", "afternoon", "evening", "night", "day after tomorrow",
            "next week", "this week"
        }
        filler_words = {
            "the", "a", "an", "please", "weather", "temperature", "temp",
            "rain", "raining", "rainy", "forecast", "wind", "humidity",
            "condition", "sky", "climate", "what", "how", "is", "are",
            "will", "it", "be", "going", "to", "tell", "show", "me",
            "about", "like", "for", "at", "in", "of", "what's", "whats", "'s"
        }

        # Prefer text following a location preposition. Stop before temporal
        # phrases or question clauses.
        patterns = [
            r"\b(?:in|at|for)\s+(.+?)(?=\s+(?:today|tomorrow|tonight|now|currently|right now|this morning|this afternoon|this evening|this week|next week)\b|$)",
            r"\b(?:what|how)\s+about\s+(.+)$",
            r"^(.+?)\s+(?:weather|forecast|temperature|temp)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, candidate, re.IGNORECASE)
            if not match:
                continue

            cand = match.group(1).strip(" ,.-")
            # Remove trailing conversational clauses that aren't part of a city.
            cand = re.split(
                r"\s+(?:what|will|how|is|are|tell|show|please)\b",
                cand,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip(" ,.-")

            # A follow-up such as "What about tomorrow?" must not treat the
            # temporal word itself as a city. Check this before returning.
            if cand.lower() in temporal_words:
                continue

            # Remove temporal phrases even when they weren't caught by the lookahead.
            for phrase in sorted(temporal_words, key=len, reverse=True):
                cand = re.sub(rf"\s+{re.escape(phrase)}$", "", cand, flags=re.IGNORECASE).strip(" ,.-")

            # Keep letters, spaces, apostrophes, hyphens and common city punctuation.
            cand = re.sub(r"[^\w\s.'’,-]", " ", cand, flags=re.UNICODE)
            cand = re.sub(r"\s+", " ", cand).strip(" ,.-")

            tokens = [w for w in cand.split() if w.lower() not in filler_words]
            if tokens:
                return " ".join(tokens)

        # Action questions without a city should use the active/current location.
        if any(w in clean.lower() for w in [
            "umbrella", "sunglasses", "sun glasses", "sunlight", "sunscreen", "sun screen", "sunburn", "uv index", "uv",
            "छाता", "छत्री", "குடை", "గొడుగు", "ಛತ್ರಿ", "ছাতা", "കുട",
            "धूप का चश्मा", "சன் க்ளாஸ்", "సన్ గ్లాసెస్", "सनग्लास"
        ]):
            return None

        # A final fallback for short "weather London" / "London weather" forms.
        stripped = re.sub(
            r"\b(?:today|tomorrow|tonight|now|currently|right now|morning|afternoon|evening|night)\b",
            " ",
            candidate,
            flags=re.IGNORECASE,
        )
        stripped = re.sub(
            r"\b(?:weather|forecast|temperature|temp|rain|wind|humidity)\b",
            " ",
            stripped,
            flags=re.IGNORECASE,
        )
        stripped = re.sub(
            r"\b(?:7\s*[- ]?days?|seven\s*[- ]?days?|weekly|week)\b",
            " ",
            stripped,
            flags=re.IGNORECASE,
        )
        stripped = re.sub(r"\s+", " ", stripped).strip(" ,.-")
        # Never turn a conversational action/advisory sentence into a city name.
        action_markers = [
            "sunscreen", "sun screen", "sunburn", "umbrella", "sunglasses", "sun glasses",
            "should i", "can i", "is it safe", "take", "wear", "use", "carry",
            "nalaiku", "naalaiku", "malai iruka", "mazhai iruka", "நாளைக்கு", "மழை இருக்கா"
        ]
        if any(marker in low_clean for marker in action_markers):
            return None

        if stripped and len(stripped.split()) <= 6:
            tokens = [w for w in stripped.split() if w.lower() not in filler_words]
            if tokens:
                return " ".join(tokens)

        return None
