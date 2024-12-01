# These are all the imports needed
import os
import pytest
from fastapi import HTTPException
from unittest.mock import Mock
import asyncio
from datetime import datetime, timedelta, UTC  # Make sure UTC is explicitly imported
import jwt
from security_manager import SecurityManager, RateLimitExceeded, JWTBearer

# Import JWT config from security_manager
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")  # Fallback for testing
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")  # Fallback for testing

class MockRequest:
    def __init__(self, client_host="127.0.0.1", path="/test"):
        self.client = Mock()
        self.client.host = client_host
        self.url = Mock()
        self.url.path = path

@pytest.mark.asyncio
async def test_jwt_bearer_invalid_scheme():
    # Create a token but use an invalid scheme
    payload = {
        "sub": "user_id",
        "exp": int((datetime.now(UTC) + timedelta(minutes=1)).timestamp())
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    jwt_bearer = JWTBearer()

    # Mock a FastAPI request with an invalid Authorization scheme
    mock_request = Mock()
    mock_request.headers = {"Authorization": f"Token {token}"}  # Using "Token" instead of "Bearer"

    # Should raise HTTPException with correct error message
    with pytest.raises(HTTPException) as exc_info:
        await jwt_bearer(mock_request)
    assert exc_info.value.status_code == 403
    assert "Invalid authentication scheme" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_rate_limit_burst():
    security_mgr = SecurityManager()
    mock_request = MockRequest()
    cache_key = f"{mock_request.client.host}:{mock_request.url.path}"
    
    # First 5 requests should succeed
    for _ in range(5):
        try:
            if cache_key in security_mgr.api_key_cache:
                last_request_time = security_mgr.api_key_cache[cache_key]
                current_time = datetime.now(UTC)
                if (current_time - last_request_time).total_seconds() < 1:
                    await asyncio.sleep(1.1)  # Wait for the rate limit to reset
                    
            await security_mgr.check_rate_limit(mock_request, "5/second", 1)
            await asyncio.sleep(0.1)  # Small delay between requests
        except RateLimitExceeded:
            pytest.fail("Should not raise RateLimitExceeded for first 5 requests")
    
    # The 6th request should fail with RateLimitExceeded
    with pytest.raises(RateLimitExceeded) as exc_info:
        await security_mgr.check_rate_limit(mock_request, "5/second", 1)
    
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in str(exc_info.value.detail)
