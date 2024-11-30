import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
import gc
import psutil
import asyncio
import os
import logging
from fastapi import WebSocket
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from uuid import uuid4

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from database import DatabaseManager, engine
from models import User, Thread, Message, ThreadParticipant, ThreadAgent, AgentType, ThreadStatus
from .conftest import test_db_session, test_engine, reliability_reset

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
    """Create multiple messages with proper error handling and cleanup."""
    messages = []
    try:
        for i in range(count):
            result = await session.execute(
                text("""
                INSERT INTO messages (id, thread_id, user_id, content, created_at)
                VALUES (gen_random_uuid(), :thread_id, :user_id, :content, NOW())
                RETURNING id
                """),
                {
                    'thread_id': str(thread_id),
                    'user_id': str(user_id),
                    'content': f'Message {i}'
                }
            )
            messages.append(await result.scalar())
        await session.commit()
        return messages
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating messages: {e}")
        raise

@pytest.mark.asyncio
async def test_thread_management_reliability(test_db_session, reliability_reset, process):
    """Test thread creation and management under load."""
    await reliability_reset
    initial_memory = process.memory_info().rss
    
    try:
        # Create multiple threads concurrently
        async def create_thread(i):
            # Create a new session for each thread creation
            TestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with TestSession() as session:
                try:
                    result = await session.execute(
                        text("""
                        INSERT INTO threads (id, title, description, owner_id, status, created_at, updated_at)
                        VALUES (
                            gen_random_uuid(),
                            :title,
                            :description,
                            :owner_id::uuid,
                            'ACTIVE',
                            NOW(),
                            NOW()
                        )
                        RETURNING id
                        """),
                        {
                            'title': f'Thread {i}',
                            'description': f'Description {i}',
                            'owner_id': str(uuid4())
                        }
                    )
                    thread_id = await result.scalar()
                    await session.commit()
                    return thread_id
                except Exception as e:
                    await session.rollback()
                    raise e

        tasks = [create_thread(i) for i in range(100)]
        thread_ids = await asyncio.gather(*tasks)

        # Verify thread creation using main session
        result = await test_db_session.execute(text("SELECT COUNT(*) FROM threads"))
        count = await result.scalar()
        assert count == 100
        assert len(thread_ids) == 100

        # Check memory usage
        gc.collect()
        final_memory = process.memory_info().rss
        assert (final_memory - initial_memory) < 10 * 1024 * 1024

    except Exception as e:
        await test_db_session.rollback()
        logger.error(f"Error in thread management test: {e}")
        raise
    finally:
        await test_db_session.close()

@pytest.mark.asyncio
async def test_message_persistence_reliability(test_db_session, test_thread, reliability_reset):
    """Test message handling under heavy load."""
    await reliability_reset
    thread_id, owner_id = await test_thread
    
    try:
        # Create many messages concurrently
        tasks = []
        for batch in range(10):
            tasks.append(create_messages(test_db_session, thread_id, owner_id, 50))

        message_batches = await asyncio.gather(*tasks)
        all_messages = [msg for batch in message_batches for msg in batch]

        # Verify message creation
        result = await test_db_session.execute(
            text("SELECT COUNT(*) FROM messages WHERE thread_id = :thread_id"),
            {'thread_id': str(thread_id)}
        )
        count = await result.scalar()
        assert count == 500

    except Exception as e:
        await test_db_session.rollback()
        logger.error(f"Error in message persistence test: {e}")
        raise
    finally:
        await test_db_session.close()

@pytest.mark.asyncio
async def test_participant_management_reliability(test_db_session, test_thread, reliability_reset):
    """Test thread participant management under load."""
    await reliability_reset
    thread_id, _ = await test_thread
    
    try:
        # Add multiple participants concurrently
        async def add_participant(i):
            result = await test_db_session.execute(
                text("""
                INSERT INTO thread_participants (thread_id, user_id, joined_at, is_active)
                VALUES (:thread_id::uuid, :user_id::uuid, NOW(), true)
                RETURNING user_id
                """),
                {'thread_id': str(thread_id), 'user_id': str(uuid4())}
            )
            return await result.scalar()

        tasks = [add_participant(i) for i in range(100)]
        participant_ids = await asyncio.gather(*tasks)
        await test_db_session.commit()

        # Verify participants
        result = await test_db_session.execute(
            text("SELECT COUNT(*) FROM thread_participants WHERE thread_id = :thread_id"),
            {'thread_id': str(thread_id)}
        )
        count = await result.scalar()
        assert count == 101  # Including original participant from test_thread

    except Exception as e:
        await test_db_session.rollback()
        logger.error(f"Error in participant management test: {e}")
        raise
    finally:
        await test_db_session.close()

