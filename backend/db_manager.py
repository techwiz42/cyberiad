from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from fastapi import WebSocket
from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class DatabaseManagerImpl:
    def __init__(self):
        self._active_connections: Dict[UUID, Dict[UUID, WebSocket]] = {}

    async def get_user_by_username(self, session: AsyncSession, username: str):
        """Get user by username."""
        try:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting user by username: {e}")
            raise

    async def create_user(self, session: AsyncSession, username: str, email: str, hashed_password: str):
        """Create a new user."""
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
        """Create a new thread."""
        try:
            thread = Thread(
                owner_id=owner_id,
                title=title,
                description=description
            )
            session.add(thread)
            await session.commit()
            await session.refresh(thread)
            
            # Add owner as participant
            await self.add_thread_participant(session, thread.id, owner_id)
            
            return thread
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating thread: {e}")
            raise

    async def get_user_threads(self, session: AsyncSession, user_id: UUID):
        """Get all threads where user is participant."""
        try:
            result = await session.execute(
                select(Thread)
                .join(ThreadParticipant)
                .where(ThreadParticipant.user_id == user_id)
                .order_by(desc(Thread.updated_at))
                .options(joinedload(Thread.participants))
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting user threads: {e}")
            raise

    async def add_thread_participant(self, session: AsyncSession, thread_id: UUID, user_id: UUID):
        """Add participant to thread."""
        try:
            participant = ThreadParticipant(
                thread_id=thread_id,
                user_id=user_id
            )
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
                           metadata: Optional[dict] = None):
        """Create a new message."""
        try:
            message = Message(
                thread_id=thread_id,
                user_id=user_id,
                agent_id=agent_id,
                content=content,
                metadata=metadata or {}
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
        """Get thread messages with pagination."""
        try:
            query = select(Message).where(Message.thread_id == thread_id)
            
            if before:
                query = query.where(Message.created_at < before)
                
            query = query.order_by(desc(Message.created_at)).limit(limit)
            
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting thread messages: {e}")
            raise

    async def is_thread_participant(self, session: AsyncSession, thread_id: UUID, user_id: UUID) -> bool:
        """Check if user is thread participant."""
        try:
            result = await session.execute(
                select(ThreadParticipant)
                .where(and_(
                    ThreadParticipant.thread_id == thread_id,
                    ThreadParticipant.user_id == user_id,
                    ThreadParticipant.is_active == True
                ))
            )
            return result.scalars().first() is not None
        except Exception as e:
            logger.error(f"Error checking thread participant: {e}")
            raise

    # WebSocket connection management
    async def add_active_connection(self, thread_id: UUID, user_id: UUID, websocket: WebSocket):
        """Add active WebSocket connection."""
        if thread_id not in self._active_connections:
            self._active_connections[thread_id] = {}
        self._active_connections[thread_id][user_id] = websocket

    async def remove_active_connection(self, thread_id: UUID, user_id: UUID):
        """Remove active WebSocket connection."""
        if thread_id in self._active_connections:
            self._active_connections[thread_id].pop(user_id, None)
            if not self._active_connections[thread_id]:
                del self._active_connections[thread_id]

    async def broadcast_to_thread(self, thread_id: UUID, sender_id: UUID, message: str):
        """Broadcast message to all thread participants."""
        if thread_id in self._active_connections:
            for user_id, websocket in self._active_connections[thread_id].items():
                if user_id != sender_id:
                    try:
                        await websocket.send_text(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting message: {e}")
                        await self.remove_active_connection(thread_id, user_id)

# Create database manager instance
db_manager_impl = DatabaseManagerImpl()
