import time
import re
import os
import asyncio
from typing import Awaitable, Callable
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel
from sqlalchemy.future import select

from backend.intent import route_intent
from backend.tts import generate_speech, get_voice, clean_text_for_tts, chunk_text
from backend.utils import get_logger, get_error_response
from backend.auth_router import router as auth_router
from backend.auth import get_current_user_from_token, get_current_user
from backend.database import AsyncSessionLocal, init_database, get_db
from backend.models import User, ChatHistory, UserPreference, SystemAnalytics, LongTermMemory
from backend.memory import summarize_memory
from backend.plugins import load_plugins

app = FastAPI(title="Aura AI", description="Localhost Voice Assistant API")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
logger = get_logger("MainApp")

app.include_router(auth_router, prefix="/api")

RATE_LIMIT_SECONDS = 0.5
client_last_request = {}
message_counters = {}


class ChatRequest(BaseModel):
    content: str
    language: str = "en"


class ChatResponse(BaseModel):
    text: str
    audio_chunks: list[str]

@app.on_event("startup")
async def startup_event():
    await init_database()
    load_plugins()

@app.get("/")
async def get(request: Request):
    # Dynamically detect background video in static/
    video_file = "background.mp4"
    if os.path.exists("static"):
        for f in os.listdir("static"):
            if f.endswith(".mp4"):
                video_file = f
                break
    return templates.TemplateResponse("index.html", {"request": request, "bg_video": video_file})

async def background_memory_task(user_id: int):
    async with AsyncSessionLocal() as db:
        user_req = await db.execute(select(User).filter(User.id == user_id))
        user = user_req.scalars().first()
        if user:
            await summarize_memory(user, db)


async def process_command(
    user: User,
    command: str,
    lang: str,
    db,
    send_status: Callable[[str, str], Awaitable[None]] | None = None,
    include_tts: bool = True,
) -> tuple[str, list[str]]:
    async def noop_status(_state: str, _message: str):
        return None

    send_status = send_status or noop_status

    user_msg = ChatHistory(user_id=user.id, role="user", content=command)
    db.add(user_msg)
    await db.commit()

    message_counters[user.id] = message_counters.get(user.id, 0) + 1

    mem_req = await db.execute(select(LongTermMemory).filter(LongTermMemory.user_id == user.id))
    memories = mem_req.scalars().all()
    mem_context = "; ".join([m.content for m in memories])

    start_time = time.time()
    try:
        history_req = await db.execute(
            select(ChatHistory).filter(ChatHistory.user_id == user.id).order_by(ChatHistory.id.desc()).limit(4)
        )
        history = list(reversed(history_req.scalars().all()))

        if mem_context:
            history.insert(0, ChatHistory(role="system", content=f"User long term facts: {mem_context}"))

        response_text = await route_intent(command, lang, user, history, db, send_status)
        if not response_text or not isinstance(response_text, str):
            response_text = get_error_response(lang)
    except Exception as e:
        logger.error(f"Intent failure: {e}")
        response_text = get_error_response(lang)

    exec_time = (time.time() - start_time) * 1000
    db.add(SystemAnalytics(command=command, execution_time_ms=exec_time))
    await db.commit()

    display_text = response_text.strip()
    aura_msg = ChatHistory(user_id=user.id, role="aura", content=display_text)
    db.add(aura_msg)
    await db.commit()

    tts_text = clean_text_for_tts(display_text)
    if not tts_text.strip():
        tts_text = "Okay"
    if len(tts_text.strip()) < 5:
        tts_text = f"{tts_text}. Done."

    audio_chunks: list[str] = []
    if include_tts:
        try:
            voice = get_voice(lang)
            chunks = chunk_text(tts_text, lang)

            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                await send_status("speaking", "Transmitting Voice Data..." if i > 0 else "Voice Feed Established...")
                audio_b64 = await generate_speech(chunk, voice, lang)
                if audio_b64:
                    audio_chunks.append(audio_b64)
        except Exception as e:
            logger.error(f"TTS sequence failed: {e}")

    await send_status("ready", "Ready.")

    if message_counters[user.id] >= 5:
        message_counters[user.id] = 0
        asyncio.create_task(background_memory_task(user.id))
    elif "remember" in command.lower() or "save this" in command.lower():
        asyncio.create_task(background_memory_task(user.id))

    return display_text, audio_chunks


@app.post("/api/chat", response_model=ChatResponse)
async def chat_api(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    command = payload.content.strip()
    if not command:
        return ChatResponse(text="", audio_chunks=[])

    text, audio_chunks = await process_command(
        current_user,
        command,
        payload.language or "en",
        db,
        include_tts=False,
    )
    return ChatResponse(text=text, audio_chunks=audio_chunks)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    await websocket.accept()
    
    if not token:
        await websocket.close(code=1008, reason="Authentication failed")
        return
        
    async with AsyncSessionLocal() as db:
        try:
            user = await get_current_user_from_token(token, db)
        except Exception as e:
            logger.error(f"WS Auth Error: {e}")
            await websocket.close(code=1008, reason="Authentication failed")
            return
            
        client_host = websocket.client.host if websocket.client else "unknown"
        client_port = websocket.client.port if websocket.client else "unknown"
        client_id = f"{user.username}_{client_host}:{client_port}"
        
        logger.info(f"Client connected: {client_id}")
        client_last_request[client_id] = 0
        
        if user.id not in message_counters:
            message_counters[user.id] = 0
            
        prefs_result = await db.execute(select(UserPreference).filter(UserPreference.user_id == user.id))
        prefs = prefs_result.scalars().first()
        base_lang = prefs.language if prefs else "en"
        base_voice = prefs.tts_voice if prefs else get_voice(base_lang)
        
        async def send_status(state: str, message: str):
            try:
                await websocket.send_json({"type": "status", "state": state, "message": message})
            except Exception:
                pass
            
        try:
            while True:
                data = await websocket.receive_json()
                
                now = time.time()
                if now - client_last_request.get(client_id, 0) < RATE_LIMIT_SECONDS:
                    logger.warning(f"Rate limit hit by {client_id}. Dropping request.")
                    continue
                client_last_request[client_id] = now
                
                if data.get("type") == "text":
                    command = data.get("content")
                    if not command:
                        continue
                        
                    lang = data.get("language", base_lang)
                    logger.info(f"Request [{client_id}]: '{command}' | Lang: {lang}")
                    display_text, audio_chunks = await process_command(user, command, lang, db, send_status)

                    await websocket.send_json({
                        "type": "response",
                        "text": display_text
                    })

                    for audio_b64 in audio_chunks:
                        await websocket.send_json({
                            "type": "audio_chunk",
                            "audio_b64": audio_b64
                        })
                    
        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {client_id}")
            client_last_request.pop(client_id, None)
        except Exception as e:
            logger.error(f"WebSocket Error from {client_id}: {e}")
