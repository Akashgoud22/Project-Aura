import os
import json
import asyncio
from groq import Groq
from backend.utils import get_logger
from backend.models import User

logger = get_logger("Planner")

async def generate_plan(command: str, user: User, lang: str) -> list:
    """
    Uses LLM to break down a complex command into a sequence of actionable intents.
    Returns a list of dicts: [{"intent": "open_web", "payload": "youtube.com"}, ...]
    """
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key or groq_api_key == "YOUR_GROQ_API_KEY_HERE":
        logger.error("No GROQ API KEY for planner")
        return []

    client = Groq(api_key=groq_api_key)

    system_prompt = f"""
    You are the task planner for Aura AI. The user will give a command.
    If the command is complex or multi-step (e.g., 'play a song on youtube'), break it down into a JSON array of steps.
    Valid intents:
    - open_web: payload is the domain (e.g. google.com or youtube.com)
    - play_youtube: payload is the search query
    - search_web: payload is the search query
    - open_app: payload is the app name
    - install_app: payload is the app name
    - speak: payload is what to say to the user
    
    If it's a simple conversation, just return a single 'speak' intent.
    Output ONLY valid JSON array. Example:
    [
      {{"intent": "play_youtube", "payload": "Lofi hip hop"}}
    ]
    Speech must be in language code: {lang}.
    """

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.chat.completions.create,
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": command}
                ],
                temperature=0.1
            ),
            timeout=12
        )
        
        output = response.choices[0].message.content.strip()
        if output.startswith("```json"):
            output = output[7:-3]
        if output.startswith("```"):
            output = output[3:-3]
            
        plan = json.loads(output)
        if isinstance(plan, list):
            return plan
        return [plan]
    except Exception as e:
        logger.error(f"Planner failed: {e}")
        return []
