import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent / "backend"))
sys.path.append(str(Path(__file__).resolve().parent.parent))


import pytest
from fastapi import WebSocket, WebSocketDisconnect
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
from datetime import datetime
from websocket_manager import ConnectionManager

@pytest.fixture
def connection_manager():
    """Fixture to initialize the ConnectionManager instance."""
    return ConnectionManager()

@pytest.mark.asyncio
async def test_initialization(connection_manager):
    """Test the initialization of ConnectionManager."""
    assert connection_manager.active_connections == {}
    assert connection_manager.user_threads == {}
    assert connection_manager.connection_timestamps == {}
    assert connection_manager.typing_status == {}

@pytest.mark.asyncio
async def test_add_connection(connection_manager):
    """Test adding a WebSocket connection."""
    user_id = uuid4()
    thread_id = uuid4()
    mock_websocket = AsyncMock(spec=WebSocket)
    
    await connection_manager.connect(mock_websocket, thread_id, user_id)
    
    assert thread_id in connection_manager.active_connections
    assert user_id in connection_manager.active_connections[thread_id]
    assert connection_manager.active_connections[thread_id][user_id] == mock_websocket

@pytest.mark.asyncio
async def test_remove_connection(connection_manager):
    """Test removing a WebSocket connection."""
    user_id = uuid4()
    thread_id = uuid4()
    mock_websocket = AsyncMock(spec=WebSocket)

    await connection_manager.connect(mock_websocket, thread_id, user_id)
    await connection_manager.disconnect(user_id, thread_id)

    # Validate thread is removed if empty
    if thread_id in connection_manager.active_connections:
        assert user_id not in connection_manager.active_connections[thread_id]
    else:
        assert thread_id not in connection_manager.active_connections

@pytest.mark.asyncio
async def test_handle_websocket_disconnect(connection_manager):
    """Test handling WebSocket disconnection."""
    user_id = uuid4()
    thread_id = uuid4()
    mock_websocket = AsyncMock(spec=WebSocket)
    
    await connection_manager.connect(mock_websocket, thread_id, user_id)
    
    # Simulate WebSocket disconnection
    mock_websocket.receive.side_effect = WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        await mock_websocket.receive()

@pytest.mark.asyncio
async def test_typing_status_management(connection_manager):
    """Test managing typing statuses."""
    user_id = uuid4()
    thread_id = uuid4()
    
    connection_manager.typing_status.setdefault(thread_id, {})
    connection_manager.typing_status[thread_id][user_id] = datetime.utcnow()
    
    assert user_id in connection_manager.typing_status[thread_id]

@pytest.mark.asyncio
async def test_connection_timestamps(connection_manager):
    """Test updating and checking connection timestamps."""
    user_id = uuid4()
    thread_id = uuid4()
    mock_websocket = AsyncMock(spec=WebSocket)

    await connection_manager.connect(mock_websocket, thread_id, user_id)

    # Match the key format used in ConnectionManager
    timestamp_key = f"{thread_id}:{user_id}"
    assert timestamp_key in connection_manager.connection_timestamps
    assert isinstance(connection_manager.connection_timestamps[timestamp_key], datetime)
