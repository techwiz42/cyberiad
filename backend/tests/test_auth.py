
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "backend"))
sys.path.append(str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import pytest

from server import app

client = TestClient(app)

mock_db_manager = AsyncMock()
mock_auth_manager = AsyncMock()

@pytest.mark.asyncio
@patch("database.db_manager.get_user_by_username", new_callable=AsyncMock)
@patch("database.db_manager.create_user", new_callable=AsyncMock)
@patch("auth.auth_manager.create_access_token", new_callable=AsyncMock)
async def test_register_user_new_user(mock_get_user_by_username, mock_create_user, mock_create_access_token):
    # Mock behavior
    mock_get_user_by_username.return_value = None
    mock_create_user.return_value = {
        "username": "test_user",
        "email": "test_user@example.com",
        "hashed_password": "hashed_password"
    }
    mock_create_access_token.return_value = "mocked_token"

    # Test payload
    payload = {
        "username": "test_user",
        "password": "secure_password",
        "email": "test_user@example.com"
    }

    # Send request
    response = client.post("/api/auth/register", json=payload)

    # Assertions
    assert response.status_code == 200
    assert response.json() == {"access_token": "mocked_token", "token_type": "bearer"}

@pytest.mark.asyncio
@patch("database.db_manager.get_user_by_username", new_callable=AsyncMock)
@patch("database.db_manager.create_user", new_callable=AsyncMock)
async def test_register_user_creation_failure(mock_get_user_by_username, mock_create_user):
    # Mock behavior
    mock_get_user_by_username.return_value = None  # Simulate user does not exist
    mock_create_user.side_effect = Exception("Database error")  # Simulate failure

    # Test payload
    payload = {
        "username": "test_user",
        "password": "secure_password",
        "email": "test_user@example.com"
    }

    # Send request
    response = client.post("/api/auth/register", json=payload)

    # Assertions
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}

@pytest.mark.asyncio
@patch("database.db_manager", mock_db_manager)
async def test_register_user_existing_user():
    mock_db_manager.get_user_by_username.return_value = {"username": "existing_user"}

    payload = {
        "username": "existing_user",
        "password": "secure_password",
        "email": "existing_user@example.com"
    }
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 400
    assert response.json() == {"detail": "User already exists"}


@pytest.mark.asyncio
async def test_register_user_invalid_input():
    payload = {"username": "", "password": "", "email": ""}
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 422  # Validation error

