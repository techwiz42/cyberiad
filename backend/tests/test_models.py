import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent / "backend"))
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import functools
from models import User, Thread, ThreadParticipant, ThreadAgent, Message, UserRole, AgentType, ThreadStatus
from .conftest import test_db_session

pytestmark = pytest.mark.asyncio  # Mark all tests in this module as async

@pytest.fixture
async def test_user(test_db_session: AsyncSession):
    """Create a test user with a unique username."""
    async with test_db_session as session:
        unique_username = f"testuser_{uuid.uuid4().hex[:8]}"
        user = User(
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password="hashed_password_here",
            role=UserRole.USER
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

@pytest.fixture
async def test_thread(test_db_session: AsyncSession, test_user: User):
    """Create a test thread with the test user as owner."""
    async with test_db_session as session:
        thread = Thread(
            title="Test Thread",
            description="Test Description",
            owner_id=test_user.id,  # Use test_user directly, no await
            status=ThreadStatus.ACTIVE
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        return thread

@pytest.mark.asyncio
async def test_user_creation(test_db_session):
    """Test user creation and attributes."""
    async for session in test_db_session:
        unique_username = f"newuser_{uuid.uuid4().hex[:8]}"
        user = User(
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password="hashed",
            role=UserRole.USER
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        assert isinstance(user.id, uuid.UUID)
        assert user.username == unique_username
        assert user.email == f"{unique_username}@example.com"
        assert user.role == UserRole.USER
        assert user.is_active is True
        assert isinstance(user.created_at, datetime)

@pytest.mark.asyncio
async def test_thread_creation(test_db_session, test_user):
    """Test thread creation and attributes."""
    user = await test_user
    async for session in test_db_session:
        thread = Thread(
            title="Test Thread",
            description="Test Description",
            owner_id=user.id
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        
        assert isinstance(thread.id, uuid.UUID)
        assert thread.title == "Test Thread"
        assert thread.description == "Test Description"
        assert thread.owner_id == user.id
        assert thread.status == ThreadStatus.ACTIVE
        assert isinstance(thread.created_at, datetime)
        assert isinstance(thread.updated_at, datetime)

async def test_thread_participant(test_db_session: AsyncSession, test_user: User, test_thread: Thread):
    """Test thread participant creation and attributes."""
    async with test_db_session as session:
        # Check if participant exists using ORM
        stmt = select(ThreadParticipant).where(
            ThreadParticipant.thread_id == test_thread.id,  # Use directly, no await
            ThreadParticipant.user_id == test_user.id       # Use directly, no await
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if not existing:
            participant = ThreadParticipant(
                thread_id=test_thread.id,
                user_id=test_user.id
            )
            session.add(participant)
            await session.commit()
            await session.refresh(participant)
            
            assert participant.thread_id == test_thread.id
            assert participant.user_id == test_user.id
            assert participant.is_active is True
            assert isinstance(participant.joined_at, datetime)


@pytest.mark.asyncio
async def test_thread_agent(test_db_session, test_thread):
    """Test thread agent creation and attributes."""
    thread = await test_thread
    async for session in test_db_session:
        agent = ThreadAgent(
            thread_id=thread.id,
            agent_type=AgentType.LAWYER,
            settings={"response_style": "formal"}
        )
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        
        assert isinstance(agent.id, uuid.UUID)
        assert agent.thread_id == thread.id
        assert agent.agent_type == AgentType.LAWYER
        assert agent.is_active is True
        assert agent.settings == {"response_style": "formal"}
        assert isinstance(agent.created_at, datetime)

@pytest.mark.asyncio
async def test_message(test_db_session, test_thread, test_user):
    """Test message creation and attributes."""
    thread = await test_thread
    user = await test_user
    async for session in test_db_session:
        message = Message(
            thread_id=thread.id,
            user_id=user.id,
            content="Test message content",
            message_metadata={"importance": "high"}
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        
        assert isinstance(message.id, uuid.UUID)
        assert message.thread_id == thread.id
        assert message.user_id == user.id
        assert message.content == "Test message content"
        assert message.message_metadata == {"importance": "high"}
        assert isinstance(message.created_at, datetime)

@pytest.mark.asyncio
async def test_relationships(test_db_session, test_user, test_thread):
    """Test model relationships."""
    user = await test_user
    thread = await test_thread
    async for session in test_db_session:
        # Check for existing participant using ORM
        exists = await session.execute(
            select(ThreadParticipant).where(
                ThreadParticipant.thread_id == thread.id,
                ThreadParticipant.user_id == user.id
            )
        )
        if not exists.scalar_one_or_none():
            participant = ThreadParticipant(
                thread_id=thread.id,
                user_id=user.id
            )
            session.add(participant)
        
        message = Message(
            thread_id=thread.id,
            user_id=user.id,
            content="Test message"
        )
        session.add(message)
        await session.commit()
        
        # Refresh objects to get updated relationships
        await session.refresh(thread)
        await session.refresh(user)
        
        # Test relationships
        assert thread.owner.id == user.id
        assert any(p.user_id == user.id for p in thread.participants)
        assert any(m.content == "Test message" for m in thread.messages)

@pytest.mark.asyncio
async def test_cascade_deletes(test_db_session, test_thread, test_user):
    """Test cascade deletions."""
    thread = await test_thread
    user = await test_user
    async for session in test_db_session:
        # Create all related records
        participant = ThreadParticipant(
            thread_id=thread.id,
            user_id=user.id
        )
        session.add(participant)
        
        agent = ThreadAgent(
            thread_id=thread.id,
            agent_type=AgentType.LAWYER
        )
        session.add(agent)
        
        message = Message(
            thread_id=thread.id,
            content="Test message"
        )
        session.add(message)
        await session.commit()
        
        # Delete thread
        await session.delete(thread)
        await session.commit()
        
        # Verify records are deleted using ORM
        assert await session.execute(
            select(ThreadAgent).where(ThreadAgent.thread_id == thread.id)
        ).scalar_one_or_none() is None
        
        assert await session.execute(
            select(Message).where(Message.thread_id == thread.id)
        ).scalar_one_or_none() is None
        
        assert await session.execute(
            select(ThreadParticipant).where(ThreadParticipant.thread_id == thread.id)
        ).scalar_one_or_none() is None

def test_user_roles():
    """Test user role enum values."""
    assert UserRole.ADMIN.value == "admin"
    assert UserRole.USER.value == "user"

def test_agent_types():
    """Test agent type enum values."""
    assert AgentType.LAWYER.value == "lawyer"
    assert AgentType.ACCOUNTANT.value == "accountant"
    assert AgentType.PSYCHOLOGIST.value == "psychologist"

def test_thread_statuses():
    """Test thread status enum values."""
    assert ThreadStatus.ACTIVE.value == "active"
    assert ThreadStatus.ARCHIVED.value == "archived"
    assert ThreadStatus.CLOSED.value == "closed"
