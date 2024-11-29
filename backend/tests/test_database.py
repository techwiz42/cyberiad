# tests/test_database.py
import pytest
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from database import DatabaseManager, Base
from models import User, Thread, ThreadParticipant, Message, ThreadAgent
from fastapi import WebSocket
import uuid
from datetime import datetime, timedelta
import asyncio
import logging

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/cyberiad_test"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def db_manager(test_engine):
    """Create a database manager instance for testing."""
    manager = DatabaseManager()
    manager.engine = test_engine
    manager.SessionLocal = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    await manager.init_db()
    return manager

@pytest.fixture
async def session(db_manager):
    """Create a database session for testing."""
    async with db_manager.SessionLocal() as session:
        yield session
        await session.rollback()

# User Tests
@pytest.mark.asyncio
async def test_create_user(db_manager, session):
    username = "testuser"
    email = "test@example.com"
    hashed_password = "hashed_password"
    
    user = await db_manager.create_user(
        session,
        username=username,
        email=email,
        hashed_password=hashed_password
    )
    
    assert user.username == username
    assert user.email == email
    assert user.hashed_password == hashed_password
    assert isinstance(user.id, uuid.UUID)
    assert isinstance(user.created_at, datetime)

@pytest.mark.asyncio
async def test_get_user_by_username(db_manager, session):
    # Create test user
    username = "findme"
    user = await db_manager.create_user(
        session,
        username=username,
        email="find@example.com",
        hashed_password="password123"
    )
    
    # Test retrieval
    found_user = await db_manager.get_user_by_username(session, username)
    assert found_user.id == user.id
    assert found_user.username == username

# Thread Tests
@pytest.mark.asyncio
async def test_create_thread(db_manager, session):
    # Create a user first
    user = await db_manager.create_user(
        session,
        username="threadowner",
        email="owner@example.com",
        hashed_password="password"
    )
    
    title = "Test Thread"
    description = "Test Description"
    
    thread = await db_manager.create_thread(
        session,
        owner_id=user.id,
        title=title,
        description=description
    )
    
    assert thread.title == title
    assert thread.description == description
    assert thread.owner_id == user.id
    assert isinstance(thread.id, uuid.UUID)
    assert isinstance(thread.created_at, datetime)

@pytest.mark.asyncio
async def test_get_thread(db_manager, session):
    # Create user and thread
    user = await db_manager.create_user(
        session,
        username="threaduser",
        email="thread@example.com",
        hashed_password="password"
    )
    
    thread = await db_manager.create_thread(
        session,
        owner_id=user.id,
        title="Find This Thread"
    )
    
    # Test retrieval
    found_thread = await db_manager.get_thread(session, thread.id)
    assert found_thread.id == thread.id
    assert found_thread.title == "Find This Thread"

@pytest.mark.asyncio
async def test_get_user_threads(db_manager, session):
    # Create user and multiple threads
    user = await db_manager.create_user(
        session,
        username="multithread",
        email="multi@example.com",
        hashed_password="password"
    )
    
    threads = []
    for i in range(3):
        thread = await db_manager.create_thread(
            session,
            owner_id=user.id,
            title=f"Thread {i}"
        )
        threads.append(thread)
    
    # Test retrieval
    user_threads = await db_manager.get_user_threads(session, user.id)
    assert len(user_threads) == 3
    assert all(t.owner_id == user.id for t in user_threads)

# Thread Participant Tests
@pytest.mark.asyncio
async def test_add_thread_participant(db_manager, session):
    # Create user and thread
    user = await db_manager.create_user(
        session,
        username="participant",
        email="participant@example.com",
        hashed_password="password"
    )
    
    thread = await db_manager.create_thread(
        session,
        owner_id=user.id,
        title="Participant Thread"
    )
    
    # Add participant
    participant = await db_manager.add_thread_participant(
        session,
        thread.id,
        user.id
    )
    
    assert participant.thread_id == thread.id
    assert participant.user_id == user.id

@pytest.mark.asyncio
async def test_is_thread_participant(db_manager, session):
    # Create user and thread
    user = await db_manager.create_user(
        session,
        username="isparticipant",
        email="is@example.com",
        hashed_password="password"
    )
    
    thread = await db_manager.create_thread(
        session,
        owner_id=user.id,
        title="Participation Test"
    )
    
    # Add participant
    await db_manager.add_thread_participant(session, thread.id, user.id)
    
    # Test verification
    is_participant = await db_manager.is_thread_participant(
        session,
        thread.id,
        user.id
    )
    assert is_participant is True

