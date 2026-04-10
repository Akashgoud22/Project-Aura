from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.database import get_db
from backend.models import User, UserPreference, UserSettings, ChatHistory
from backend.auth import get_password_hash, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

@router.post("/register")
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter((User.username == user.username) | (User.email == user.email)))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username or email already registered")
        
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, email=user.email, password_hash=hashed_password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    prefs = UserPreference(user_id=new_user.id)
    settings = UserSettings(user_id=new_user.id)
    db.add(prefs)
    db.add(settings)
    await db.commit()
    
    return {"message": "User registered successfully"}

@router.post("/login")
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.username == user.username))
    db_user = result.scalars().first()
    
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    access_token = create_access_token(data={"sub": db_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}

@router.get("/profile")
async def get_user_profile(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserPreference).filter(UserPreference.user_id == current_user.id))
    prefs = result.scalars().first()
    return {
        "username": current_user.username,
        "avatar": "default",
        "role": current_user.role,
        "language": prefs.language if prefs else "en",
        "theme": prefs.theme if prefs else "dark"
    }

@router.get("/history")
async def get_user_history(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatHistory)
        .filter(ChatHistory.user_id == current_user.id)
        .order_by(ChatHistory.id.desc())
        .limit(10)
    )
    history = result.scalars().all()
    out = []
    for h in history:
        if h.role == "user" or h.role == "aura":
            out.append({"role": h.role, "content": h.content, "timestamp": h.timestamp.isoformat() if h.timestamp else None})
    return out
