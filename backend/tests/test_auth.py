# tests/test_auth.py
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from fastapi.security import OAuth2PasswordBearer
import time
from pydantic import ValidationError 
from unittest.mock import patch
from fastapi import HTTPException
from jose import jwt, JWTError
import sys
from pathlib import Path
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

@pytest.fixture
async def test_user(test_db_session):
    async with test_db_session as session:
        auth_mgr = AuthManager()
        hashed_password = auth_mgr.get_password_hash("testpassword123")
        
        # Use a random username to avoid conflicts
        unique_username = f"testuser_{uuid.uuid4().hex[:8]}"
        
        # Use ORM instead of raw SQL
        user = User(
            username=unique_username,
            email=f"{unique_username}@example.com",
            hashed_password=hashed_password,
            role=UserRole.USER
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

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
async def test_get_current_user_valid_token(auth_manager, test_db_session, test_user):
    """Test that a valid token correctly returns the associated user."""
    user = await test_user  # Await the coroutine instead of iterating
    
    # Create a valid token for the user
    token = auth_manager.create_access_token({"sub": user.username})

    # Retrieve the current user with the token
    async with test_db_session as session:
        current_user = await auth_manager.get_current_user(token, session)
        
        # Validate the retrieved user
        assert current_user is not None
        assert current_user.username == user.username
       
@pytest.mark.asyncio
async def test_get_current_user_invalid_token(auth_manager, test_db_session):
    """Test that an invalid token is properly rejected."""
    async with test_db_session as session:
        with pytest.raises(HTTPException) as exc_info:
            await auth_manager.get_current_user("invalid_token", session)
        assert exc_info.value.status_code == 401
        assert "Invalid authentication credentials" in exc_info.value.detail

@pytest.mark.asyncio
async def test_get_current_user_expired_token(auth_manager, test_db_session, test_user):
    """Test that an expired token is properly rejected."""
    # First get the test user
    user = await test_user
    
    # Create a token that's already expired
    data = {
        "sub": user.username, 
        "exp": datetime.utcnow() - timedelta(minutes=1)
    }
    expired_token = jwt.encode(data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    async with test_db_session as session:
        with pytest.raises(HTTPException) as exc_info:
            await auth_manager.get_current_user(expired_token, session)
        assert exc_info.value.status_code == 401
        assert "Invalid authentication credentials" in exc_info.value.detail
    

def test_token_model():
    """Test Token model creation and validation."""
    token_data = {
        "access_token": "some_token",
        "token_type": "bearer",
        "user_id": str(uuid.uuid4()),  # Use proper UUID string
        "username": "testuser"
    }
    token = Token(**token_data)
    
    # Test all fields
    assert token.access_token == token_data["access_token"]
    assert token.token_type == token_data["token_type"]
    assert token.user_id == token_data["user_id"]
    assert token.username == token_data["username"]
    
    # Test model conversion to dict
    token_dict = token.model_dump()
    assert all(token_dict[k] == v for k, v in token_data.items())

def test_token_model_validation():
    """Test Token model validation rules."""
    # Test required fields
    with pytest.raises(ValueError):
        Token()  # Should fail without required fields
    
    # Test invalid token type
    with pytest.raises(ValueError):
        Token(
            access_token="token",
            token_type="invalid",
            user_id=str(uuid.uuid4()),
            username="testuser"
        )

def test_user_auth_model():
    """Test UserAuth model creation and validation."""
    user_data = {
        "username": "newuser",
        "email": "new@example.com",
        "password": "password123"
    }
    user_auth = UserAuth(**user_data)
    
    # Test all fields
    assert user_auth.username == user_data["username"]
    assert user_auth.email == user_data["email"]
    assert user_auth.password == user_data["password"]
    
    # Test model conversion to dict
    user_dict = user_auth.model_dump()
    assert all(user_dict[k] == v for k, v in user_data.items())

def test_user_auth_model_validation():
    """Test UserAuth model validation rules."""
    # Test required fields
    with pytest.raises(ValueError):
        UserAuth()  # Should fail without required fields
    
    # Test invalid email
    with pytest.raises(ValueError):
        UserAuth(
            username="testuser",
            email="invalid-email",
            password="password123"
        )
    
    # Test username length
    with pytest.raises(ValueError):
        UserAuth(
            username="a",  # Too short
            email="test@example.com",
            password="password123"
        )

@pytest.mark.asyncio
async def test_password_hashing_performance(auth_manager):
    """Test that password hashing has appropriate performance characteristics.
    
    The test ensures that:
    - Hashing is not too fast (which could indicate weak security)
    - Hashing is not too slow (which would affect usability)
    - Hashing is consistent across multiple runs
    """
    password = "test_password"
    NUM_SAMPLES = 3
    MIN_TIME = 0.05  # 50ms minimum
    MAX_TIME = 0.5   # 500ms maximum
    
    # Test multiple samples to ensure consistent performance
    times = []
    hashes = []
    
    for _ in range(NUM_SAMPLES):
        start_time = time.perf_counter()  # More precise than time.time()
        hash_result = auth_manager.get_password_hash(password)
        end_time = time.perf_counter()
        
        hashing_time = end_time - start_time
        times.append(hashing_time)
        hashes.append(hash_result)
    
    avg_time = sum(times) / len(times)
    
    # Test performance bounds
    assert MIN_TIME < avg_time < MAX_TIME, \
        f"Hashing time ({avg_time:.3f}s) outside acceptable range ({MIN_TIME}-{MAX_TIME}s)"
    
    # Verify that each hash is different (due to random salt)
    assert len(set(hashes)) == NUM_SAMPLES, \
        "Multiple hashes of same password should be unique due to salt"
    
    # Verify that each hash can be verified
    for hash_value in hashes:
        assert auth_manager.verify_password(password, hash_value), \
            "Hash verification failed"

def test_oauth2_password_bearer():
    """Test OAuth2PasswordBearer configuration."""
    from fastapi.security import OAuth2PasswordBearer

    # Just verify that we can create the scheme
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
    assert isinstance(oauth2_scheme, OAuth2PasswordBearer)