# Message Tests
@pytest.mark.asyncio
async def test_create_message(db_manager, session):
    # Create user and thread
    user = await db_manager.create_user(
        session,
        username="messenger",
        email="messenger@example.com",
        hashed_password="password"
    )
    
    thread = await db_manager.create_thread(
        session,
        owner_id=user.id,
        title="Message Thread"
    )
    
    # Create message
    content = "Test message"
    message = await db_manager.create_message(
        session,
        thread_id=thread.id,
        user_id=user.id,
        content=content
    )
    
    assert message.content == content
    assert message.thread_id == thread.id
    assert message.user_id == user.id
    assert isinstance(message.created_at, datetime)

@pytest.mark.asyncio
async def test_get_thread_messages(db_manager, session):
    # Create user and thread
    user = await db_manager.create_user(
        session,
        username="msghistory",
        email="history@example.com",
        hashed_password="password"
    )
    
    thread = await db_manager.create_thread(
        session,
        owner_id=user.id,
        title="Message History"
    )
    
    # Create multiple messages
    messages = []
    for i in range(3):
        message = await db_manager.create_message(
            session,
            thread_id=thread.id,
            user_id=user.id,
            content=f"Message {i}"
        )
        messages.append(message)
    
    # Test retrieval
    thread_messages = await db_manager.get_thread_messages(
        session,
        thread.id,
        limit=10
    )
    assert len(thread_messages) == 3
    assert all(m.thread_id == thread.id for m in thread_messages)

# WebSocket Connection Tests
@pytest.mark.asyncio
async def test_websocket_management(db_manager):
    thread_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_websocket = Mock(spec=WebSocket)
    
    # Add connection
    await db_manager.add_active_connection(thread_id, user_id, mock_websocket)
    assert thread_id in db_manager._active_connections
    assert user_id in db_manager._active_connections[thread_id]
    
    # Remove connection
    await db_manager.remove_active_connection(thread_id, user_id)
    assert thread_id not in db_manager._active_connections

@pytest.mark.asyncio
async def test_broadcast_to_thread(db_manager):
    thread_id = uuid.uuid4()
    sender_id = uuid.uuid4()
    receiver_id = uuid.uuid4()
    
    # Create mock websockets
    sender_ws = AsyncMock(spec=WebSocket)
    receiver_ws = AsyncMock(spec=WebSocket)
    
    # Add connections
    await db_manager.add_active_connection(thread_id, sender_id, sender_ws)
    await db_manager.add_active_connection(thread_id, receiver_id, receiver_ws)
    
    # Test broadcast
    message = "Test broadcast"
    await db_manager.broadcast_to_thread(thread_id, sender_id, message)
    
    # Verify receiver got message but sender didn't
    receiver_ws.send_text.assert_called_once_with(message)
    sender_ws.send_text.assert_not_called()

@pytest.mark.asyncio
async def test_get_thread_context(db_manager, session):
    # Create user and thread
    user = await db_manager.create_user(
        session,
        username="context",
        email="context@example.com",
        hashed_password="password"
    )
    
    thread = await db_manager.create_thread(
        session,
        owner_id=user.id,
        title="Context Thread"
    )
    
    # Create messages
    messages = [
        "First message",
        "Second message",
        "Third message"
    ]
    
    for content in messages:
        await db_manager.create_message(
            session,
            thread_id=thread.id,
            user_id=user.id,
            content=content
        )
    
    # Get context
    context = await db_manager.get_thread_context(session, thread.id, limit=3)
    for message in messages:
        assert message in context

# Error Handling Tests
@pytest.mark.asyncio
async def test_database_errors(db_manager, session):
    with pytest.raises(Exception):
        await db_manager.create_user(
            session,
            username="duplicate",
            email="duplicate@example.com",
            hashed_password="password"
        )
        # Try to create duplicate user
        await db_manager.create_user(
            session,
            username="duplicate",
            email="duplicate@example.com",
            hashed_password="password"
        )

@pytest.mark.asyncio
async def test_transaction_rollback(db_manager, session):
    # Start transaction
    async with session.begin():
        user = await db_manager.create_user(
            session,
            username="rollback",
            email="rollback@example.com",
            hashed_password="password"
        )
        # Force rollback
        await session.rollback()
    
    # Verify user wasn't created
    result = await db_manager.get_user_by_username(session, "rollback")
    assert result is None