@pytest.mark.asyncio
async def test_agent_management_reliability(test_db_session, test_thread, reliability_reset):
    """Test thread agent management under load."""
    await reliability_reset
    thread_id, _ = await test_thread
    
    try:
        # Add multiple agents concurrently
        async def add_agent():
            result = await test_db_session.execute(
                text("""
                INSERT INTO thread_agents (id, thread_id, agent_type, is_active, created_at)
                VALUES (gen_random_uuid(), :thread_id::uuid, :agent_type, true, NOW())
                RETURNING id
                """),
                {
                    'thread_id': str(thread_id),
                    'agent_type': AgentType.LAWYER.value
                }
            )
            return await result.scalar()

        tasks = [add_agent() for _ in range(20)]
        agent_ids = await asyncio.gather(*tasks)
        await test_db_session.commit()

        # Test agent message creation
        for agent_id in agent_ids:
            await test_db_session.execute(
                text("""
                INSERT INTO messages (id, thread_id, agent_id, content, created_at)
                VALUES (gen_random_uuid(), :thread_id::uuid, :agent_id::uuid, :content, NOW())
                """),
                {
                    'thread_id': str(thread_id),
                    'agent_id': str(agent_id),
                    'content': f'Agent {agent_id} response'
                }
            )
        await test_db_session.commit()

        # Verify agents and messages
        result = await test_db_session.execute(
            text("SELECT COUNT(*) FROM thread_agents WHERE thread_id = :thread_id"),
            {'thread_id': str(thread_id)}
        )
        agent_count = await result.scalar()
        assert agent_count == 20

    except Exception as e:
        await test_db_session.rollback()
        logger.error(f"Error in agent management test: {e}")
        raise
    finally:
        await test_db_session.close()

@pytest.mark.asyncio
async def test_read_receipt_reliability(test_db_session, test_thread, reliability_reset):
    """Test read receipt handling under load."""
    await reliability_reset
    thread_id, owner_id = await test_thread
    
    try:
        # Create messages
        message_ids = await create_messages(test_db_session, thread_id, owner_id, 100)

        # Create read receipts concurrently
        async def mark_read(message_id):
            await test_db_session.execute(
                text("""
                INSERT INTO message_read_receipts (id, message_id, user_id, read_at)
                VALUES (gen_random_uuid(), :message_id::uuid, :user_id::uuid, NOW())
                """),
                {
                    'message_id': str(message_id),
                    'user_id': str(uuid4())
                }
            )

        tasks = [mark_read(msg_id) for msg_id in message_ids]
        await asyncio.gather(*tasks)
        await test_db_session.commit()

        # Verify read receipts
        result = await test_db_session.execute(
            text("""
            SELECT COUNT(*) FROM message_read_receipts 
            WHERE message_id IN (
                SELECT id FROM messages WHERE thread_id = :thread_id
            )
            """),
            {'thread_id': str(thread_id)}
        )
        count = await result.scalar()
        assert count == 100

    except Exception as e:
        await test_db_session.rollback()
        logger.error(f"Error in read receipt test: {e}")
        raise
    finally:
        await test_db_session.close()

