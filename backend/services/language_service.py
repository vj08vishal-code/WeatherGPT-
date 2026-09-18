"""Lightweight language detection and response localization for WeatherGPT.

No external translation service is required. The detector combines Unicode-script
signals with common weather phrases, and the response templates keep numeric
weather facts from Open-Meteo unchanged while translating the surrounding text.
"""
import re
from typing import Optional


class LanguageService:
    SUPPORTED = {"en", "hi", "mr", "ta", "te", "kn", "bn", "ml"}

    @classmethod
    def detect(cls, text: str) -> str:
        if not text:
            return "en"
        # Strong Unicode script signals.
        if re.search(r"[\u0900-\u097F]", text):
            # Hindi/Marathi share Devanagari; distinguish by common Marathi forms.
            if re.search(r"\b(आहे|मध्ये|उद्या|पाऊस|हवामान|काय)\b", text):
                return "mr"
            return "hi"
        if re.search(r"[\u0B80-\u0BFF]", text): return "ta"
        if re.search(r"[\u0C00-\u0C7F]", text): return "te"
        if re.search(r"[\u0C80-\u0CFF]", text): return "kn"
        if re.search(r"[\u0980-\u09FF]", text): return "bn"
        if re.search(r"[\u0D00-\u0D7F]", text): return "ml"

        # Useful for common Romanized Indian-language questions typed in English letters.
        low = text.lower()
        roman_scores = {
            "hi": ["ka mausam", "kaise hai", "barish", "baarish", "kal", "aaj", "chahiye", "chahiye kya", "le jana", "nikalna"],
            "mr": ["havaman", "pavs", "paus", "udya", "aaj", "ghyava", "ghyave", "pahije", "mausam kasa"],
            "ta": ["vaanilai", "mazhai", "mazha", "malai", "naalai", "naalaiku", "nalaiku", "naliku", "indru", "venuma", "eppadi", "kudai", "iruka"],
            "te": ["vaataavaranam", "varsham", "repu", "ivala", "godugu", "ela undi"],
            "kn": ["mauna", "male", "naale", "ivattu", "chhatri", "hege ide"],
            "bn": ["abohawa", "brishti", "kal", "aj", "chata", "kemon"],
            "ml": ["kaalavastha", "mazha", "nale", "innu", "kuda", "engane"],
        }
        scores = {k: sum(1 for p in ps if p in low) for k, ps in roman_scores.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "en"

    @classmethod
    def localize(cls, intent: str, data: dict, language: str) -> Optional[str]:
        if language == "en":
            return None
        loc = data.get("loc", "your location")
        cur = data.get("cur")
        f = data.get("forecast")
        if not cur:
            return None
        temp = cur.temperature; feels = cur.feels_like; cond = cur.condition
        prob = cur.precipitation_probability; wind = cur.wind_speed; hum = cur.humidity
        tmw = f[1] if f and len(f) > 1 else None

        # Localized templates for the most useful demo intents.
        if intent == "temperature":
            return {
                "hi": f"🌡️ **{loc} में अभी तापमान {temp}°C है**, और महसूस {feels}°C हो रहा है ({cond})।",
                "mr": f"🌡️ **{loc} मध्ये सध्या तापमान {temp}°C आहे**, आणि जाणवणारे तापमान {feels}°C आहे ({cond}).",
                "ta": f"🌡️ **{loc} இல் தற்போது வெப்பநிலை {temp}°C**, உணரப்படும் வெப்பநிலை {feels}°C ({cond}).",
                "te": f"🌡️ **{loc}లో ప్రస్తుతం ఉష్ణోగ్రత {temp}°C**, అనిపించే ఉష్ణోగ్రత {feels}°C ({cond}).",
                "kn": f"🌡️ **{loc} ನಲ್ಲಿ ಈಗ ತಾಪಮಾನ {temp}°C**, ಅನುಭವವಾಗುವ ತಾಪಮಾನ {feels}°C ({cond}).",
                "bn": f"🌡️ **{loc}-এ এখন তাপমাত্রা {temp}°C**, অনুভূত তাপমাত্রা {feels}°C ({cond})।",
                "ml": f"🌡️ **{loc} ൽ ഇപ്പോഴത്തെ താപനില {temp}°C**, അനുഭവപ്പെടുന്നത് {feels}°C ({cond}).",
            }.get(language)
        if intent in ("umbrella_recommendation", "rain_tomorrow", "weather_tomorrow") and tmw:
            if intent == "umbrella_recommendation":
                p = tmw.precipitation_probability_max
                yes = p >= 50
                return {
                    "hi": f"☔ **{'कल छाता साथ ले जाना बेहतर रहेगा' if yes else 'कल छाते की जरूरत कम है'}।** {loc} में कल बारिश की संभावना **{p}%** है और स्थिति **{tmw.condition}** रहेगी।",
                    "mr": f"☔ **{'उद्या छत्री सोबत ठेवणे चांगले' if yes else 'उद्या छत्रीची गरज कमी आहे'}।** {loc} मध्ये पावसाची शक्यता **{p}%** आहे आणि स्थिती **{tmw.condition}** राहण्याची शक्यता आहे.",
                    "ta": f"☔ **{'நாளை குடையை எடுத்துச் செல்வது நல்லது' if yes else 'நாளை குடை தேவையில்லை'}**. {loc} இல் மழைக்கான வாய்ப்பு **{p}%**, நிலை **{tmw.condition}**.",
                    "te": f"☔ **{'రేపు గొడుగు తీసుకెళ్లడం మంచిది' if yes else 'రేపు గొడుగు అవసరం తక్కువ'}**. {loc}లో వర్షం అవకాశం **{p}%**, పరిస్థితి **{tmw.condition}**.",
                    "kn": f"☔ **{'ನಾಳೆ ಛತ್ರಿ ತೆಗೆದುಕೊಂಡು ಹೋಗುವುದು ಉತ್ತಮ' if yes else 'ನಾಳೆ ಛತ್ರಿ ಅಗತ್ಯ ಕಡಿಮೆ'}**. {loc} ನಲ್ಲಿ ಮಳೆಯ ಸಾಧ್ಯತೆ **{p}%**, ಪರಿಸ್ಥಿತಿ **{tmw.condition}**.",
                    "bn": f"☔ **{'আগামীকাল ছাতা সঙ্গে নেওয়া ভালো' if yes else 'আগামীকাল ছাতার প্রয়োজন কম'}**। {loc}-এ বৃষ্টির সম্ভাবনা **{p}%**, অবস্থা **{tmw.condition}**।",
                    "ml": f"☔ **{'നാളെ കുട കൊണ്ടുപോകുന്നത് നല്ലതാണ്' if yes else 'നാളെ കുടയുടെ ആവശ്യം കുറവാണ്'}**. {loc} ൽ മഴയ്ക്കുള്ള സാധ്യത **{p}%**, അവസ്ഥ **{tmw.condition}**.",
                }.get(language)
            if intent == "rain_tomorrow":
                p = tmw.precipitation_probability_max
                return {
                    "hi": f"🌧️ **{loc} में कल बारिश की संभावना {p}% है**, और मौसम **{tmw.condition}** रहेगा।",
                    "mr": f"🌧️ **{loc} मध्ये उद्या पावसाची शक्यता {p}% आहे**, आणि हवामान **{tmw.condition}** राहील.",
                    "ta": f"🌧️ **{loc} இல் நாளை மழைக்கான வாய்ப்பு {p}%**, வானிலை **{tmw.condition}** இருக்கும்.",
                    "te": f"🌧️ **{loc}లో రేపు వర్షం వచ్చే అవకాశం {p}%**, వాతావరణం **{tmw.condition}**గా ఉంటుంది.",
                    "kn": f"🌧️ **{loc} ನಲ್ಲಿ ನಾಳೆ ಮಳೆಯ ಸಾಧ್ಯತೆ {p}%**, ಹವಾಮಾನ **{tmw.condition}** ಇರುತ್ತದೆ.",
                    "bn": f"🌧️ **{loc}-এ আগামীকাল বৃষ্টির সম্ভাবনা {p}%**, আবহাওয়া **{tmw.condition}** থাকবে।",
                    "ml": f"🌧️ **{loc} ൽ നാളെ മഴയ്ക്കുള്ള സാധ്യത {p}%**, കാലാവസ്ഥ **{tmw.condition}** ആയിരിക്കും.",
                }.get(language)
            return {
                "hi": f"📅 **{loc} में कल का मौसम:** {tmw.condition}, अधिकतम **{tmw.temp_max}°C**, न्यूनतम **{tmw.temp_min}°C**, बारिश की संभावना **{tmw.precipitation_probability_max}%**।",
                "mr": f"📅 **{loc} मधील उद्याचे हवामान:** {tmw.condition}, कमाल **{tmw.temp_max}°C**, किमान **{tmw.temp_min}°C**, पावसाची शक्यता **{tmw.precipitation_probability_max}%**.",
                "ta": f"📅 **{loc} நாளைய வானிலை:** {tmw.condition}, அதிகபட்சம் **{tmw.temp_max}°C**, குறைந்தபட்சம் **{tmw.temp_min}°C**, மழை வாய்ப்பு **{tmw.precipitation_probability_max}%**.",
                "te": f"📅 **{loc}లో రేపటి వాతావరణం:** {tmw.condition}, గరిష్ఠం **{tmw.temp_max}°C**, కనిష్ఠం **{tmw.temp_min}°C**, వర్షం అవకాశం **{tmw.precipitation_probability_max}%**.",
                "kn": f"📅 **{loc} ನಲ್ಲಿ ನಾಳೆಯ ಹವಾಮಾನ:** {tmw.condition}, ಗರಿಷ್ಠ **{tmw.temp_max}°C**, ಕನಿಷ್ಠ **{tmw.temp_min}°C**, ಮಳೆಯ ಸಾಧ್ಯತೆ **{tmw.precipitation_probability_max}%**.",
                "bn": f"📅 **{loc}-এ আগামীকালের আবহাওয়া:** {tmw.condition}, সর্বোচ্চ **{tmw.temp_max}°C**, সর্বনিম্ন **{tmw.temp_min}°C**, বৃষ্টির সম্ভাবনা **{tmw.precipitation_probability_max}%**।",
                "ml": f"📅 **{loc} ലെ നാളത്തെ കാലാവസ്ഥ:** {tmw.condition}, കൂടിയത് **{tmw.temp_max}°C**, കുറഞ്ഞത് **{tmw.temp_min}°C**, മഴയുടെ സാധ്യത **{tmw.precipitation_probability_max}%**.",
            }.get(language)
        if intent == "sunscreen_recommendation":
            target = tmw if tmw and data.get("target_date") == "tomorrow" else None
            uv = getattr(target, "uv_index_max", None) if target else getattr(data.get("cur"), "uv_index", None)
            when = "tomorrow" if target else "today"
            uv_text = f"{uv}" if uv is not None else "unavailable"
            messages = {
                "hi": f"☀️ **{when} {loc} में sunscreen पर विचार करें।** अनुमानित UV Index **{uv_text}** है। बाहर लंबे समय तक रहने पर धूप से बचाव रखना उपयोगी है।",
                "mr": f"☀️ **{when} {loc} मध्ये sunscreen वापरण्याचा विचार करा.** अंदाजे UV Index **{uv_text}** आहे. बराच वेळ बाहेर राहणार असल्यास सूर्यापासून संरक्षण ठेवा.",
                "ta": f"☀️ **{when} {loc} இல் sunscreen பயன்படுத்துவது நல்லது.** எதிர்பார்க்கப்படும் UV Index **{uv_text}**. நீண்ட நேரம் வெளியே இருப்பின் வெயிலிலிருந்து பாதுகாப்பு எடுத்துக்கொள்ளுங்கள்.",
                "te": f"☀️ **{when} {loc}లో sunscreen ఉపయోగించడం మంచిది.** అంచనా UV Index **{uv_text}**. ఎక్కువసేపు బయట ఉంటే సూర్యరశ్మి నుంచి రక్షణ తీసుకోండి.",
                "kn": f"☀️ **{when} {loc} ನಲ್ಲಿ sunscreen ಬಳಸುವುದು ಒಳ್ಳೆಯದು.** ನಿರೀಕ್ಷಿತ UV Index **{uv_text}**. ಹೆಚ್ಚು ಸಮಯ ಹೊರಗಿದ್ದರೆ ಸೂರ್ಯನಿಂದ ರಕ್ಷಣೆ ಪಡೆಯಿರಿ.",
                "bn": f"☀️ **{when} {loc}-এ sunscreen ব্যবহার করার কথা ভাবুন।** প্রত্যাশিত UV Index **{uv_text}**। দীর্ঘ সময় বাইরে থাকলে সূর্য থেকে সুরক্ষা নিন।",
                "ml": f"☀️ **{when} {loc} ൽ sunscreen ഉപയോഗിക്കുന്നത് നല്ലതാണ്.** പ്രതീക്ഷിക്കുന്ന UV Index **{uv_text}** ആണ്. കൂടുതൽ സമയം പുറത്താണെങ്കിൽ സൂര്യപ്രകാശത്തിൽ നിന്ന് സംരക്ഷണം എടുക്കുക.",
            }
            return messages.get(language)

        if intent == "sunglasses_recommendation":
            target = tmw if tmw and data.get("target_date") == "tomorrow" else None
            condition = (target.condition if target else cond).lower()
            sunny = any(x in condition for x in ["clear", "mainly clear", "partly cloudy"])
            p = target.precipitation_probability_max if target else prob
            yes = sunny and p < 40
            return {
                "hi": f"🕶️ **{'हाँ, धूप के लिए sunglasses रखना अच्छा रहेगा' if yes else 'धूप के चश्मे की जरूरत कम लगती है'}।** मौसम {target.condition if target else cond} है और बारिश की संभावना **{p}%** है।",
                "mr": f"🕶️ **{'हो, उन्हासाठी sunglasses ठेवणे चांगले' if yes else 'sunglasses ची गरज कमी वाटते'}।** हवामान {target.condition if target else cond} आहे आणि पावसाची शक्यता **{p}%** आहे.",
                "ta": f"🕶️ **{'ஆம், வெயிலுக்காக sunglasses எடுத்துச் செல்வது நல்லது' if yes else 'sunglasses தேவையில்லை'}**. நிலை {target.condition if target else cond}, மழை வாய்ப்பு **{p}%**.",
                "te": f"🕶️ **{'అవును, ఎండ కోసం sunglasses తీసుకెళ్లడం మంచిది' if yes else 'sunglasses అవసరం తక్కువ'}**. పరిస్థితి {target.condition if target else cond}, వర్షం అవకాశం **{p}%**.",
                "kn": f"🕶️ **{'ಹೌದು, ಬಿಸಿಲಿಗಾಗಿ sunglasses ತೆಗೆದುಕೊಂಡು ಹೋಗುವುದು ಉತ್ತಮ' if yes else 'sunglasses ಅಗತ್ಯ ಕಡಿಮೆ'}**. ಪರಿಸ್ಥಿತಿ {target.condition if target else cond}, ಮಳೆಯ ಸಾಧ್ಯತೆ **{p}%**.",
                "bn": f"🕶️ **{'হ্যাঁ, রোদের জন্য sunglasses সঙ্গে রাখা ভালো' if yes else 'sunglasses-এর প্রয়োজন কম'}**। অবস্থা {target.condition if target else cond}, বৃষ্টির সম্ভাবনা **{p}%**।",
                "ml": f"🕶️ **{'അതെ, വെയിലിനായി sunglasses കൊണ്ടുപോകുന്നത് നല്ലതാണ്' if yes else 'sunglasses ആവശ്യം കുറവാണ്'}**. അവസ്ഥ {target.condition if target else cond}, മഴയുടെ സാധ്യത **{p}%**.",
            }.get(language)
        if intent in ("rain", "rain_probability"):
            return {
                "hi": f"🌧️ **{loc} में बारिश की संभावना {prob}% है** और अभी मौसम {cond} है।",
                "mr": f"🌧️ **{loc} मध्ये पावसाची शक्यता {prob}% आहे** आणि सध्या हवामान {cond} आहे.",
                "ta": f"🌧️ **{loc} இல் மழைக்கான வாய்ப்பு {prob}%**, தற்போது நிலை {cond}.",
                "te": f"🌧️ **{loc}లో వర్షం అవకాశం {prob}%**, ప్రస్తుతం పరిస్థితి {cond}.",
                "kn": f"🌧️ **{loc} ನಲ್ಲಿ ಮಳೆಯ ಸಾಧ್ಯತೆ {prob}%**, ಈಗಿನ ಪರಿಸ್ಥಿತಿ {cond}.",
                "bn": f"🌧️ **{loc}-এ বৃষ্টির সম্ভাবনা {prob}%**, বর্তমানে অবস্থা {cond}।",
                "ml": f"🌧️ **{loc} ൽ മഴയ്ക്കുള്ള സാധ്യത {prob}%**, ഇപ്പോഴത്തെ അവസ്ഥ {cond}."
            }.get(language)

        if intent == "umbrella_recommendation" and not tmw:
            yes = cur.is_raining or prob >= 50
            return {
                "hi": f"☔ **{'हाँ, छाता साथ रखना बेहतर है' if yes else 'अभी छाते की जरूरत कम है'}।** {loc} में बारिश की संभावना **{prob}%** है।",
                "mr": f"☔ **{'हो, छत्री सोबत ठेवणे चांगले' if yes else 'सध्या छत्रीची गरज कमी आहे'}।** {loc} मध्ये पावसाची शक्यता **{prob}%** आहे.",
                "ta": f"☔ **{'ஆம், குடையை எடுத்துச் செல்வது நல்லது' if yes else 'இப்போது குடை தேவையில்லை'}**. {loc} இல் மழை வாய்ப்பு **{prob}%**.",
                "te": f"☔ **{'అవును, గొడుగు తీసుకెళ్లడం మంచిది' if yes else 'ఇప్పుడు గొడుగు అవసరం తక్కువ'}**. {loc}లో వర్షం అవకాశం **{prob}%**.",
                "kn": f"☔ **{'ಹೌದು, ಛತ್ರಿ ತೆಗೆದುಕೊಂಡು ಹೋಗುವುದು ಉತ್ತಮ' if yes else 'ಈಗ ಛತ್ರಿ ಅಗತ್ಯ ಕಡಿಮೆ'}**. {loc} ನಲ್ಲಿ ಮಳೆಯ ಸಾಧ್ಯತೆ **{prob}%**.",
                "bn": f"☔ **{'হ্যাঁ, ছাতা সঙ্গে রাখা ভালো' if yes else 'এখন ছাতার প্রয়োজন কম'}**। {loc}-এ বৃষ্টির সম্ভাবনা **{prob}%**।",
                "ml": f"☔ **{'അതെ, കുട കൊണ്ടുപോകുന്നത് നല്ലതാണ്' if yes else 'ഇപ്പോൾ കുടയുടെ ആവശ്യം കുറവാണ്'}**. {loc} ൽ മഴയുടെ സാധ്യത **{prob}%**."
            }.get(language)

        if intent == "current_weather":
            return {
                "hi": f"📍 **{loc} का मौसम:** {cond}, तापमान **{temp}°C**, महसूस **{feels}°C**, नमी **{hum}%**, हवा **{wind} km/h**, बारिश की संभावना **{prob}%**।",
                "mr": f"📍 **{loc} चे हवामान:** {cond}, तापमान **{temp}°C**, जाणवणारे **{feels}°C**, आर्द्रता **{hum}%**, वारा **{wind} km/h**, पावसाची शक्यता **{prob}%**.",
                "ta": f"📍 **{loc} வானிலை:** {cond}, வெப்பநிலை **{temp}°C**, உணரப்படும் **{feels}°C**, ஈரப்பதம் **{hum}%**, காற்று **{wind} km/h**, மழை வாய்ப்பு **{prob}%**.",
                "te": f"📍 **{loc} వాతావరణం:** {cond}, ఉష్ణోగ్రత **{temp}°C**, అనిపించేది **{feels}°C**, తేమ **{hum}%**, గాలి **{wind} km/h**, వర్షం అవకాశం **{prob}%**.",
                "kn": f"📍 **{loc} ಹವಾಮಾನ:** {cond}, ತಾಪಮಾನ **{temp}°C**, ಅನುಭವ **{feels}°C**, ಆರ್ದ್ರತೆ **{hum}%**, ಗಾಳಿ **{wind} km/h**, ಮಳೆಯ ಸಾಧ್ಯತೆ **{prob}%**.",
                "bn": f"📍 **{loc}-এর আবহাওয়া:** {cond}, তাপমাত্রা **{temp}°C**, অনুভূত **{feels}°C**, আর্দ্রতা **{hum}%**, বাতাস **{wind} km/h**, বৃষ্টির সম্ভাবনা **{prob}%**।",
                "ml": f"📍 **{loc} ലെ കാലാവസ്ഥ:** {cond}, താപനില **{temp}°C**, അനുഭവപ്പെടുന്നത് **{feels}°C**, ഈർപ്പം **{hum}%**, കാറ്റ് **{wind} km/h**, മഴയുടെ സാധ്യത **{prob}%**.",
            }.get(language)
        return None
