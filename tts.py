import uuid
import base64
import os
import asyncio
import re
import edge_tts
from backend.utils import get_logger

logger = get_logger("TTS")

VOICES = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-MadhurNeural",
    "te": "te-IN-ShrutiNeural"
}

def get_voice(lang_code: str) -> str:
    return VOICES.get(lang_code, "en-US-AriaNeural")

def clean_text_for_tts(text: str) -> str:
    # Remove URLs
    text = re.sub(r'http\S+|www\.\S+', '', text)
    # Remove markdown symbols
    text = re.sub(r'[*#`]', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def chunk_text(text: str, lang: str = "en") -> list[str]:
    max_length = 300 if lang in ["hi", "te"] else 150
    chunks = []
    # Split by sentence terminology, keeping the punctuation attached to words
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    current_chunk = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += (sentence + " ")
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
                
            if len(sentence) > max_length:
                # Force slice large sentences
                words = sentence.split(' ')
                sub_chunk = ""
                for word in words:
                    if len(sub_chunk) + len(word) <= max_length:
                         sub_chunk += (word + " ")
                    else:
                         chunks.append(sub_chunk.strip())
                         sub_chunk = word + " "
                current_chunk = sub_chunk
            else:
                current_chunk = sentence + " "
                
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks


async def generate_speech(text: str, voice: str, lang: str = "en") -> str:
    """Robust TTS with timeout, validation, and cleanup"""

    # 🛑 Prevent useless calls
    if not text or not text.strip():
        logger.warning("Empty text received for TTS")
        return None

    temp_file = f"temp_{uuid.uuid4()}.mp3"

    try:
        # Slightly faster speech reduces the laggy feel without becoming too sharp.
        rate_val = "-5%" if lang in ["hi", "te"] else "+18%"
        
        communicate = edge_tts.Communicate(text, voice, rate=rate_val)

        # ⏱️ Timeout protection (important)
        await asyncio.wait_for(communicate.save(temp_file), timeout=10)

        # 📦 Read file safely
        def read_encode():
            with open(temp_file, "rb") as audio_file:
                return base64.b64encode(audio_file.read()).decode("utf-8")

        audio_b64 = await asyncio.to_thread(read_encode)
        return audio_b64

    except asyncio.TimeoutError:
        logger.error("TTS generation timed out")
        return None

    except Exception as e:
        logger.error(f"TTS failed: {e}")
        return None

    finally:
        # 🧹 Cleanup
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception as e:
                logger.error(f"Failed to delete temp file {temp_file}: {e}")
