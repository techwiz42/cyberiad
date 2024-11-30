from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import joinedload
from sqlalchemy.future import select
from fastapi import WebSocket
from typing import List, Optional, Dict, AsyncGenerator
from datetime import datetime
from uuid import UUID
import logging
import os
from models import Base, User, Thread, ThreadParticipant, Message, ThreadAgent

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/cyberiad")

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class DatabaseManager:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = AsyncSessionLocal
        self._active_connections: Dict[UUID, Dict[UUID, WebSocket]] = {}

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def init_db(self):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_user_by_username(self, session: AsyncSession, username: str):
        result = await session.execute(select(User).where(User.username == username))
        return result.scalars().first()

    async def create_user(self, session: AsyncSession, username: str, email: str, hashed_password: str):
        try:
            user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                created_at=datetime.utcnow()
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating user: {e}")
            raise

    async def create_thread(self, session: AsyncSession, owner_id: UUID, title: str, description: Optional[str] = None):
        try:
            thread = Thread(
                owner_id=owner_id,
                title=title,
                description=description
            )
            session.add(thread)
            await session.commit()
            await session.refresh(thread)
            
            await self.add_thread_participant(session, thread.id, owner_id)
            return thread
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating thread: {e}")
            raise

    async def get_thread(self, session: AsyncSession, thread_id: UUID):
        result = await session.execute(
            select(Thread)
            .where(Thread.id == thread_id)
            .options(joinedload(Thread.participants))
        )
        return result.scalars().first()

    async def get_user_threads(self, session: AsyncSession, user_id: UUID):
        result = await session.execute(
            select(Thread)
            .join(ThreadParticipant)
            .where(ThreadParticipant.user_id == user_id)
            .order_by(desc(Thread.updated_at))
            .options(joinedload(Thread.participants))
        )
        return result.scalars().unique().all()

    async def add_thread_participant(self, session: AsyncSession, thread_id: UUID, user_id: UUID):
        try:
            participant = ThreadParticipant(thread_id=thread_id, user_id=user_id)
            session.add(participant)
            await session.commit()
            return participant
        except Exception as e:
            await session.rollback()
            logger.error(f"Error adding thread participant: {e}")
            raise

    async def create_message(self, session: AsyncSession, thread_id: UUID, 
                           content: str, user_id: Optional[UUID] = None, 
                           agent_id: Optional[UUID] = None, 
                           message_metadata: Optional[dict] = None):
        try:
            message = Message(
                thread_id=thread_id,
                user_id=user_id,
                agent_id=agent_id,
                content=content,
                message_metadata=message_metadata or {}
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return message
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating message: {e}")
            raise

    async def get_thread_messages(self, session: AsyncSession, thread_id: UUID, 
                                limit: int = 50, before: Optional[datetime] = None):
        query = select(Message).where(Message.thread_id == thread_id)
        if before:
            query = query.where(Message.created_at < before)
        query = query.order_by(desc(Message.created_at)).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

    async def is_thread_participant(self, session: AsyncSession, thread_id: UUID, user_id: UUID) -> bool:
        result = await session.execute(
            select(ThreadParticipant)
            .where(and_(
                ThreadParticipant.thread_id == thread_id,
                ThreadParticipant.user_id == user_id,
                ThreadParticipant.is_active == True
            ))
        )
        return result.scalars().first() is not None

    async def get_thread_agents(self, session: AsyncSession, thread_id: UUID):
        result = await session.execute(
            select(ThreadAgent)
            .where(ThreadAgent.thread_id == thread_id)
            .where(ThreadAgent.is_active == True)
        )
        return result.scalars().all()

    async def get_thread_context(self, session: AsyncSession, thread_id: UUID, limit: int = 10) -> str:
        messages = await self.get_thread_messages(session, thread_id, limit)
        return "\n".join([f"{msg.content}" for msg in messages])

    # WebSocket connection management
    async def add_active_connection(self, thread_id: UUID, user_id: UUID, websocket: WebSocket):
        if thread_id not in self._active_connections:
            self._active_connections[thread_id] = {}
        self._active_connections[thread_id][user_id] = websocket

    async def remove_active_connection(self, thread_id: UUID, user_id: UUID):
        if thread_id in self._active_connections:
            self._active_connections[thread_id].pop(user_id, None)
            if not self._active_connections[thread_id]:
                del self._active_connections[thread_id]

    async def broadcast_to_thread(self, thread_id: UUID, sender_id: UUID, message: str):
        if thread_id in self._active_connections:
            for user_id, websocket in self._active_connections[thread_id].items():
                if user_id != sender_id:
                    try:
                        await websocket.send_text(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting message: {e}")
                        await self.remove_active_connection(thread_id, user_id)

# Create database manager instance
db_manager = DatabaseManager()
