import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent / "backend"))
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
from sqlalchemy import select
from database import DatabaseManager
from models import User, Thread, ThreadParticipant, Message
from fastapi import WebSocket
import uuid
from datetime import datetime, UTC
from .conftest import test_db_session

@pytest.mark.asyncio
async def test_create_user(test_db_session):
    """Test user creation and basic attributes."""
    async with test_db_session as session:
        db_manager = DatabaseManager()
        unique_username = f"testuser_{uuid.uuid4().hex[:8]}"
        user = await db_manager.create_user(
            session,
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password="hashed_password"
        )
        
        assert user.username == unique_username
        assert user.email == f"{unique_username}@example.com"
        assert user.hashed_password == "hashed_password"
        assert isinstance(user.id, uuid.UUID)
        assert isinstance(user.created_at, datetime)
        assert user.is_active is True

@pytest.mark.asyncio
async def test_get_user_by_username(test_db_session):
    """Test user retrieval by username."""
    async with test_db_session as session:
        db_manager = DatabaseManager()
        unique_username = f"findme_{uuid.uuid4().hex[:8]}"
        
        # Create test user
        user = await db_manager.create_user(
            session,
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password="password123"
        )
        
        # Test retrieval
        found_user = await db_manager.get_user_by_username(session, unique_username)
        assert found_user.id == user.id
        assert found_user.username == unique_username

@pytest.mark.asyncio
async def test_create_thread(test_db_session):
    """Test thread creation with owner."""
    async with test_db_session as session:
        db_manager = DatabaseManager()
        
        # Create owner
        unique_username = f"owner_{uuid.uuid4().hex[:8]}"
        user = await db_manager.create_user(
            session,
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password="password"
        )
        
        # Create thread
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
async def test_get_thread(test_db_session):
    """Test thread retrieval."""
    async with test_db_session as session:
        db_manager = DatabaseManager()
        
        # Create user and thread
        unique_username = f"thread_{uuid.uuid4().hex[:8]}"
        user = await db_manager.create_user(
            session,
            username=unique_username,
            email=f"{unique_username}@example.com",
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
async def test_get_user_threads(test_db_session):
    """Test retrieval of all user's threads."""
    async with test_db_session as session:
        db_manager = DatabaseManager()
        
        # Create user
        unique_username = f"multi_{uuid.uuid4().hex[:8]}"
        user = await db_manager.create_user(
            session,
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password="password"
        )
        
        # Create multiple threads
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

@pytest.mark.asyncio
async def test_thread_participant(test_db_session):
    """Test thread participant operations."""
    async with test_db_session as session:
        db_manager = DatabaseManager()
        
        # Create user and thread
        unique_username = f"participant_{uuid.uuid4().hex[:8]}"
        user = await db_manager.create_user(
            session,
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password="password"
        )
        
        thread = await db_manager.create_thread(
            session,
            owner_id=user.id,
            title="Participant Thread"
        )
        
        # Verify the participant was added by create_thread
        is_participant = await db_manager.is_thread_participant(
            session,
            thread.id,
            user.id
        )
        assert is_participant is True

        # Test participant properties
        result = await session.execute(
            select(ThreadParticipant).where(
                ThreadParticipant.thread_id == thread.id,
                ThreadParticipant.user_id == user.id
            )
        )
        participant = result.scalar_one()
        assert participant.thread_id == thread.id
        assert participant.user_id == user.id
        assert participant.is_active is True

@pytest.mark.asyncio
async def test_messages(test_db_session):
    """Test message creation and retrieval."""
    async with test_db_session as session:
        db_manager = DatabaseManager()
        
        # Create user and thread
        unique_username = f"messenger_{uuid.uuid4().hex[:8]}"
        user = await db_manager.create_user(
            session,
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password="password"
        )
        
        thread = await db_manager.create_thread(
            session,
            owner_id=user.id,
            title="Message Thread"
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

@pytest.mark.asyncio
async def test_websocket_management():
    """Test WebSocket connection management."""
    db_manager = DatabaseManager()
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
async def test_thread_context(test_db_session):
    """Test thread context retrieval."""
    async with test_db_session as session:
        db_manager = DatabaseManager()
        
        # Create user and thread
        unique_username = f"context_{uuid.uuid4().hex[:8]}"
        user = await db_manager.create_user(
            session,
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password="password"
        )
        
        thread = await db_manager.create_thread(
            session,
            owner_id=user.id,
            title="Context Thread"
        )
        
        # Create messages
        messages = ["First message", "Second message", "Third message"]
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

@pytest.mark.asyncio
async def test_broadcast_to_thread():
    """Test thread message broadcasting."""
    db_manager = DatabaseManager()
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
async def test_error_handling(test_db_session):
    """Test database error handling."""
    async with test_db_session as session:
        db_manager = DatabaseManager()
        username = f"duplicate_{uuid.uuid4().hex[:8]}"
        
        # Create first user
        await db_manager.create_user(
            session,
            username=username,
            email=f"{username}@example.com",
            hashed_password="password"
        )
        
        # Try to create duplicate user
        with pytest.raises(Exception):
            await db_manager.create_user(
                session,
                username=username,
                email=f"{username}@example.com",
                hashed_password="password"
            )
