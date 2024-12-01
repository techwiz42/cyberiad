import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
import gc
import asyncio
import psutil
import weakref
from datetime import datetime
import uuid
from fastapi import WebSocket
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from models import User, Thread, Message, ThreadParticipant
from database import DatabaseManager
from websocket_manager import ConnectionManager
from .conftest import test_db_session

def get_process_memory():
    """Get current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

async def count_db_connections(session):
    """Count active database connections."""
    result = await session.execute(
        text("""
        SELECT count(*) 
        FROM pg_stat_activity 
        WHERE datname = current_database()
        """)
    )
    return result.scalar()

class MockWebSocket:
    """Mock WebSocket class for testing."""
    def __init__(self):
        self.closed = False
        self._accepted = False
        
    async def accept(self):
        self._accepted = True
    
    async def send_text(self, data: str):
        if not self._accepted or self.closed:
            raise RuntimeError("WebSocket is not connected or is closed")
    
    async def close(self):
        self.closed = True
        self._accepted = False

class MockConnectionManager(ConnectionManager):
    """Mock connection manager for testing."""
    async def disconnect(self, thread_id: uuid.UUID, user_id: uuid.UUID):
        if thread_id in self.active_connections and user_id in self.active_connections[thread_id]:
            ws = self.active_connections[thread_id][user_id]
            await ws.close()
            del self.active_connections[thread_id][user_id]
            if not self.active_connections[thread_id]:
                del self.active_connections[thread_id]

@pytest.mark.asyncio
async def test_database_connection_leaks(test_db_session):
    """Test that database connections are properly closed."""
    async with test_db_session as session:
        initial_count = await count_db_connections(session)
        
        # Perform multiple queries sequentially
        for _ in range(50):
            await session.execute(text("SELECT 1"))
            await session.commit()
        
        # Force garbage collection
        gc.collect()
        await asyncio.sleep(0.1)  # Allow connections to close
        
        final_count = await count_db_connections(session)
        assert final_count <= initial_count + 1  # +1 for the counting query itself

@pytest.mark.asyncio
async def test_websocket_connection_cleanup():
    """Test that WebSocket connections are properly cleaned up."""
    connection_manager = MockConnectionManager()
    websockets = []
    
    # Create multiple WebSocket connections
    for i in range(5):
        ws = MockWebSocket()
        thread_id = uuid.uuid4()
        user_id = uuid.uuid4()
        await connection_manager.connect(ws, thread_id, user_id)
        websockets.append((thread_id, user_id, ws))
    
    # Disconnect all connections sequentially
    for thread_id, user_id, ws in websockets:
        await connection_manager.disconnect(thread_id, user_id)
        assert ws.closed, f"WebSocket for user {user_id} was not properly closed"
    
    # Verify cleanup
    assert len(connection_manager.active_connections) == 0, "Active connections not cleared"

@pytest.mark.asyncio
async def test_sequential_access(test_db_session):
    """Test database behavior with sequential operations."""
    async with test_db_session as session:
        # Create test user
        user = User(
            username=f"sequential_test_{uuid.uuid4().hex}",
            email="sequential@test.com",
            hashed_password="test",
            created_at=datetime.now()
        )
        session.add(user)
        await session.commit()
        user_id = user.id

        # Create threads sequentially
        thread_ids = []
        for i in range(5):
            thread = Thread(
                title=f"Thread {uuid.uuid4().hex}",
                owner_id=user_id,
                created_at=datetime.now()
            )
            session.add(thread)
            await session.commit()
            thread_ids.append(thread.id)

        # Create messages sequentially
        for thread_id in thread_ids:
            for i in range(10):
                message = Message(
                    thread_id=thread_id,
                    user_id=user_id,
                    content=f"Message {i}",
                    created_at=datetime.now()
                )
                session.add(message)
                await session.commit()

            # Verify message count immediately after creation
            result = await session.execute(
                select(Message).where(Message.thread_id == thread_id)
            )
            messages = result.scalars().all()
            assert len(messages) == 10, f"Thread {thread_id} has incorrect message count"

@pytest.mark.asyncio
async def test_memory_growth(test_db_session):
    """Test for memory leaks during database operations."""
    initial_memory = get_process_memory()
    peak_memory = initial_memory
    
    async with test_db_session as session:
        # Perform multiple database operations sequentially
        for i in range(100):
            user = User(
                username=f"user_{uuid.uuid4().hex}",
                email=f"user_{i}@test.com",
                hashed_password="test",
                created_at=datetime.now()
            )
            session.add(user)
            await session.flush()
            await session.commit()
            
            current_memory = get_process_memory()
            peak_memory = max(peak_memory, current_memory)
    
        # Force garbage collection
        gc.collect()
        await asyncio.sleep(0.1)  # Allow memory to be freed
        
        final_memory = get_process_memory()
        memory_growth = final_memory - initial_memory
        
        # Allow for some memory overhead but fail if it's excessive
        assert memory_growth < 50, f"Excessive memory growth detected: {memory_growth}MB"

@pytest.mark.asyncio
async def test_connection_cleanup_under_error(test_db_session):
    """Test connection cleanup when errors occur."""
    initial_memory = get_process_memory()
    connection_count_start = 0
    ws_manager = MockConnectionManager()
    
    async with test_db_session as session:
        connection_count_start = await count_db_connections(session)
        
        # Create some websockets that will error
        websockets = []
        for i in range(10):
            ws = MockWebSocket()
            thread_id = uuid.uuid4()
            user_id = uuid.uuid4()
            await ws_manager.connect(ws, thread_id, user_id)
            websockets.append((thread_id, user_id, ws))
            
        # Simulate errors and disconnections
        for thread_id, user_id, ws in websockets[:5]:
            # Simulate crash without proper cleanup
            ws._accepted = False
            ws.closed = False
            del ws_manager.active_connections[thread_id][user_id]
            
        # Force cleanup
        gc.collect()
        await asyncio.sleep(0.1)
        
        # Check DB connections
        connection_count_end = await count_db_connections(session)
        assert connection_count_end <= connection_count_start + 1, "Database connections leaked"
        
        # Check websocket manager state
        active_connections = len([conn 
                                for conns in ws_manager.active_connections.values() 
                                for conn in conns.values()])
        assert active_connections == 5, "WebSocket connections leaked"
        
        # Check memory
        final_memory = get_process_memory()
        memory_growth = final_memory - initial_memory
        assert memory_growth < 10, f"Memory leaked: {memory_growth}MB growth"

@pytest.mark.asyncio
async def test_sustained_load(test_db_session):
    """Test resource cleanup under sustained load."""
    initial_memory = get_process_memory()
    peak_memory = initial_memory
    memory_samples = []
    
    async with test_db_session as session:
        # Record initial connection count
        start_connections = await count_db_connections(session)
        
        # Create websocket manager
        ws_manager = MockConnectionManager()
        
        # Run sustained load for 60 virtual users over 10 "cycles"
        for cycle in range(10):
            # Create some DB load
            for i in range(60):
                user = User(
                    username=f"user_{cycle}_{uuid.uuid4().hex}",
                    email=f"user_{cycle}_{i}@test.com",
                    hashed_password="test",
                    created_at=datetime.now()
                )
                session.add(user)
                await session.commit()
            
            # Create some websocket load
            websockets = []
            for i in range(60):
                ws = MockWebSocket()
                thread_id = uuid.uuid4()
                user_id = uuid.uuid4()
                await ws_manager.connect(ws, thread_id, user_id)
                websockets.append((thread_id, user_id, ws))
            
            # Cleanup websockets
            for thread_id, user_id, ws in websockets:
                await ws_manager.disconnect(thread_id, user_id)
            
            # Force GC
            gc.collect()
            await asyncio.sleep(0.1)
            
            # Sample memory
            current_memory = get_process_memory()
            memory_samples.append(current_memory)
            peak_memory = max(peak_memory, current_memory)
        
        # Final checks
        end_connections = await count_db_connections(session)
        assert end_connections <= start_connections + 1, "Database connections leaked"
        
        assert len(ws_manager.active_connections) == 0, "WebSocket connections leaked"
        
        # Check memory stability
        memory_variation = max(memory_samples) - min(memory_samples)
        assert memory_variation < 50, f"Memory usage unstable: {memory_variation}MB variation"
        
        final_memory = get_process_memory()
        memory_growth = final_memory - initial_memory
        assert memory_growth < 50, f"Memory leaked: {memory_growth}MB growth"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
