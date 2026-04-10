from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
import datetime
from backend.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), default="user", nullable=False) # admin, user, child
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    preferences = relationship("UserPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    chat_history = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    long_term_memory = relationship("LongTermMemory", back_populates="user", cascade="all, delete-orphan")


class UserPreference(Base):
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    language = Column(String(10), default="en") # en, hi, te
    tts_voice = Column(String(50), default="en-US-AriaNeural")
    theme = Column(String(20), default="dark") # dark, neon, custom
    personality = Column(String(50), default="professional") # professional, friendly, sarcastic
    
    user = relationship("User", back_populates="preferences")


class UserSettings(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    website_blacklist = Column(Text, default="[]") # JSON list of blocked sites
    command_filtering = Column(Boolean, default=False)
    allowed_start_time = Column(String(5), default="00:00") # HH:MM
    allowed_end_time = Column(String(5), default="23:59") # HH:MM
    
    user = relationship("User", back_populates="settings")


class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String(10), nullable=False) # 'user' or 'aura'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="chat_history")

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    intent = Column(String(50))
    payload = Column(Text)
    status = Column(String(20)) # success, failed, denied
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="audit_logs")

class LongTermMemory(Base):
    __tablename__ = "long_term_memory"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    content = Column(Text, nullable=False)
    type = Column(String(50)) # preference, behavior, fact
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="long_term_memory")

class SystemAnalytics(Base):
    __tablename__ = "system_analytics"
    id = Column(Integer, primary_key=True, index=True)
    command = Column(Text)
    execution_time_ms = Column(Float)
    failure_rate = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
