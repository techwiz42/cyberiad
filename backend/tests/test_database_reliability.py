# tests/test_database_reliability.py
import pytest
import gc
import psutil
import asyncio
import os
import sys
from pathlib import Path
import weakref
from fastapi import WebSocket
from sqlalchemy import text
from datetime import datetime, timedelta
from uuid import uuid4

sys.path.append(str(Path(__file__).resolve().parent / "backend"))
sys.path.append(str(Path(__file__).resolve().parent.parent))

from .conftest import test_engine, test_db_session, reset_db
from database import DatabaseManager
from models import Thread, Message, ThreadParticipant, ThreadAgent, AgentType

class MockWebSocket:
    def __init__(self):
        self.sent_messages = []
        self.closed = False
        
    async def send_text(self, message):
        self.sent_messages.append(message)
        
    async def close(self):
        self.closed = True

@pytest.fixture
def process():
    return psutil.Process(os.getpid())

async def create_messages(session, thread_id, user_id, count):
    messages = []
    for i in range(count):
        result = await session.execute(
            text("""
            INSERT INTO messages (thread_id, user_id, content)
            VALUES (:thread_id, :user_id, :content)
            RETURNING id
            """),
            {
                'thread_id': thread_id,
                'user_id': user_id,
                'content': f'Message {i}'
            }
        )
        messages.append(await result.scalar())
    await session.commit()
    return messages

@pytest.mark.asyncio
async def test_thread_management_reliability(test_db_session, reset_db, process):
    """Test thread creation and management under load."""
    await reset_db
    initial_memory = process.memory_info().rss
    
    # Create multiple threads concurrently
    async def create_thread(i):
        result = await test_db_session.execute(
            text("""
            INSERT INTO threads (title, description, owner_id)
            VALUES (:title, :description, :owner_id)
            RETURNING id
            """),
            {
                'title': f'Thread {i}',
                'description': f'Description {i}',
                'owner_id': str(uuid4())
            }
        )
        return await result.scalar()
    
    tasks = [create_thread(i) for i in range(100)]
    thread_ids = await asyncio.gather(*tasks)
    await test_db_session.commit()
    
    # Verify thread creation
    result = await test_db_session.execute(
        text("SELECT COUNT(*) FROM threads")
    )
    count = await result.scalar()
    assert count == 100
    assert len(thread_ids) == 100
    
    # Check memory usage
    gc.collect()
    final_memory = process.memory_info().rss
    assert (final_memory - initial_memory) < 10 * 1024 * 1024
    
@pytest.mark.asyncio
async def test_message_persistence_reliability(test_db_session, test_thread, reset_db):
    """Test message handling under heavy load."""
    await reset_db
    thread_id, owner_id = await test_thread
    
    # Create many messages concurrently
    tasks = []
    for batch in range(10):
        tasks.append(create_messages(test_db_session, thread_id, owner_id, 50))
    
    message_batches = await asyncio.gather(*tasks)
    all_messages = [msg for batch in message_batches for msg in batch]
    
    # Verify message creation
    result = await test_db_session.execute(
        text("SELECT COUNT(*) FROM messages WHERE thread_id = :thread_id"),
        {'thread_id': thread_id}
    )
    count = await result.scalar()
    assert count == 500

@pytest.mark.asyncio
async def test_websocket_connection_reliability(test_db_session, test_thread, reset_db):
    """Test WebSocket connection management under load."""
    await reset_db
    thread_id, _ = await test_thread
    
    db_manager = DatabaseManager()
    
    # Create multiple WebSocket connections
    connections = {}
    for i in range(50):
        user_id = uuid4()
        ws = MockWebSocket()
        await db_manager.add_active_connection(thread_id, user_id, ws)
        connections[user_id] = ws
    
    # Broadcast messages
    for i in range(10):
        sender_id = list(connections.keys())[0]
        await db_manager.broadcast_to_thread(thread_id, sender_id, f"Broadcast {i}")
    
    # Verify message delivery
    for ws in list(connections.values())[1:]:  # Exclude sender
        assert len(ws.sent_messages) == 10
    
    # Test connection cleanup
    for user_id in connections:
        await db_manager.remove_active_connection(thread_id, user_id)

@pytest.mark.asyncio
async def test_participant_management_reliability(test_db_session, test_thread, reset_db):
    """Test thread participant management under load."""
    await reset_db
    thread_id, _ = await test_thread
    
    # Add multiple participants concurrently
    async def add_participant(i):
        result = await test_db_session.execute(
            text("""
            INSERT INTO thread_participants (thread_id, user_id)
            VALUES (:thread_id, :user_id)
            RETURNING user_id
            """),
            {'thread_id': thread_id, 'user_id': str(uuid4())}
        )
        return await result.scalar()
    
    tasks = [add_participant(i) for i in range(100)]
    participant_ids = await asyncio.gather(*tasks)
    
    # Verify participants
    result = await test_db_session.execute(
        text("SELECT COUNT(*) FROM thread_participants WHERE thread_id = :thread_id"),
        {'thread_id': thread_id}
    )
    count = await result.scalar()
    assert count == 100

