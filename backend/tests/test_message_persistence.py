# tests/test_message_persistence.py
import pytest
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import HTTPException
from message_persistence import MessagePersistenceManager
from models import Base, Message, MessageReadReceipt, User

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/cyberiad_test"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def session(test_engine):
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def message_manager(session):
    return MessagePersistenceManager(session)

@pytest.fixture
async def test_user():
    return {
        'id': uuid4(),
        'username': 'testuser'
    }

@pytest.fixture
async def test_thread():
    return {
        'id': uuid4(),
        'title': 'Test Thread'
    }

@pytest.mark.asyncio
async def test_save_message(message_manager, test_user, test_thread):
    message_data = {
        'thread_id': test_thread['id'],
        'user_id': test_user['id'],
        'content': 'Test message content',
        'metadata': {'importance': 'high'},
        'client_generated_id': str(uuid4())
    }
    
    message = await message_manager.save_message(message_data)
    
    assert message.thread_id == message_data['thread_id']
    assert message.user_id == message_data['user_id']
    assert message.content == message_data['content']
    assert message.metadata['importance'] == 'high'
    assert message.edited is False
    assert message.deleted is False
    assert isinstance(message.created_at, datetime)

@pytest.mark.asyncio
async def test_get_thread_messages(message_manager, test_thread, test_user):
    # Create multiple messages
    messages = []
    for i in range(3):
        message_data = {
            'thread_id': test_thread['id'],
            'user_id': test_user['id'],
            'content': f'Message {i}',
            'metadata': {'sequence': i}
        }
        message = await message_manager.save_message(message_data)
        messages.append(message)
    
    # Test retrieval with different parameters
    # Default retrieval
    retrieved = await message_manager.get_thread_messages(test_thread['id'])
    assert len(retrieved) == 3
    
    # Test with limit
    limited = await message_manager.get_thread_messages(test_thread['id'], limit=2)
    assert len(limited) == 2
    
    # Test with pagination
    before_id = messages[-1].id
    paginated = await message_manager.get_thread_messages(
        test_thread['id'],
        before_id=before_id
    )
    assert len(paginated) == 2

@pytest.mark.asyncio
async def test_update_message(message_manager, test_user, test_thread):
    # Create initial message
    message_data = {
        'thread_id': test_thread['id'],
        'user_id': test_user['id'],
        'content': 'Original content'
    }
    original_message = await message_manager.save_message(message_data)
    
    # Update message
    new_content = 'Updated content'
    updated_message = await message_manager.update_message(
        original_message.id,
        new_content,
        test_user['id']
    )
    
    assert updated_message.content == new_content
    assert updated_message.edited is True
    assert isinstance(updated_message.edited_at, datetime)
    assert 'edit_history' in updated_message.metadata
    assert len(updated_message.metadata['edit_history']) == 1
    assert updated_message.metadata['edit_history'][0]['content'] == 'Original content'

@pytest.mark.asyncio
async def test_soft_delete_message(message_manager, test_user, test_thread):
    message_data = {
        'thread_id': test_thread['id'],
        'user_id': test_user['id'],
        'content': 'Message to delete'
    }
    message = await message_manager.save_message(message_data)
    
    deleted_message = await message_manager.soft_delete_message(
        message.id,
        test_user['id']
    )
    
    assert deleted_message.deleted is True
    assert isinstance(deleted_message.deleted_at, datetime)
    assert deleted_message.metadata['deleted_by'] == str(test_user['id'])

@pytest.mark.asyncio
async def test_create_read_receipt(message_manager, test_user):
    message_data = {
        'thread_id': uuid4(),
        'user_id': test_user['id'],
        'content': 'Test message'
    }
    message = await message_manager.save_message(message_data)
    
    # Create read receipt
    receipt = await message_manager.create_read_receipt(
        message.id,
        test_user['id'],
        datetime.utcnow()
    )
    
    assert receipt.message_id == message.id
    assert receipt.user_id == test_user['id']
    assert isinstance(receipt.read_at, datetime)

@pytest.mark.asyncio
async def test_get_unread_count(message_manager, test_user, test_thread):
    # Create several messages
    other_user_id = uuid4()
    for _ in range(5):
        await message_manager.save_message({
            'thread_id': test_thread['id'],
            'user_id': other_user_id,
            'content': 'Unread message'
        })
    
    # Mark some as read
    messages = await message_manager.get_thread_messages(test_thread['id'])
    for message in messages[:2]:
        await message_manager.create_read_receipt(
            message.id,
            test_user['id'],
            datetime.utcnow()
        )
    
    # Check unread count
    unread_count = await message_manager.get_unread_count(
        test_thread['id'],
        test_user['id']
    )
    assert unread_count == 3

@pytest.mark.asyncio
async def test_mark_thread_read(message_manager, test_user, test_thread):
    # Create several messages
    other_user_id = uuid4()
    for _ in range(3):
        await message_manager.save_message({
            'thread_id': test_thread['id'],
            'user_id': other_user_id,
            'content': 'Message to mark read'
        })
    
    # Mark thread as read
    await message_manager.mark_thread_read(test_thread['id'], test_user['id'])
    
    # Verify all messages are marked as read
    unread_count = await message_manager.get_unread_count(
        test_thread['id'],
        test_user['id']
    )
    assert unread_count == 0

@pytest.mark.asyncio
async def test_error_handling(message_manager, test_user, test_thread):
    # Test invalid message update
    with pytest.raises(HTTPException) as exc:
        await message_manager.update_message(
            uuid4(),  # Non-existent message ID
            'New content',
            test_user['id']
        )
    assert exc.value.status_code == 404

    # Test unauthorized message update
    other_user_id = uuid4()
    message = await message_manager.save_message({
        'thread_id': test_thread['id'],
        'user_id': other_user_id,
        'content': 'Cannot update this'
    })
    
    with pytest.raises(HTTPException) as exc:
        await message_manager.update_message(
            message.id,
            'Unauthorized update',
            test_user['id']  # Different user than creator
        )
    assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_message_metadata_handling(message_manager, test_user, test_thread):
    # Test complex metadata
    complex_metadata = {
        'importance': 'high',
        'tags': ['urgent', 'follow-up'],
        'references': {
            'previous_message': str(uuid4()),
            'external_links': ['http://example.com']
        }
    }
    
    message = await message_manager.save_message({
        'thread_id': test_thread['id'],
        'user_id': test_user['id'],
        'content': 'Message with metadata',
        'metadata': complex_metadata
    })
    
    assert message.metadata == complex_metadata
    assert message.metadata['tags'][0] == 'urgent'
    assert 'previous_message' in message.metadata['references']

@pytest.mark.asyncio
async def test_concurrent_operations(message_manager, test_user, test_thread):
    # Test concurrent message creation
    async def create_message(content):
        return await message_manager.save_message({
            'thread_id': test_thread['id'],
            'user_id': test_user['id'],
            'content': content
        })
    
    # Create multiple messages concurrently
    messages = await asyncio.gather(*[
        create_message(f'Concurrent message {i}')
        for i in range(5)
    ])
    
    assert len(messages) == 5
    assert len({msg.id for msg in messages}) == 5  # All IDs should be unique
