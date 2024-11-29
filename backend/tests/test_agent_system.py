# tests/test_agent_system.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, UTC, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from jose import jwt

from agent_system import AgentSystem, AgentRole, AgentResponse, AGENTS
from auth import AuthManager, JWT_SECRET_KEY, JWT_ALGORITHM
from models import User, UserRole
from .conftest import test_engine, test_db_session

@pytest.fixture
def auth_manager():
    return AuthManager()

@pytest.fixture
async def test_user(test_db_session):
    async for session in test_db_session:
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password",
            role=UserRole.USER
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async for session in test_db_session:  # Get session from generator
        # Create user
        hashed_password = auth_manager.get_password_hash(user_data["password"])
        user = User(
            username=user_data["username"],
            email=user_data["email"],
            hashed_password=hashed_password,
            role=UserRole.USER
        )
        
        session.add(user)  # Use the session from generator
        await session.commit()
        
        # Verify user was created
        result = await session.get(User, user.id)
        assert result is not None
        assert result.username == user_data["username"]
        assert result.email == user_data["email"]

@pytest.mark.asyncio
async def test_create_access_token(auth_manager):
    """Test JWT token creation"""
    data = {"sub": "testuser"}
    token = auth_manager.create_access_token(data)
    
    # Verify token
    decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    assert decoded["sub"] == "testuser"
    assert "exp" in decoded

    # Ensure expiration is in the future
    exp = datetime.fromtimestamp(decoded["exp"], UTC)
    assert exp > datetime.now(UTC)

@pytest.mark.asyncio
async def test_agent_roles_enum():
    assert AgentRole.DOCTOR.value == "doctor"
    assert AgentRole.LAWYER.value == "lawyer"
    assert AgentRole.ACCOUNTANT.value == "accountant"
    assert AgentRole.ETHICIST.value == "ethicist"

@pytest.mark.asyncio
async def test_transfer_to_valid_agent():
    system = AgentSystem()
    agent = system.transfer_to("doctor")
    assert agent.name == "doctor"
    assert agent.instructions.startswith("As a medical professional")

@pytest.mark.asyncio
async def test_transfer_to_invalid_agent():
    system = AgentSystem()
    agent = system.transfer_to("invalid_agent")
    assert agent is None

@pytest.mark.asyncio
async def test_agent_response():
    mock_agent = Mock()
    mock_agent.name = "doctor"
    with patch.dict(AGENTS, {"doctor": mock_agent}):
        system = AgentSystem()
        agent = system.transfer_to("doctor")
        assert agent == mock_agent
