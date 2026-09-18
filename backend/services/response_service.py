"""
response_service.py - Precise & Actionable Weather Response Generator (Phase 2).
Generates concise, natural conversational responses matching ONLY the scope of the user's intent.
Enforces the critical rule: no unsolicited 7-day forecast dumps on targeted questions.
"""

from typing import Tuple, Optional
from ..models.schemas import WeatherReport, ParsedQuery
from .weather_service import WeatherService


class ResponseService:
    """Generates natural language replies and sets appropriate UI card attachments."""

    @classmethod
    def generate_response(
        cls,
        query: ParsedQuery,
        report: WeatherReport,
        weather_service: WeatherService
    ) -> Tuple[str, Optional[str]]:
        """
        Returns:
            Tuple[reply_text: str, card_type: Optional[str]]
            card_type can be None (text-only), 'forecast' (7-day cards), or 'overview' (full card).
        """
        intent = query.intent
        loc_name = report.location.name
        cur = report.current
        forecast = report.forecast or []

        # Safety-first context used by actionable recommendations.
        target_advice = forecast[1] if query.target_date == "tomorrow" and len(forecast) > 1 else None
        advice_condition = (target_advice.condition if target_advice else cur.condition)
        advice_prob = (target_advice.precipitation_probability_max if target_advice else cur.precipitation_probability)
        severe_weather = any(
            word in advice_condition.lower()
            for word in ["thunderstorm", "lightning", "hail", "violent"]
        )

        # ====================================================================
        # 1. TEMPERATURE & FEELS LIKE
        # ====================================================================
        if intent == "temperature":
            reply = (
                f"🌡️ It's currently **{cur.temperature}°C** in **{loc_name}**, "
                f"with a feels-like temperature of **{cur.feels_like}°C** ({cur.condition})."
            )
            return reply, None

        if intent == "feels_like":
            reply = (
                f"🌡️ In **{loc_name}**, the actual temperature is **{cur.temperature}°C**, "
                f"but it feels like **{cur.feels_like}°C** due to current humidity ({cur.humidity}%)."
            )
            return reply, None

        # ====================================================================
        # 2. RAIN & PRECIPITATION (TODAY / CURRENT)
        # ====================================================================
        if intent in ["rain", "rain_probability"]:
            prob = cur.precipitation_probability
            if cur.is_raining:
                reply = (
                    f"🌧️ **Yes, it is currently raining in {loc_name}.**\n\n"
                    f"Current condition is **{cur.condition}** with approximately **{cur.precipitation} mm** of precipitation. "
                    f"Carry an umbrella if you're stepping outside! ☔"
                )
            elif prob >= 60:
                reply = (
                    f"🌧️ There is a **{prob}% chance of precipitation today** in **{loc_name}** ({cur.condition}). "
                    f"Rain is likely later today. Carry an umbrella if you're going out. ☔"
                )
            elif prob >= 25:
                reply = (
                    f"🌦️ There is a **{prob}% chance of precipitation today** in **{loc_name}**. "
                    f"Current condition is **{cur.condition}**. A light passing shower is possible."
                )
            else:
                reply = (
                    f"☀️ **No rain expected right now in {loc_name}.**\n\n"
                    f"Precipitation probability is low at **{prob}%** with **{cur.condition}**."
                )
            return reply, None

        # ====================================================================
        # 3. UMBRELLA RECOMMENDATION
        # ====================================================================
        if intent == "umbrella_recommendation":
            # If the user asked about tomorrow, use tomorrow's forecast rather than current conditions.
            if query.target_date == "tomorrow" and len(forecast) > 1:
                tmw = forecast[1]
                prob = tmw.precipitation_probability_max
                if severe_weather:
                    reply = (
                        f"⚠️ **Yes, carry rain protection tomorrow, but safety comes first.**\n\n"
                        f"There is a **{prob}% precipitation probability** in **{loc_name}**, with **{tmw.condition}** expected. "
                        f"If lightning or a thunderstorm occurs, seek proper shelter rather than relying on an umbrella outdoors."
                    )
                elif prob >= 50:
                    reply = (
                        f"☔ **Yes, take an umbrella tomorrow.**\n\n"
                        f"There is a **{prob}% precipitation probability** in **{loc_name}** tomorrow, with **{tmw.condition}** expected."
                    )
                elif prob >= 25:
                    reply = (
                        f"🌂 **An umbrella might come in handy tomorrow.**\n\n"
                        f"There is a **{prob}% precipitation probability** in **{loc_name}** tomorrow, with **{tmw.condition}** expected."
                    )
                else:
                    reply = (
                        f"☀️ **You probably won't need an umbrella tomorrow in {loc_name}.**\n\n"
                        f"Rain probability is only **{prob}%**, with **{tmw.condition}** expected."
                    )
                return reply, None

            prob = cur.precipitation_probability
            if cur.is_raining:
                reply = (
                    f"☔ **Yes, definitely take an umbrella!**\n\n"
                    f"It is actively raining in **{loc_name}** right now ({cur.condition}, {cur.precipitation} mm)."
                )
            elif prob >= 50:
                reply = (
                    f"☔ **Yes, it's recommended to carry an umbrella.**\n\n"
                    f"There is a **{prob}% precipitation probability** today in **{loc_name}** ({cur.condition})."
                )
            elif prob >= 25:
                reply = (
                    f"🌂 **An umbrella might come in handy.**\n\n"
                    f"There is a moderate **{prob}% chance of rain** today in **{loc_name}**. Keep one nearby just in case."
                )
            else:
                reply = (
                    f"☀️ **No umbrella needed today in {loc_name}.**\n\n"
                    f"The chance of rain is only **{prob}%** with **{cur.condition}**."
                )
            return reply, None

        # ====================================================================
        # 3B. SUN PROTECTION RECOMMENDATIONS
        # ====================================================================
        if intent == "sunscreen_recommendation":
            target = forecast[1] if query.target_date == "tomorrow" and len(forecast) > 1 else None
            uv = target.uv_index_max if target else cur.uv_index
            when = "tomorrow" if target else "today"
            if uv is None:
                return (f"☀️ I couldn't get the UV Index for {loc_name} right now, so I can't give a UV-based recommendation. Check the forecast again shortly.", None)
            if uv >= 6:
                level = "high" if uv < 8 else "very high"
                if severe_weather:
                    advice = (
                        "UV may still be high during brighter daytime periods, but thunderstorms are the priority. "
                        "Avoid staying outdoors during lightning; use sun protection only when it is safe to be outside."
                    )
                else:
                    advice = "Sun protection is advisable, especially if you'll be outside for an extended period."
            elif uv >= 3:
                level = "moderate"
                advice = "Consider sun protection if you'll be outside for an extended period."
            else:
                level = "low"
                advice = "UV exposure is expected to be relatively low."
            return (
                f"☀️ **For {when} in {loc_name}, the maximum UV Index is expected to be {uv} ({level}).**\n\n{advice}",
                None
            )

        if intent == "sunglasses_recommendation":
            target = forecast[1] if query.target_date == "tomorrow" and len(forecast) > 1 else None
            condition = target.condition if target else cur.condition
            rain_prob = target.precipitation_probability_max if target else cur.precipitation_probability
            uv = target.uv_index_max if target else cur.uv_index
            when = "tomorrow" if target else "today"
            if uv is not None:
                if severe_weather:
                    advice = (
                        "UV may still be high during brighter periods, but thunderstorms/rain take priority. "
                        "Avoid being outdoors during lightning; sunglasses are only useful when conditions are safe and bright."
                    )
                elif uv >= 6:
                    advice = "Sunglasses would be useful in bright daylight, and sun protection is advisable."
                elif uv >= 3:
                    advice = "Sunglasses may be useful in bright daylight."
                else:
                    advice = "UV exposure is expected to be relatively low."
                return (
                    f"🕶️ **For {when} in {loc_name}, the maximum UV Index is expected to be {uv}.**\n\n"
                    f"Forecast: **{condition}**, rain probability **{rain_prob}%**. {advice}",
                    None
                )
            return (
                f"🕶️ **For {when} in {loc_name}:** {condition}, with a **{rain_prob}%** rain probability. "
                f"UV data is unavailable right now, so I can't make a UV-based sunglasses recommendation.",
                None
            )

        # ====================================================================
        # 4. WEATHER TOMORROW
        # ====================================================================
        if intent == "weather_tomorrow":
            if len(forecast) > 1:
                tmw = forecast[1]
                rain_note = f" with a **{tmw.precipitation_probability_max}%** rain chance" if tmw.precipitation_probability_max > 0 else " with minimal rain chance"
                reply = (
                    f"📅 **Tomorrow's Weather in {loc_name} ({tmw.day}):**\n\n"
                    f"Expect **{tmw.condition}** with a daytime high of **{tmw.temp_max}°C** and a low of **{tmw.temp_min}°C**{rain_note}."
                )
            else:
                reply = f"Tomorrow's forecast for **{loc_name}** is currently being updated."
            return reply, None

        # ====================================================================
        # 5. RAIN TOMORROW
        # ====================================================================
        if intent == "rain_tomorrow":
            if len(forecast) > 1:
                tmw = forecast[1]
                prob = tmw.precipitation_probability_max
                precip = tmw.precipitation_sum
                if prob >= 50:
                    reply = (
                        f"🌧️ **Yes, rain is likely tomorrow in {loc_name}.**\n\n"
                        f"Tomorrow has a **{prob}% precipitation probability** ({precip} mm expected) with **{tmw.condition}**. "
                        f"Plan ahead and keep an umbrella ready. ☔"
                    )
                elif prob >= 20:
                    reply = (
                        f"🌦️ There is a **{prob}% chance of rain tomorrow** in **{loc_name}** ({precip} mm expected) with **{tmw.condition}**."
                    )
                else:
                    reply = (
                        f"☀️ **No significant rain expected tomorrow in {loc_name}.**\n\n"
                        f"Precipitation chance is just **{prob}%** with **{tmw.condition}**."
                    )
            else:
                reply = f"Tomorrow's precipitation outlook for **{loc_name}** is currently being updated."
            return reply, None

        # ====================================================================
        # 6. PART OF DAY (E.G. TOMORROW EVENING, MORNING, TONIGHT)
        # ====================================================================
        if intent == "part_of_day" or query.time_of_day:
            tod = query.time_of_day or "evening"
            tdate = query.target_date or "today"
            summary = weather_service.extract_part_of_day_summary(report, target_date=tdate, time_of_day=tod)

            if summary:
                day_title = "Tomorrow" if tdate == "tomorrow" else ("Tonight" if tod == "night" else "Today")
                rain_text = f"Rain chance is **{summary['precipitation_probability']}%**" if summary['precipitation_probability'] > 0 else "No rain expected"
                reply = (
                    f"🌆 **{day_title} {tod.title()} in {loc_name}:**\n\n"
                    f"• **Condition:** {summary['condition']}\n"
                    f"• **Temperature:** Approximately **{summary['temperature']}°C** (feels like **{summary['feels_like']}°C**)\n"
                    f"• **Precipitation:** {rain_text} ({summary['precipitation_sum']} mm)\n"
                    f"• **Wind:** {summary['wind_speed']} km/h"
                )
            else:
                reply = f"Hourly part-of-day data for **{loc_name}** ({tdate} {tod}) is currently unavailable."
            return reply, None

        # ====================================================================
        # 7. HUMIDITY
        # ====================================================================
        if intent == "humidity":
            h = cur.humidity
            if h >= 80:
                desc = "The air is very humid and feels heavy/muggy."
            elif h >= 55:
                desc = "Humidity is moderate and generally comfortable."
            elif h >= 30:
                desc = "Humidity is relatively low and comfortable."
            else:
                desc = "The air is quite dry."
            reply = f"💧 Relative humidity in **{loc_name}** is currently at **{h}%**. {desc}"
            return reply, None

        # ====================================================================
        # 8. WIND
        # ====================================================================
        if intent == "wind":
            w = cur.wind_speed
            dir_compass = cur.wind_direction_compass
            advice = " Wind conditions are calm." if w < 15 else (" Moderate breeze." if w < 28 else " Gusty conditions—use caution outdoors.")
            reply = f"💨 Wind in **{loc_name}** is blowing at **{w} km/h** from the **{dir_compass}** ({cur.wind_direction}°).{advice}"
            return reply, None

        # ====================================================================
        # 9. OUTDOOR ACTIVITY SUITABILITY
        # ====================================================================
        if intent == "outdoor_suitability":
            out = weather_service.evaluate_outdoor_suitability(report)
            rating_emoji = "✅" if out["rating"] == "Good" else ("⚠️" if out["rating"] == "Moderate" else "❌")
            reply = (
                f"{rating_emoji} **Outdoor Activity Suitability for {loc_name}: {out['rating']}**\n\n"
                f"{out['summary']}\n\n"
                f"• Current Temp: **{out['temperature']}°C** (Feels like {out['feels_like']}°C)\n"
                f"• Rain Chance: **{out['rain_probability']}%**\n"
                f"• Wind: **{out['wind_speed']} km/h**"
            )
            return reply, None

        # ====================================================================
        # 10. TRAVEL SUITABILITY
        # ====================================================================
        if intent == "travel_suitability":
            rain_risk = "Rain is possible during your travel period, so plan accordingly and carry an umbrella." if cur.precipitation_probability >= 40 or cur.is_raining else "No major precipitation expected to impact local travel."
            wind_note = " High winds reported—drive with care." if cur.wind_speed > 28 else ""
            reply = (
                f"🚗 **Travel Weather for {loc_name}:**\n\n"
                f"Current temperature is **{cur.temperature}°C** with **{cur.condition}**. {rain_risk}{wind_note}"
            )
            return reply, None

        # ====================================================================
        # 11. 7-DAY / WEEKLY FORECAST (Explicitly requested)
        # ====================================================================
        if intent == "forecast_7day":
            reply = (
                f"📅 Here is the **7-day weather forecast** for **{loc_name}**:\n\n"
                f"Temperatures range between **{min(f.temp_min for f in forecast)}°C** and **{max(f.temp_max for f in forecast)}°C** over the coming week."
            )
            return reply, "forecast"

        # ====================================================================
        # 12. GENERAL CURRENT WEATHER OVERVIEW
        # ====================================================================
        rain_status = f"🌧️ Raining ({cur.precipitation} mm)" if cur.is_raining else "🌤️ No rain"
        reply = (
            f"📍 **Weather in {loc_name}:**\n\n"
            f"• **Condition:** {cur.condition}\n"
            f"• **Temperature:** {cur.temperature}°C (feels like {cur.feels_like}°C)\n"
            f"• **Humidity:** {cur.humidity}%\n"
            f"• **Wind:** {cur.wind_speed} km/h {cur.wind_direction_compass}\n"
            f"• **Rain Status:** {rain_status}"
        )
        return reply, "overview"
