import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent / "backend"))
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, UserRole
from auth import AuthManager
from .conftest import test_db_session

@pytest.mark.asyncio
async def test_authenticate_user(test_db_session: AsyncSession):
    """Test user authentication with database."""
    async with test_db_session as session:
        auth_manager = AuthManager()
        
        # Create test user
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password",
            role=UserRole.USER
        )
        session.add(user)
        await session.commit()

        # Test valid credentials
        with patch.object(auth_manager, 'verify_password', return_value=True):
            authenticated_user = await auth_manager.authenticate_user(
                session,
                user.username,
                "correct_password"
            )
            assert authenticated_user is not None
            assert authenticated_user.username == user.username

        # Test invalid credentials
        with patch.object(auth_manager, 'verify_password', return_value=False):
            non_authenticated_user = await auth_manager.authenticate_user(
                session,
                user.username,
                "wrong_password"
            )
            assert non_authenticated_user is None

@pytest.mark.asyncio
async def test_register_user(test_db_session: AsyncSession):
    """Test user registration."""
    async with test_db_session as session:
        auth_manager = AuthManager()
        
        # Create user
        hashed_password = auth_manager.get_password_hash("password123")
        user = User(
            username="newuser",
            email="new@example.com",
            hashed_password=hashed_password,
            role=UserRole.USER
        )
        
        session.add(user)
        await session.commit()
        
        # Verify user was created
        result = await session.get(User, user.id)
        assert result is not None
        assert result.username == "newuser"
        assert result.email == "new@example.com"