@pytest.mark.asyncio
async def test_agent_management_reliability(test_db_session, test_thread, reset_db):
    """Test thread agent management under load."""
    await reset_db
    thread_id, _ = await test_thread
    
    # Add multiple agents concurrently
    async def add_agent():
        result = await test_db_session.execute(
            text("""
            INSERT INTO thread_agents (thread_id, agent_type)
            VALUES (:thread_id, :agent_type)
            RETURNING id
            """),
            {
                'thread_id': thread_id,
                'agent_type': AgentType.LAWYER.value
            }
        )
        return await result.scalar()
    
    tasks = [add_agent() for _ in range(20)]
    agent_ids = await asyncio.gather(*tasks)
    
    # Test agent message creation
    for agent_id in agent_ids:
        await test_db_session.execute(
            text("""
            INSERT INTO messages (thread_id, agent_id, content)
            VALUES (:thread_id, :agent_id, :content)
            """),
            {
                'thread_id': thread_id,
                'agent_id': agent_id,
                'content': f'Agent {agent_id} response'
            }
        )
    
    await test_db_session.commit()

@pytest.mark.asyncio
async def test_read_receipt_reliability(test_db_session, test_thread, reset_db):
    """Test read receipt handling under load."""
    await reset_db
    thread_id, owner_id = await test_thread
    
    # Create messages
    message_ids = await create_messages(test_db_session, thread_id, owner_id, 100)
    
    # Create read receipts concurrently
    async def mark_read(message_id):
        await test_db_session.execute(
            text("""
            INSERT INTO message_read_receipts (message_id, user_id, read_at)
            VALUES (:message_id, :user_id, :read_at)
            """),
            {
                'message_id': message_id,
                'user_id': str(uuid4()),
                'read_at': datetime.utcnow()
            }
        )
    
    tasks = [mark_read(msg_id) for msg_id in message_ids]
    await asyncio.gather(*tasks)
    await test_db_session.commit()

@pytest.mark.asyncio
async def test_concurrent_operations(test_db_session, test_thread, reset_db):
    """Test multiple database operations happening concurrently."""
    await reset_db
    thread_id, owner_id = await test_thread
    
    async def mixed_operations(i):
        # Create message
        message_result = await test_db_session.execute(
            text("""
            INSERT INTO messages (thread_id, user_id, content)
            VALUES (:thread_id, :user_id, :content)
            RETURNING id
            """),
            {
                'thread_id': thread_id,
                'user_id': owner_id,
                'content': f'Message {i}'
            }
        )
        message_id = await message_result.scalar()
        
        # Add participant
        await test_db_session.execute(
            text("""
            INSERT INTO thread_participants (thread_id, user_id)
            VALUES (:thread_id, :user_id)
            """),
            {'thread_id': thread_id, 'user_id': str(uuid4())}
        )
        
        # Create read receipt
        await test_db_session.execute(
            text("""
            INSERT INTO message_read_receipts (message_id, user_id, read_at)
            VALUES (:message_id, :user_id, :read_at)
            """),
            {
                'message_id': message_id,
                'user_id': str(uuid4()),
                'read_at': datetime.utcnow()
            }
        )
    
    tasks = [mixed_operations(i) for i in range(50)]
    await asyncio.gather(*tasks)
    await test_db_session.commit()

@pytest.mark.asyncio
async def test_database_recovery(test_db_session, test_thread, reset_db):
    """Test database recovery after simulated failures."""
    await reset_db
    thread_id, owner_id = await test_thread
    
    # Simulate transaction failure
    async with test_db_session.begin() as transaction:
        await create_messages(test_db_session, thread_id, owner_id, 10)
        await transaction.rollback()
    
    # Verify database state is clean
    result = await test_db_session.execute(
        text("SELECT COUNT(*) FROM messages WHERE thread_id = :thread_id"),
        {'thread_id': thread_id}
    )
    count = await result.scalar()
    assert count == 0
    
    # Verify can continue operations
    await create_messages(test_db_session, thread_id, owner_id, 5)
    result = await test_db_session.execute(
        text("SELECT COUNT(*) FROM messages WHERE thread_id = :thread_id"),
        {'thread_id': thread_id}
    )
    count = await result.scalar()
    assert count == 5