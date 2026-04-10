import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import json
from backend.models import User, UserSettings
from backend.utils import get_logger

logger = get_logger("Permissions")

async def check_command_permission(user: User, intent: str, payload: str, db: AsyncSession) -> bool:
    """
    Check if a user is allowed to execute a command based on their role, time, and content.
    Returns True if allowed, returns False if blocked.
    """
    if user.role == "admin":
        return True
        
    result = await db.execute(select(UserSettings).filter(UserSettings.user_id == user.id))
    settings = result.scalars().first()
    
    if not settings:
        return True
        
    # Time limits
    now_time = datetime.datetime.now().time()
    try:
        start_h, start_m = map(int, settings.allowed_start_time.split(':'))
        end_h, end_m = map(int, settings.allowed_end_time.split(':'))
        start_t = datetime.time(start_h, start_m)
        end_t = datetime.time(end_h, end_m)
        
        if start_t < end_t:
            if not (start_t <= now_time <= end_t):
                logger.warning(f"User {user.username} blocked by time restriction.")
                return False
        else: 
            if not (now_time >= start_t or now_time <= end_t):
                logger.warning(f"User {user.username} blocked by time restriction.")
                return False
    except Exception as e:
        logger.error(f"Time check error: {e}")
        
    # Role restricts
    if user.role == "child":
        if intent in ["system_command", "install_app"]:
            return False
            
    # Blacklist check
    if intent in ["open_web", "search_web", "play_youtube"] and payload:
        try:
            blacklist = json.loads(settings.website_blacklist)
            for blocked_site in blacklist:
                if blocked_site.lower() in payload.lower():
                    return False
        except Exception:
            pass
            
    return True
