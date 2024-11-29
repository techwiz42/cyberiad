# tests/test_websocket_manager.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi import WebSocket, WebSocketDisconnect
from uuid import UUID, uuid4
import json
import asyncio
from typing import Dict, Set
from websocket_manager import WebSocketManager, ConnectionManager

class MockWebSocket:
    def __init__(self):
        self.sent_messages = []
        self.accept = AsyncMock()
        self.close = AsyncMock()
        self.receive_text = AsyncMock()
        self.send_text = AsyncMock()
        
    async def send_json(self, data: dict):
        self.sent_messages.append(data)
        
    def reset_mocks(self):
        self.accept.reset_mock()
        self.close.reset_mock()
        self.sent_messages = []

@pytest.fixture
def websocket():
    return MockWebSocket()

@pytest.fixture
def connection_manager():
    return ConnectionManager()

@pytest.mark.asyncio
async def test_connect(connection_manager, websocket):
    thread_id = uuid4()
    user_id = uuid4()
    
    await connection_manager.connect(websocket, thread_id, user_id)
    
    # Verify connection was established
    websocket.accept.assert_called_once()
    assert connection_manager._active_connections[thread_id][user_id] == websocket

@pytest.mark.asyncio
async def test_disconnect(connection_manager, websocket):
    thread_id = uuid4()
    user_id = uuid4()
    
    # First connect
    await connection_manager.connect(websocket, thread_id, user_id)
    
    # Then disconnect
    await connection_manager.disconnect(thread_id, user_id)
    
    # Verify connection was removed
    assert thread_id not in connection_manager._active_connections or \
           user_id not in connection_manager._active_connections[thread_id]

@pytest.mark.asyncio
async def test_broadcast(connection_manager):
    # Set up multiple mock websockets
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    ws3 = MockWebSocket()
    
    thread_id = uuid4()
    user1_id = uuid4()
    user2_id = uuid4()
    user3_id = uuid4()
    
    # Connect multiple users
    await connection_manager.connect(ws1, thread_id, user1_id)
    await connection_manager.connect(ws2, thread_id, user2_id)
    await connection_manager.connect(ws3, thread_id, user3_id)
    
    # Test broadcast
    message = "Test broadcast message"
    sender_id = user1_id
    
    await connection_manager.broadcast(thread_id, sender_id, message)
    
    # Verify that other users received the message but not the sender
    assert not ws1.send_text.called  # sender shouldn't receive their own message
    ws2.send_text.assert_called_once_with(message)
    ws3.send_text.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_handle_client_message(connection_manager, websocket):
    thread_id = uuid4()
    user_id = uuid4()
    
    # Set up receive_text to return a message and then raise WebSocketDisconnect
    websocket.receive_text.side_effect = [
        '{"type": "message", "content": "Hello"}',
        WebSocketDisconnect()
    ]
    
    await connection_manager.connect(websocket, thread_id, user_id)
    
    # Handle messages until disconnect
    await connection_manager.handle_client_message(websocket, thread_id, user_id)
    
    # Verify message was received
    websocket.receive_text.assert_called()
    assert thread_id not in connection_manager._active_connections

@pytest.mark.asyncio
async def test_send_personal_message(connection_manager, websocket):
    thread_id = uuid4()
    user_id = uuid4()
    
    await connection_manager.connect(websocket, thread_id, user_id)
    
    message = "Personal message"
    await connection_manager.send_personal_message(thread_id, user_id, message)
    
    websocket.send_text.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_connection_cleanup(connection_manager):
    # Create some stale connections
    stale_thread_id = uuid4()
    stale_user_id = uuid4()
    stale_ws = MockWebSocket()
    stale_ws.close.side_effect = Exception("Connection already closed")
    
    await connection_manager.connect(stale_ws, stale_thread_id, stale_user_id)
    
    # Run cleanup
    await connection_manager.cleanup_connections()
    
    # Verify stale connections were removed
    assert stale_thread_id not in connection_manager._active_connections

@pytest.mark.asyncio
async def test_close_all_connections(connection_manager):
    # Set up multiple connections
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    
    thread_id = uuid4()
    user1_id = uuid4()
    user2_id = uuid4()
    
    await connection_manager.connect(ws1, thread_id, user1_id)
    await connection_manager.connect(ws2, thread_id, user2_id)
    
    # Close all connections
    await connection_manager.close_all_connections()
    
    # Verify all connections were closed
    ws1.close.assert_called_once()
    ws2.close.assert_called_once()
    assert not connection_manager._active_connections

@pytest.mark.asyncio
async def test_handle_invalid_message(connection_manager, websocket):
    thread_id = uuid4()
    user_id = uuid4()
    
    # Set up invalid JSON message
    websocket.receive_text.side_effect = ["invalid json", WebSocketDisconnect()]
    
    await connection_manager.connect(websocket, thread_id, user_id)
    
    # Handle messages until disconnect
    await connection_manager.handle_client_message(websocket, thread_id, user_id)
    
    # Verify connection was closed due to invalid message
    websocket.close.assert_called_once()

@pytest.mark.asyncio
async def test_concurrent_connections(connection_manager):
    # Test handling multiple concurrent connections
    thread_id = uuid4()
    num_users = 5
    users = []
    
    for _ in range(num_users):
        user_id = uuid4()
        ws = MockWebSocket()
        users.append((user_id, ws))
        await connection_manager.connect(ws, thread_id, user_id)
    
    # Verify all connections were established
    assert len(connection_manager._active_connections[thread_id]) == num_users
    
    # Test broadcasting to all connections
    message = "Broadcast test"
    await connection_manager.broadcast(thread_id, users[0][0], message)
    
    # Verify message was received by all except sender
    for user_id, ws in users[1:]:
        ws.send_text.assert_called_once_with(message)
    assert not users[0][1].send_text.called

@pytest.mark.asyncio
async def test_reconnection(connection_manager, websocket):
    thread_id = uuid4()
    user_id = uuid4()
    
    # Initial connection
    await connection_manager.connect(websocket, thread_id, user_id)
    
    # Disconnect
    await connection_manager.disconnect(thread_id, user_id)
    
    # Reconnect
    new_websocket = MockWebSocket()
    await connection_manager.connect(new_websocket, thread_id, user_id)
    
    # Verify new connection is active
    assert connection_manager._active_connections[thread_id][user_id] == new_websocket
