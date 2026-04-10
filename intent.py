import os
import json
import asyncio
from typing import Callable, Awaitable
from groq import Groq

from backend.actions import open_desktop_app, open_website, get_wikipedia_summary, fallback_search, install_app_fallback
from backend.utils import get_error_response, get_logger
from backend.models import User, AuditLog
from backend.permissions import check_command_permission
from backend.planner import generate_plan
from backend.browser_agent import play_youtube_video
from backend.plugins import get_plugins
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("IntentRouter")

SUPPORTIVE_PREFIXES = {
    "en": "Of course. ",
    "hi": "Bilkul. ",
    "te": "Tappakunda. ",
}

ACTION_PREFIXES = (
    "open ",
    "play ",
    "search ",
    "find ",
    "install ",
    "launch ",
    "start ",
    "remember ",
    "save this",
)


def make_response_supportive(text: str, lang: str) -> str:
    text = (text or "").strip()
    if not text:
        return text

    lowered = text.lower()
    if any(lowered.startswith(prefix.lower()) for prefix in ("of course", "sure", "certainly", "absolutely", "happy to help")):
        return text

    prefix = SUPPORTIVE_PREFIXES.get(lang, SUPPORTIVE_PREFIXES["en"])
    return f"{prefix}{text}"


def get_local_conversational_response(command: str, lang: str) -> str | None:
    cmd_lower = command.lower().strip()
    if cmd_lower in {"hi", "hello", "hey", "hey aura", "hello aura"}:
        replies = {
            "en": "I'm here with you. How can I help right now?",
            "hi": "Main yahin hoon. Abhi main aapki kis tarah madad kar sakti hoon?",
            "te": "Nenu ikkade unnaanu. Ippudu nenu meeku ela sahayam cheyagalanu?",
        }
        return replies.get(lang, replies["en"])
    if cmd_lower in {"thanks", "thank you", "thankyou"}:
        replies = {
            "en": "You're welcome. I'm here whenever you need me.",
            "hi": "Aapka swagat hai. Jab bhi zaroorat ho, main yahin hoon.",
            "te": "Mee kosam eppudaina siddhanga untaanu.",
        }
        return replies.get(lang, replies["en"])
    return None

def enforce_language(text: str, lang: str) -> str:
    if lang == "en":
        return text
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='auto', target=lang).translate(text)
    except Exception:
        return text

