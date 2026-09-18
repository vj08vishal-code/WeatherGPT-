"""
chat_service.py - Conversational Weather Chat Processor (Phase 2 Façade).
Routes incoming queries through:
  QueryService (intent + city extraction)
  → LocationService (geocoding)
  → WeatherService (live telemetry)
  → ResponseService (precise, intent-scoped reply)

Preserves Phase 1 greeting / help responses verbatim.
"""

from typing import Optional
from .models.schemas import ChatRequest, ChatResponse, Location
from .weather.open_meteo import OpenMeteoClient
from .services.location_service import LocationService
from .query_service import QueryService
from .services.weather_service import WeatherService
from .services.response_service import ResponseService
from .services.language_service import LanguageService
from .verification_service import VerificationService


class ChatService:
    """Conversational engine for WeatherGPT (Phase 2)."""

    def __init__(self, weather_client: Optional[OpenMeteoClient] = None):
        weather_client = weather_client or OpenMeteoClient()
        self.weather_service = WeatherService(weather_client)
        self.verification_service = VerificationService()

    def process_message(self, request: ChatRequest) -> ChatResponse:
        """Main chat handler — intent-first, then targeted response."""
        raw_msg = request.message.strip()

        # Empty message guard
        if not raw_msg:
            return ChatResponse(
                reply="Hello! How can I assist you with the weather today? Ask me about temperature, rainfall, or a 7-day forecast.",
                weather_data=None,
                location=request.location,
                intent="empty",
                card_type=None
            )

        # ── Step 1: Parse intent, location name, temporal params ──────────────
        parsed = QueryService.parse_query(
            raw_message=raw_msg,
            current_location=request.location,
            session_id=request.session_id
        )

        # ── Step 2: Static responses (no weather fetch needed) ─────────────────
        if parsed.intent == "greeting":
            active_loc_name = request.location.name if request.location else "your location"
            return ChatResponse(
                reply=(
                    f"👋 Hello! I am **WeatherGPT**, your atmospheric intelligence assistant.\n\n"
                    f"Currently tracking **{active_loc_name}**. You can ask me:\n"
                    f"• *\"What's the temperature?\"*\n"
                    f"• *\"Will it rain?\"*\n"
                    f"• *\"How is the weather tomorrow?\"*\n"
                    f"• *\"What's the 7-day forecast?\"*\n"
                    f"Or mention any other city like *\"Weather in London\"*."
                ),
                weather_data=None,
                location=request.location,
                intent="greeting",
                card_type=None
            )

        if parsed.intent == "help":
            return ChatResponse(
                reply=(
                    "🌦️ **WeatherGPT** provides real-time, precision atmospheric telemetry and 7-day forecasts powered by Open-Meteo.\n\n"
                    "Ask questions like:\n"
                    "• *\"What is the temperature in Delhi?\"*\n"
                    "• *\"Is it raining right now?\"*\n"
                    "• *\"How is the weather tomorrow in Chennai?\"*\n"
                    "• *\"Show me the weekly forecast.\"*"
                ),
                weather_data=None,
                location=request.location,
                intent="help",
                card_type=None
            )

        # ── Step 3: Resolve target location ───────────────────────────────────
        target_location: Optional[Location] = None

        if parsed.location_name:
            # Query mentioned an explicit city — geocode it
            target_location = LocationService.resolve_location(parsed.location_name)
            if not target_location:
                return ChatResponse(
                    reply=(
                        f"❌ I couldn't locate **\"{parsed.location_name.title()}\"**. "
                        f"Please check the spelling or select a city from the location search."
                    ),
                    weather_data=None,
                    location=request.location,
                    intent="unknown_location",
                    card_type=None
                )
        elif request.location:
            # No city in query — use the currently selected location
            target_location = request.location
        else:
            # Absolute fallback
            target_location = LocationService.get_default_location()

        # Update session context with resolved location
        session = QueryService.get_session(request.session_id)
        session.update(location=target_location)

        # ── Step 4: Fetch live weather data ────────────────────────────────────
        try:
            weather_report = self.weather_service.get_weather_report(target_location)
        except Exception as e:
            return ChatResponse(
                reply=f"⚠️ Unable to retrieve live weather data for **{target_location.name}** right now. Error: {str(e)}",
                weather_data=None,
                location=target_location,
                intent="api_error",
                card_type=None
            )

        # ── Step 5: Cross-check the weather with an independent provider ──────
        verification_target_date = None
        if parsed.target_date == "tomorrow" and len(weather_report.forecast) > 1:
            verification_target_date = weather_report.forecast[1].date
        elif parsed.target_date in {
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"
        }:
            wanted = parsed.target_date[:3].lower()
            for item in weather_report.forecast:
                if item.day.lower().startswith(wanted):
                    verification_target_date = item.date
                    break

        # For a proof/confidence follow-up, reuse the exact verification snapshot
        # that produced the earlier indicator. This prevents a second live API
        # call from changing MEDIUM -> HIGH (or vice versa) moments later.
        session = QueryService.get_session(request.session_id)

        # A follow-up such as "why this confidence?" MUST explain the exact
        # indicator shown on the previous answer. Do not make a second live
        # verification call that can change MEDIUM -> HIGH (or vice versa).
        if parsed.intent == "forecast_confidence" and session.last_verification is not None:
            verification = session.last_verification
            verification_target_date = session.last_verification_target_date
        else:
            verification = self.verification_service.verify(
                location=target_location,
                report=weather_report,
                target_date=verification_target_date
            )

        # ── Step 6: Generate precise, intent-scoped response ──────────────────
        if parsed.intent == "forecast_confidence":
            level = verification.get("level", "UNVERIFIED")
            summary = verification.get("summary", "")
            reasons = verification.get("reasons", [])
            scope = "the requested forecast" if verification.get("mode") == "forecast" else "the current weather"
            if level == "HIGH":
                lead = f"🟢 **Forecast confidence: HIGH** for {target_location.name}."
            elif level == "MEDIUM":
                lead = f"🟡 **Forecast confidence: MEDIUM** for {target_location.name}."
            elif level == "LOW":
                lead = f"🔴 **Forecast confidence: LOW** for {target_location.name}."
            else:
                lead = f"⚪ **Forecast confidence: UNVERIFIED** for {target_location.name}."

            reply_text = (
                f"{lead}\n\n"
                f"I compared {scope} using the available weather providers. **{summary}**\n\n"
                + ("\n".join(f"• {reason}" for reason in reasons) if reasons else "• No secondary-provider comparison was available.")
                + "\n\n"
                "**Important:** this is a source-agreement confidence signal, not a claim that the forecast is a specific percentage accurate. "
                "True forecast accuracy requires comparing saved forecasts with later observations over many locations and dates."
            )
            card_type = None
        else:
            reply_text, card_type = ResponseService.generate_response(
                query=parsed,
                report=weather_report,
                weather_service=self.weather_service
            )

        localized = LanguageService.localize(
            parsed.intent,
            {
                "loc": target_location.name,
                "cur": weather_report.current,
                "forecast": weather_report.forecast,
                "target_date": parsed.target_date,
                "verification": verification,
            },
            parsed.language
        )
        if localized:
            reply_text = localized

        # AUTOMATIC CREDIBILITY INDICATOR
        # Every weather answer gets one visible credibility signal. It is NOT
        # limited to "will it rain tomorrow" or any other special sentence.
        # If a secondary provider is unavailable, show UNVERIFIED instead of
        # silently hiding the signal.
        if parsed.intent not in {"greeting", "help"}:
            level = verification.get("level", "UNVERIFIED")
            summary = verification.get("summary", "")

            if parsed.intent == "forecast_7day":
                label = "Forecast data confidence"
            elif verification.get("mode") == "forecast" or parsed.target_date in {
                "tomorrow", "day_after_tomorrow", "monday", "tuesday",
                "wednesday", "thursday", "friday", "saturday", "sunday"
            }:
                label = "Forecast confidence"
            else:
                label = "Weather data confidence"

            marker = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(level, "⚪")
            reply_text = f"{reply_text.rstrip()}\n\n{marker} **{label}: {level}** — {summary}"

        # Save the exact verification snapshot so a later "why confidence?"
        # question explains the same indicator instead of recalculating it.
        if parsed.intent != "forecast_confidence":
            # Cache the exact result, including UNVERIFIED results, so a later
            # proof question explains the same snapshot instead of performing
            # a new verification request and changing the displayed state.
            session.last_verification = verification
            session.last_verification_target_date = verification_target_date
            if parsed.intent == "forecast_7day" and len(weather_report.forecast) > 1:
                session.last_forecast_anchor_date = weather_report.forecast[1].date

        # Only attach weather_data payload when the UI needs to render a card
        weather_payload = weather_report if card_type in ("forecast", "overview") else None

        return ChatResponse(
            reply=reply_text,
            weather_data=weather_payload,
            location=target_location,
            intent=parsed.intent,
            card_type=card_type,
            verification=verification
        )
