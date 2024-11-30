import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent / "backend"))
sys.path.append(str(Path(__file__).resolve().parent.parent))


import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import datetime, timezone
from message_persistence import MessagePersistenceManager
from models import Message, User

@pytest.fixture
def mock_user():
    """Fixture to provide a mock user for tests."""
    return User(id=uuid4(), username="test_user", email="test@example.com")

@pytest.fixture
def mock_message(mock_user):
    """Fixture to provide a mock message for tests."""
    return Message(
        id=uuid4(),
        content="Test message",
        created_at=datetime.now(timezone.utc),  # Updated for timezone-aware datetime
        user_id=mock_user.id,  # Updated from sender_id to user_id
        thread_id=uuid4()
    )

async def test_create_message(test_db_session: AsyncSession, mock_user):
    """Test creating a new message."""
    manager = MessagePersistenceManager(test_db_session)
    message_content = "This is a test message."
    thread_id = uuid4()

    new_message = await manager.create_message(
        content=message_content,
        user_id=mock_user.id,
        thread_id=thread_id
    )

    assert new_message.content == message_content
    assert new_message.user_id == mock_user.id
    assert new_message.thread_id == thread_id


@pytest.mark.asyncio
async def test_get_messages_by_thread(test_db_session: AsyncSession, mock_message):
    """Test retrieving messages by thread."""
    manager = MessagePersistenceManager(test_db_session)
    thread_id = mock_message.thread_id

    # Add a message to the database
    test_db_session.add(mock_message)
    await test_db_session.commit()

    # Retrieve messages by thread ID
    messages = await manager.get_messages_by_thread(thread_id=thread_id)

    assert len(messages) == 1
    assert messages[0].id == mock_message.id
    assert messages[0].content == mock_message.content

@pytest.mark.asyncio
async def test_update_message_status(test_db_session: AsyncSession, mock_message):
    """Test updating a message's status (e.g., read receipt)."""
    manager = MessagePersistenceManager(test_db_session)
    
    # Add a message to the database
    test_db_session.add(mock_message)
    await test_db_session.commit()

    # Update message read status
    await manager.mark_message_as_read(message_id=mock_message.id)

    # Verify the update in the database
    result = await test_db_session.execute(select(Message).where(Message.id == mock_message.id))
    updated_message = result.scalar_one()

    assert updated_message.read_at is not None

@pytest.mark.asyncio
async def test_delete_message(test_db_session: AsyncSession, mock_message):
    """Test deleting a message."""
    manager = MessagePersistenceManager(test_db_session)
    
    # Add a message to the database
    test_db_session.add(mock_message)
    await test_db_session.commit()

    # Delete the message
    await manager.delete_message(message_id=mock_message.id)

    # Verify the message is removed
    result = await test_db_session.execute(select(Message).where(Message.id == mock_message.id))
    deleted_message = result.scalar_one_or_none()

    assert deleted_message is None

@pytest.mark.asyncio
async def test_handle_invalid_message_id(test_db_session: AsyncSession):
    """Test handling invalid message ID during retrieval."""
    manager = MessagePersistenceManager(test_db_session)
    invalid_message_id = uuid4()

    with pytest.raises(ValueError):
        await manager.get_message_by_id(message_id=invalid_message_id)

