import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, UTC
from jose import jwt

from agent_system import AgentSystem, AgentRole, AGENTS
from auth import AuthManager, JWT_SECRET_KEY, JWT_ALGORITHM

@pytest.fixture
def auth_manager():
    return AuthManager()

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