async def route_intent(
    command: str, 
    lang: str, 
    user: User, 
    history: list, 
    db: AsyncSession,
    send_status: Callable[[str, str], Awaitable[None]]
) -> str:
    
    cmd_lower = command.lower().strip()
    local_reply = get_local_conversational_response(command, lang)
    if local_reply:
        return local_reply

    is_action_request = cmd_lower.startswith(ACTION_PREFIXES)

    if cmd_lower.startswith("open "):
        target = cmd_lower[5:].strip()
        plan = [{"intent": "open_app", "payload": target}]
    elif cmd_lower.startswith("play "):
        target = cmd_lower[5:].strip()
        plan = [{"intent": "play_youtube", "payload": target}]
    elif not is_action_request:
        plan = []
    else:
        await send_status("planning", enforce_language("Thinking about how to do this...", lang))
        plan = await generate_plan(command, user, lang)
    if not plan:
        groq_api_key = os.environ.get("GROQ_API_KEY", "")
        if not groq_api_key or groq_api_key == "YOUR_GROQ_API_KEY_HERE":
            await send_status("error", "API Error")
            return enforce_language("I'm sorry, I cannot process this right now.", lang)
        
        client = Groq(api_key=groq_api_key)
        context = "\n".join([f"{msg.role}: {msg.content}" for msg in history[-3:]])
        prompt = (
            "You are Aura, a calm, warm, supportive voice assistant. "
            "Respond naturally, clearly, and kindly. Keep it concise unless detail is needed.\n\n"
            f"User Context:\n{context}\n\nRespond to: {command}"
        )
        try:
            res = await asyncio.wait_for(
                asyncio.to_thread(
                    client.chat.completions.create,
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5
                ),
                timeout=12
            )
            return make_response_supportive(enforce_language(res.choices[0].message.content.strip(), lang), lang)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            fallback = {
                "en": "I'm having trouble reaching my reasoning service right now, but I'm still here and can handle direct commands like open or play.",
                "hi": "Mujhe abhi apni reasoning service tak pahunchne mein dikkat ho rahi hai, lekin main yahin hoon aur open ya play jaise seedhe commands handle kar sakti hoon.",
                "te": "Na reasoning service ni ippudu reach cheyalekapothunnanu, kaani nenu ikkade unnaanu mariyu open leka play laanti direct commands handle cheyagalanu.",
            }
            return make_response_supportive(fallback.get(lang, fallback["en"]), lang)

    responses = []
    
    for step in plan:
        intent = step.get("intent")
        payload = step.get("payload", "")
        
        await send_status("executing", enforce_language(f"Executing: {intent} {payload}", lang))
        
        allowed = await check_command_permission(user, intent, payload, db)
        if not allowed:
            msg = enforce_language(f"Restricted access: Cannot {intent}.", lang)
            responses.append(msg)
            db.add(AuditLog(user_id=user.id, intent=intent, payload=payload, status="denied", error_message="Permission check failed"))
            await db.commit()
            continue
            
        success = False
        attempt = 0
        error_msg = None
        plugin_handled = False
        
        while attempt < 2 and not success:
            attempt += 1
            try:
                for plugin in get_plugins():
                    if await plugin.can_handle(command, intent):
                        await send_status("executing", f"Using plugin for {intent}...")
                        result = await plugin.execute(payload, {"user": user, "lang": lang})
                        if result.get("success"):
                            responses.append(result.get("response", "Done."))
                            success = True
                        else:
                            raise Exception(result.get("error", "Plugin failed"))
                        plugin_handled = True
                        break
                
                if plugin_handled and success:
                    break
                    
                if plugin_handled and not success:
                    continue
                    
                if intent == "open_web":
                    open_website(payload)
                    responses.append(enforce_language(f"Opening {payload} for you.", lang))
                    success = True
                    
                elif intent == "play_youtube":
                    await play_youtube_video(payload)
                    responses.append(enforce_language(f"Playing {payload} on YouTube for you.", lang))
                    success = True
                    
                elif intent == "open_app":
                    app_success = open_desktop_app(payload)
                    if app_success:
                        responses.append(enforce_language(f"Opened {payload} for you.", lang))
                    else:
                        open_website(payload)
                        responses.append(enforce_language(f"I couldn't open the app directly, so I'm opening {payload} in your browser instead.", lang))
                    success = True
                        
                elif intent == "install_app":
                    install_app_fallback(payload)
                    responses.append(enforce_language(f"Opening the installation page for {payload}.", lang))
                    success = True
                    
                elif intent == "search_web":
                    wiki_res = get_wikipedia_summary(payload, lang)
                    if wiki_res["success"]:
                        responses.append(enforce_language(wiki_res["text"], lang))
                    else:
                        fallback_search(payload)
                        responses.append(enforce_language(f"Searching the web for {payload}.", lang))
                    success = True
                    
                elif intent == "speak":
                    responses.append(enforce_language(payload, lang))
                    success = True
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Execution Error (Attempt {attempt}): {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
                else:
                    responses.append(enforce_language(f"I hit a problem while trying to execute {intent}.", lang))
        
        audit_status = "success" if success else "failed"
        db.add(AuditLog(user_id=user.id, intent=intent, payload=payload, status=audit_status, error_message=error_msg))
        await db.commit()
            
    if not responses:
        return make_response_supportive(enforce_language("Done.", lang), lang)
        
    return make_response_supportive(" ".join(responses), lang)