@pytest.mark.asyncio
async def test_concurrent_operations(test_db_session, test_thread, reliability_reset):
    """Test multiple database operations happening concurrently."""
    await reliability_reset
    thread_id, owner_id = await test_thread

    try:
        async def mixed_operations(i):
            # Create message
            message_result = await test_db_session.execute(
                text("""
                INSERT INTO messages (id, thread_id, user_id, content, created_at)
                VALUES (gen_random_uuid(), :thread_id::uuid, :user_id::uuid, :content, NOW())
                RETURNING id
                """),
                {
                    'thread_id': str(thread_id),
                    'user_id': str(owner_id),
                    'content': f'Message {i}'
                }
            )
            message_id = await message_result.scalar()

            # Add participant
            await test_db_session.execute(
                text("""
                INSERT INTO thread_participants (thread_id, user_id, joined_at, is_active)
                VALUES (:thread_id::uuid, :user_id::uuid, NOW(), true)
                """),
                {
                    'thread_id': str(thread_id),
                    'user_id': str(uuid4())
                }
            )

            # Create read receipt
            await test_db_session.execute(
                text("""
                INSERT INTO message_read_receipts (id, message_id, user_id, read_at)
                VALUES (gen_random_uuid(), :message_id::uuid, :user_id::uuid, NOW())
                """),
                {
                    'message_id': str(message_id),
                    'user_id': str(uuid4())
                }
            )

        tasks = [mixed_operations(i) for i in range(50)]
        await asyncio.gather(*tasks)
        await test_db_session.commit()

        # Verify final state
        async def verify_counts():
            message_count = await test_db_session.execute(
                text("SELECT COUNT(*) FROM messages WHERE thread_id = :thread_id"),
                {'thread_id': str(thread_id)}
            )
            participant_count = await test_db_session.execute(
                text("SELECT COUNT(*) FROM thread_participants WHERE thread_id = :thread_id"),
                {'thread_id': str(thread_id)}
            )
            receipt_count = await test_db_session.execute(
                text("""
                SELECT COUNT(*) FROM message_read_receipts
                WHERE message_id IN (SELECT id FROM messages WHERE thread_id = :thread_id)
                """),
                {'thread_id': str(thread_id)}
            )
            return (
                await message_count.scalar(),
                await participant_count.scalar(),
                await receipt_count.scalar()
            )

        msg_count, part_count, receipt_count = await verify_counts()
        assert msg_count == 50  # New messages from this test
        assert part_count == 51  # 50 new + 1 original
        assert receipt_count == 50  # One receipt per message

    except Exception as e:
        await test_db_session.rollback()
        logger.error(f"Error in concurrent operations test: {e}")
        raise
    finally:
        await test_db_session.close()

@pytest.mark.asyncio
async def test_database_recovery(test_db_session, test_thread, reliability_reset):
    """Test database recovery after simulated failures."""
    await reliability_reset
    thread_id, owner_id = await test_thread

    try:
        # Simulate transaction failure
        async with test_db_session.begin() as transaction:
            await create_messages(test_db_session, thread_id, owner_id, 10)
            await transaction.rollback()

        # Verify database state is clean
        result = await test_db_session.execute(
            text("""
            SELECT COUNT(*) FROM messages
            WHERE thread_id = :thread_id AND created_at > (
                SELECT created_at FROM threads WHERE id = :thread_id
            )
            """),
            {'thread_id': str(thread_id)}
        )
        count = await result.scalar()
        assert count == 0, "Database should be clean after rollback"

        # Verify can continue operations
        await create_messages(test_db_session, thread_id, owner_id, 5)
        result = await test_db_session.execute(
            text("SELECT COUNT(*) FROM messages WHERE thread_id = :thread_id"),
            {'thread_id': str(thread_id)}
        )
        count = await result.scalar()
        assert count == 5, "Should be able to create new messages after rollback"

        # Test partial failure recovery
        async with test_db_session.begin() as transaction:
            try:
                # This should fail due to duplicate participants
                await test_db_session.execute(
                    text("""
                    INSERT INTO thread_participants (thread_id, user_id, joined_at, is_active)
                    VALUES (:thread_id::uuid, :user_id::uuid, NOW(), true)
                    """),
                    {
                        'thread_id': str(thread_id),
                        'user_id': str(owner_id)  # This is already a participant
                    }
                )
            except Exception:
                await transaction.rollback()
                logger.info("Expected failure handled correctly")

        # Verify system remains operational
        new_messages = await create_messages(test_db_session, thread_id, owner_id, 3)
        assert len(new_messages) == 3, "Should be able to create messages after handled failure"

    except Exception as e:
        await test_db_session.rollback()
        logger.error(f"Error in database recovery test: {e}")
        raise
    finally:
        await test_db_session.close()
