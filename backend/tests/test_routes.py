# tests/test_routes.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch
from routes import auth_router, thread_router, message_router, agent_router
from fastapi import FastAPI, HTTPException
from database import DatabaseManager
from auth import Token
import json
from uuid import UUID, uuid4

# Create test app
app = FastAPI()
app.include_router(auth_router)
app.include_router(thread_router)
app.include_router(message_router)
app.include_router(agent_router)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_db():
    return AsyncMock(spec=DatabaseManager)

@pytest.fixture
def mock_token():
    return {
        "access_token": "test_token",
        "token_type": "bearer",
        "user_id": str(uuid4()),
        "username": "testuser"
    }

# Auth Routes Tests
@pytest.mark.asyncio
async def test_register_user(client, mock_db):
    with patch('routes.db_manager', mock_db):
        response = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert "token_type" in response.json()
        mock_db.create_user.assert_called_once()

@pytest.mark.asyncio
async def test_register_duplicate_user(client, mock_db):
    mock_db.get_user_by_username.return_value = {"username": "existinguser"}
    
    with patch('routes.db_manager', mock_db):
        response = client.post(
            "/api/auth/register",
            json={
                "username": "existinguser",
                "email": "existing@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 400
        assert "User already exists" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login(client, mock_db, mock_token):
    mock_db.authenticate_user.return_value = True
    
    with patch('routes.auth_manager.create_access_token', return_value=mock_token["access_token"]):
        response = client.post(
            "/api/auth/token",
            data={
                "username": "testuser",
                "password": "password123"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["access_token"] == mock_token["access_token"]

# Thread Routes Tests
@pytest.mark.asyncio
async def test_create_thread(client, mock_db, mock_token):
    thread_id = uuid4()
    mock_db.create_thread.return_value = {"id": str(thread_id), "title": "Test Thread"}
    
    with patch('routes.auth_manager.get_current_user', return_value={"id": mock_token["user_id"]}):
        response = client.post(
            "/api/threads/",
            headers={"Authorization": f"Bearer {mock_token['access_token']}"},
            json={
                "title": "Test Thread",
                "description": "Test Description",
                "agent_roles": ["doctor", "lawyer"]
            }
        )
        
        assert response.status_code == 201
        assert response.json()["title"] == "Test Thread"
        mock_db.create_thread.assert_called_once()

@pytest.mark.asyncio
async def test_get_threads(client, mock_db, mock_token):
    mock_threads = [
        {"id": str(uuid4()), "title": "Thread 1"},
        {"id": str(uuid4()), "title": "Thread 2"}
    ]
    mock_db.get_user_threads.return_value = mock_threads
    
    with patch('routes.auth_manager.get_current_user', return_value={"id": mock_token["user_id"]}):
        response = client.get(
            "/api/threads/",
            headers={"Authorization": f"Bearer {mock_token['access_token']}"}
        )
        
        assert response.status_code == 200
        assert len(response.json()) == 2
        mock_db.get_user_threads.assert_called_once()

# Message Routes Tests
@pytest.mark.asyncio
async def test_send_message(client, mock_db, mock_token):
    thread_id = uuid4()
    message_id = uuid4()
    mock_db.is_thread_participant.return_value = True
    mock_db.create_message.return_value = {
        "id": str(message_id),
        "content": "Test message"
    }
    mock_db.get_thread_agents.return_value = []
    
    with patch('routes.auth_manager.get_current_user', return_value={"id": mock_token["user_id"]}):
        response = client.post(
            f"/api/messages/{thread_id}",
            headers={"Authorization": f"Bearer {mock_token['access_token']}"},
            json={"content": "Test message"}
        )
        
        assert response.status_code == 200
        assert "user_message" in response.json()
        mock_db.create_message.assert_called_once()

@pytest.mark.asyncio
async def test_get_messages(client, mock_db, mock_token):
    thread_id = uuid4()
    mock_messages = [
        {"id": str(uuid4()), "content": "Message 1"},
        {"id": str(uuid4()), "content": "Message 2"}
    ]
    mock_db.is_thread_participant.return_value = True
    mock_db.get_thread_messages.return_value = mock_messages
    
    with patch('routes.auth_manager.get_current_user', return_value={"id": mock_token["user_id"]}):
        response = client.get(
            f"/api/messages/{thread_id}",
            headers={"Authorization": f"Bearer {mock_token['access_token']}"}
        )
        
        assert response.status_code == 200
        assert len(response.json()) == 2
        mock_db.get_thread_messages.assert_called_once()

# Agent Routes Tests
@pytest.mark.asyncio
async def test_get_available_agents(client):
    response = client.get("/api/agents/roles")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "doctor" in response.json()
    assert "lawyer" in response.json()

@pytest.mark.asyncio
async def test_toggle_agent(client, mock_db, mock_token):
    thread_id = uuid4()
    mock_db.get_thread.return_value = {"owner_id": mock_token["user_id"]}
    
    with patch('routes.auth_manager.get_current_user', return_value={"id": mock_token["user_id"]}):
        response = client.post(
            f"/api/agents/{thread_id}/toggle",
            headers={"Authorization": f"Bearer {mock_token['access_token']}"},
            json={
                "agent_role": "doctor",
                "is_active": True
            }
        )
        
        assert response.status_code == 200
        mock_db.update_thread_agent.assert_called_once()

# WebSocket Tests
@pytest.mark.asyncio
async def test_websocket_endpoint(client, mock_db, mock_token):
    thread_id = uuid4()
    user_id = UUID(mock_token["user_id"])
    
    mock_db.is_thread_participant.return_value = True
    
    with client.websocket_connect(
        f"/api/threads/{thread_id}/ws?token={mock_token['access_token']}"
    ) as websocket:
        # Test connection
        data = websocket.receive_json()
        assert data["type"] == "connection_established"
        
        # Test message sending
        websocket.send_json({
            "type": "message",
            "content": "Test message"
        })
        
        # Test message receiving
        data = websocket.receive_json()
        assert data["type"] == "message"
        assert data["content"] == "Test message"

# Error Handling Tests
@pytest.mark.asyncio
async def test_unauthorized_access(client):
    response = client.get(
        "/api/threads/",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_thread_not_found(client, mock_db, mock_token):
    thread_id = uuid4()
    mock_db.get_thread.return_value = None
    
    with patch('routes.auth_manager.get_current_user', return_value={"id": mock_token["user_id"]}):
        response = client.get(
            f"/api/messages/{thread_id}",
            headers={"Authorization": f"Bearer {mock_token['access_token']}"}
        )
        
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_invalid_agent_role(client, mock_db, mock_token):
    thread_id = uuid4()
    
    with patch('routes.auth_manager.get_current_user', return_value={"id": mock_token["user_id"]}):
        response = client.post(
            f"/api/agents/{thread_id}/toggle",
            headers={"Authorization": f"Bearer {mock_token['access_token']}"},
            json={
                "agent_role": "invalid_role",
                "is_active": True
            }
        )
        
        assert response.status_code == 422  # Validation error
