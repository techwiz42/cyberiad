from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Enum, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
import uuid
import enum
from typing import Optional, List
import os

# Database URL configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/cyberiad"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True  # Set to False in production
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"

class AgentType(enum.Enum):
    LAWYER = "lawyer"
    ACCOUNTANT = "accountant"
    PSYCHOLOGIST = "psychologist"
    BUSINESS_ANALYST = "business_analyst"
    ETHICS_ADVISOR = "ethics_advisor"
    MODERATOR = "moderator"

class ThreadStatus(enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(Enum(UserRole), default=UserRole.USER)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    owned_threads = relationship("Thread", back_populates="owner")
    participations = relationship("ThreadParticipant", back_populates="user")

class Thread(Base):
    __tablename__ = "threads"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text)
    owner_id = Column(UUID, ForeignKey("users.id"))
    status = Column(Enum(ThreadStatus), default=ThreadStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    settings = Column(JSONB, default={})
    
    # Relationships
    owner = relationship("User", back_populates="owned_threads")
    participants = relationship("ThreadParticipant", back_populates="thread")
    messages = relationship("Message", back_populates="thread")
    agents = relationship("ThreadAgent", back_populates="thread")

class ThreadParticipant(Base):
    __tablename__ = "thread_participants"

    thread_id = Column(UUID, ForeignKey("threads.id"), primary_key=True)
    user_id = Column(UUID, ForeignKey("users.id"), primary_key=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_read_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    thread = relationship("Thread", back_populates="participants")
    user = relationship("User", back_populates="participations")

class ThreadAgent(Base):
    __tablename__ = "thread_agents"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID, ForeignKey("threads.id"))
    agent_type = Column(Enum(AgentType))
    is_active = Column(Boolean, default=True)
    settings = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    thread = relationship("Thread", back_populates="agents")
    messages = relationship("Message", back_populates="agent")

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID, ForeignKey("threads.id"))
    user_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    agent_id = Column(UUID, ForeignKey("thread_agents.id"), nullable=True)
    content = Column(Text, nullable=False)
    message_metadata = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    thread = relationship("Thread", back_populates="messages")
    user = relationship("User")
    agent = relationship("ThreadAgent", back_populates="messages")

# Database Manager Class
class DatabaseManager:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = AsyncSessionLocal

    async def create_tables(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self):
        async with self.SessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

# Create database manager instance
db_manager = DatabaseManager()
