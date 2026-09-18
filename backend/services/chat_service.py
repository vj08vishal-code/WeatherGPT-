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
from ..models.schemas import ChatRequest, ChatResponse, Location
from ..weather.open_meteo import OpenMeteoClient
from .location_service import LocationService
from .query_service import QueryService
from .weather_service import WeatherService
from .response_service import ResponseService
from .language_service import LanguageService
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
        if parsed.target_date and parsed.target_date not in ("today", "now"):
            # For any future-date request (tomorrow, day-after-tomorrow, or a
            # weekday), verify the same forecast day that the answer refers to.
            if parsed.target_date == "tomorrow" and len(weather_report.forecast) > 1:
                verification_target_date = weather_report.forecast[1].date
            elif parsed.target_date == "day_after_tomorrow" and len(weather_report.forecast) > 2:
                verification_target_date = weather_report.forecast[2].date
            elif parsed.target_date in {
                "monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday"
            }:
                wanted = parsed.target_date[:3].lower()
                for item in weather_report.forecast:
                    if item.day.lower().startswith(wanted):
                        verification_target_date = item.date
                        break
        elif parsed.intent == "forecast_7day" and len(weather_report.forecast) > 1:
            # A weekly request covers multiple days. Cross-check the first
            # future day as a representative signal and label it as such.
            verification_target_date = weather_report.forecast[1].date

        # Reuse the exact verification snapshot for a confidence follow-up.
        # This makes the indicator stable: "why this confidence?" explains the
        # same evidence that produced the previous indicator instead of calling
        # providers again and potentially changing the level.
        session = QueryService.get_session(request.session_id)
        if (
            parsed.intent == "forecast_confidence"
            and session.last_verification is not None
        ):
            verification = session.last_verification
        else:
            verification = self.verification_service.verify(
                location=target_location,
                report=weather_report,
                target_date=verification_target_date
            )
            # Save the exact snapshot for the next confidence explanation.
            session.last_verification = verification
            session.last_verification_target_date = verification_target_date

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

        # Credibility indicator: every successful weather answer gets a visible
        # source-agreement signal in the text as well as the UI badge. This keeps
        # the indicator visible even if a client does not render rich UI fields.
        if parsed.intent != "forecast_confidence" and verification:
            level = verification.get("level", "UNVERIFIED")
            icon = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(level, "⚪")
            mode_label = "Forecast confidence" if verification.get("mode") == "forecast" else "Data confidence"
            agreement_total = verification.get("agreement_total", 0)
            agreement_count = verification.get("agreement_count", 0)
            if agreement_total:
                signal_text = f"{agreement_count}/{agreement_total} comparison signals agree"
            else:
                signal_text = "cross-check unavailable"
            sources = " + ".join(verification.get("sources", []))
            source_text = f" · Sources: {sources}" if sources else ""
            reply_text += (
                f"\n\n{icon} **{mode_label}: {level}** — {signal_text}{source_text}."
            )

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
