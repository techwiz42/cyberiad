# tests/test_auth.py
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
from unittest.mock import patch
from fastapi import HTTPException
from jose import jwt, JWTError
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent / "backend"))
sys.path.append(str(Path(__file__).resolve().parent.parent))
from models import User, UserRole
from .conftest import test_db_session
from auth import (
    AuthManager, 
    JWT_SECRET_KEY, 
    JWT_ALGORITHM,
    Token,
    UserAuth,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

@pytest.fixture
def auth_manager():
    return AuthManager()
'''
@pytest.fixture
async def test_user(test_db_session):
    for session in test_db_session:
        # Create a test user with known credentials
        auth_mgr = AuthManager()
        hashed_password = auth_mgr.get_password_hash("testpassword123")
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "hashed_password": hashed_password
        }
    
        # Use your database manager to create user
        # This will depend on your actual User model and database structure
        result = await session.execute(
            "INSERT INTO users (username, email, hashed_password) "
            "VALUES (:username, :email, :hashed_password) RETURNING id, username, email",
            user_data
        )
        user = result.fetchone()
        await session.commit()
        return user
'''

@pytest.fixture
async def test_user(test_db_session):
    async for session in test_db_session:
        auth_mgr = AuthManager()
        hashed_password = auth_mgr.get_password_hash("testpassword123")
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "hashed_password": hashed_password,
        }

        # Wrap the SQL query with text()
        result = await session.execute(
            text(
                """
                INSERT INTO users (username, email, hashed_password)
                VALUES (:username, :email, :hashed_password)
                RETURNING id, username, email
                """
            ),
            user_data,
        )
        user = result.fetchone()
        await session.commit()
        yield user


def test_password_hashing(auth_manager):
    password = "mysecretpassword"
    hashed = auth_manager.get_password_hash(password)
    
    # Test that hash is different from original password
    assert hashed != password
    
    # Test that we can verify the password
    assert auth_manager.verify_password(password, hashed) is True
    
    # Test that wrong password fails verification
    assert auth_manager.verify_password("wrongpassword", hashed) is False
    
    # Test that password hash is different each time
    hashed2 = auth_manager.get_password_hash(password)
    assert hashed != hashed2

def test_create_access_token(auth_manager):
    data = {"sub": "testuser", "additional": "data"}
    token = auth_manager.create_access_token(data)
    
    # Decode and verify the token
    decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    
    # Check token contents
    assert decoded["sub"] == "testuser"
    assert decoded["additional"] == "data"
    assert "exp" in decoded
    
    # Check expiration time
    exp_delta = datetime.fromtimestamp(decoded["exp"]) - datetime.utcnow()
    assert timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES - 1) < exp_delta < timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

def test_create_expired_token(auth_manager):
    data = {"sub": "testuser"}
    token = auth_manager.create_access_token(data)
    
    # Modify the decoded token to set an expired time
    decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    decoded["exp"] = datetime.utcnow() - timedelta(minutes=1)
    expired_token = jwt.encode(decoded, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    # Attempt to decode expired token
    with pytest.raises(JWTError):
        jwt.decode(expired_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

@pytest.mark.asyncio
async def test_authenticate_user(test_db_session: AsyncSession):
    """Test user authentication with database."""
    async for session in test_db_session:
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
async def test_get_current_user_valid_token(auth_manager, test_db_session, test_user):
    # Consume the yielded user from the test_user fixture
    async for user in test_user:
        # Create a valid token for the user
        token = auth_manager.create_access_token({"sub": user.username})

        # Retrieve the current user with the token
        async for session in test_db_session:
            current_user = await auth_manager.get_current_user(token, session)

        # Validate the retrieved user
        assert current_user is not None
        assert current_user.username == user.username

'''
@pytest.mark.asyncio
async def test_get_current_user_invalid_token(auth_manager, test_db_session):
    with pytest.raises(HTTPException) as exc_info:
        await auth_manager.get_current_user("invalid_token", test_db_session)
    assert exc_info.value.status_code == 401
    assert "Invalid authentication credentials" in exc_info.value.detail

@pytest.mark.asyncio
async def test_get_current_user_expired_token(auth_manager, test_db_session, test_user):
    # Create a token that's already expired
    data = {"sub": test_user.username, "exp": datetime.utcnow() - timedelta(minutes=1)}
    expired_token = jwt.encode(data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    with pytest.raises(HTTPException) as exc_info:
        await auth_manager.get_current_user(expired_token, test_db_session)
    assert exc_info.value.status_code == 401

def test_token_model():
    token_data = {
        "access_token": "some_token",
        "token_type": "bearer",
        "user_id": "123",
        "username": "testuser"
    }
    token = Token(**token_data)
    assert token.access_token == "some_token"
    assert token.token_type == "bearer"
    assert token.user_id == "123"
    assert token.username == "testuser"

def test_user_auth_model():
    user_data = {
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123"
    }
    user_auth = UserAuth(**user_data)
    assert user_auth.username == "newuser"
    assert user_auth.email == "new@example.com"
    assert user_auth.password == "password123"

@pytest.mark.asyncio
async def test_oauth2_password_bearer():
    # This would test the OAuth2PasswordBearer scheme
    from fastapi.security import OAuth2PasswordBearer
    
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
    assert oauth2_scheme.tokenUrl == "token"
    assert oauth2_scheme.scheme_name == "OAuth2PasswordBearer"

@pytest.mark.asyncio
async def test_password_hashing_performance(auth_manager):
    # Test that password hashing takes a reasonable amount of time
    # Too fast might indicate weak hashing, too slow would be unusable
    import time
    
    start_time = time.time()
    hash = auth_manager.get_password_hash("test_password")
    end_time = time.time()
    
    hashing_time = end_time - start_time
    assert 0.01 < hashing_time < 0.5  # Should take between 10ms and 500ms
'''
