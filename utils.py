import logging
import random

# 🔧 Configure Central Logging (safe for small apps)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_logger(name):
    return logging.getLogger(name)

logger = get_logger("Utils")


# 🌍 Multi-lingual Error Responses
ERROR_RESPONSES = {
    "en": [
        "I couldn't process that command. Try again.",
        "I didn’t understand that. Please rephrase."
    ],
    "hi": [
        "मैं उस कमांड को समझ नहीं पायी। कृपया फिर से कहें।",
        "मुझे समझ नहीं आया। कृपया दोबारा बताएं।"
    ],
    "te": [
        "ఆ ఆదేశాన్ని అర్థం చేసుకోలేకపోయాను. దయచేసి మళ్లీ చెప్పండి.",
        "నాకు అర్థం కాలేదు. దయచేసి మళ్లీ చెప్పండి."
    ]
}


def get_error_response(lang_code):
    return random.choice(ERROR_RESPONSES.get(lang_code, ERROR_RESPONSES["en"]))


# 🧠 Structured Response Builder (USE THIS IN intent.py)
def build_response(intent: str, lang: str, **kwargs) -> str:
    responses = {
        "greeting": {
            "en": ["Hello, I am Aura. How can I help you?"],
            "hi": ["नमस्ते, मैं ऑरा हूँ। मैं आपकी कैसे मदद कर सकती हूँ?"],
            "te": ["నమస్కారం, నేను ఆరా. నేను మీకు ఎలా సహాయపడగలను?"]
        },

        "time": {
            "en": [f"The current time is {kwargs.get('time')}."],
            "hi": [f"वर्तमान समय {kwargs.get('time')} है।"],
            "te": [f"ప్రస్తుత సమయం {kwargs.get('time')}."]
        },

        "open_web": {
            "en": [f"Opening {kwargs.get('target')}"],
            "hi": [f"{kwargs.get('target')} खोल रही हूँ"],
            "te": [f"{kwargs.get('target')} తెరుస్తున్నాను"]
        },

        "open_app_success": {
            "en": [f"{kwargs.get('target')} opened successfully"],
            "hi": [f"{kwargs.get('target')} सफलतापूर्वक शुरू किया गया"],
            "te": [f"{kwargs.get('target')} విజయవంతంగా ప్రారంభించబడింది"]
        },

        "open_app_fail": {
            "en": [f"Could not open {kwargs.get('target')}"],
            "hi": [f"{kwargs.get('target')} नहीं खोल सकी"],
            "te": [f"{kwargs.get('target')} తెరవలేకపోయాను"]
        },

        "search_fallback": {
            "en": [f"Searching for {kwargs.get('target')}"],
            "hi": [f"{kwargs.get('target')} के लिए खोज रही हूँ"],
            "te": [f"{kwargs.get('target')} కోసం వెతుకుతున్నాను"]
        }
    }

    intent_group = responses.get(intent)

    if not intent_group:
        logger.warning(f"Unknown intent: {intent}")
        return get_error_response(lang)

    lang_opts = intent_group.get(lang, intent_group.get("en"))
    return random.choice(lang_opts)