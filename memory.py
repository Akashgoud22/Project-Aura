import os
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from groq import Groq
from backend.models import User, ChatHistory, LongTermMemory
from backend.utils import get_logger

logger = get_logger("Memory")

async def summarize_memory(user: User, db: AsyncSession):
    """
    Summarize the last 10 interactions into LongTermMemory.
    Should be run as a background task.
    """
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_api_key or groq_api_key == "YOUR_GROQ_API_KEY_HERE":
        return
        
    client = Groq(api_key=groq_api_key)
    
    req = await db.execute(
        select(ChatHistory).filter(ChatHistory.user_id == user.id).order_by(ChatHistory.id.desc()).limit(10)
    )
    history = reversed(req.scalars().all())
    
    conversation = "\n".join([f"{msg.role}: {msg.content}" for msg in history])
    if not conversation.strip():
        return
        
    prompt = f"""
    Analyze the following conversation and extract any new key user preferences, behaviors, or facts.
    Output ONLY a JSON list of objects. Let's strictly use valid JSON.
    Example:
    [
        {{"type": "preference", "content": "Likes lofi hip hop"}},
        {{"type": "fact", "content": "Name is John"}}
    ]
    If no new meaningful long-term facts exist, output [].
    
    Conversation:
    {conversation}
    """
    
    try:
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        output = res.choices[0].message.content.strip()
        if output.startswith("```json"): output = output[7:-3]
        if output.startswith("```"): output = output[3:-3]
        
        facts = json.loads(output)
        for fact in facts:
            new_mem = LongTermMemory(
                user_id=user.id,
                type=fact.get("type", "fact"),
                content=fact.get("content", "")
            )
            db.add(new_mem)
        
        if facts:
            await db.commit()
            logger.info(f"Summarized {len(facts)} memory points for user {user.username}")
            
    except Exception as e:
        logger.error(f"Memory summarization failed: {e}")
