# tests/test_security.py
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent / "backend"))
sys.path.append(str(Path(__file__).resolve().parent.parent))
import json
import pytest
from fastapi import Request, HTTPException
from datetime import datetime, timedelta
import jwt
from unittest.mock import Mock
import asyncio

from security_manager import (
    SecurityManager, 
    RateLimitExceeded, 
    JWTBearer,
    rate_limit,
    security_manager
)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

class MockRequest:
    def __init__(self, client_host="127.0.0.1", path="/test"):
        self.client = Mock()
        self.client.host = client_host
        self.url = Mock()
        self.url.path = path

@pytest.fixture
def security_mgr():
    return SecurityManager()

@pytest.fixture
def mock_request():
    return MockRequest()

@pytest.mark.asyncio
async def test_rate_limit_basic(security_mgr, mock_request):
    # First request should succeed
    await security_mgr.check_rate_limit(mock_request, "10/minute", 60)
    
    # Immediate second request should fail
    with pytest.raises(RateLimitExceeded):
        await security_mgr.check_rate_limit(mock_request, "10/minute", 60)

@pytest.mark.asyncio
async def test_rate_limit_different_paths(security_mgr):
    req1 = MockRequest(path="/path1")
    req2 = MockRequest(path="/path2")
    
    # Both should succeed as they're different paths
    await security_mgr.check_rate_limit(req1, "10/minute", 60)
    await security_mgr.check_rate_limit(req2, "10/minute", 60)

@pytest.mark.asyncio
async def test_rate_limit_expiration(security_mgr, mock_request):
    await security_mgr.check_rate_limit(mock_request, "10/minute", 1)
    
    # Wait for rate limit to expire
    await asyncio.sleep(1.1)
    
    # Should succeed after expiration
    await security_mgr.check_rate_limit(mock_request, "10/minute", 1)

@pytest.mark.asyncio
async def test_blocked_ip_basic(security_mgr, mock_request):
    # Record failed attempts to trigger blocking
    for _ in range(5):
        await security_mgr.record_failed_attempt(mock_request)
    
    # Verify IP is blocked
    with pytest.raises(HTTPException) as exc:
        await security_mgr.check_blocked_ip(mock_request)
    assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_blocked_ip_expiration(security_mgr, mock_request):
    # Block IP with very short duration for testing
    security_mgr.blocked_ips[mock_request.client.host] = datetime.utcnow() + timedelta(seconds=1)
    
    # Verify initially blocked
    with pytest.raises(HTTPException):
        await security_mgr.check_blocked_ip(mock_request)
    
    # Wait for block to expire
    await asyncio.sleep(1.1)
    
    # Should succeed after expiration
    await security_mgr.check_blocked_ip(mock_request)

@pytest.mark.asyncio
async def test_failed_attempts_tracking(security_mgr, mock_request):
    # Record multiple failed attempts
    for i in range(4):
        await security_mgr.record_failed_attempt(mock_request)
        assert security_mgr.failed_attempts[mock_request.client.host] == i + 1
    
    # Next attempt should trigger blocking
    await security_mgr.record_failed_attempt(mock_request)
    assert mock_request.client.host in security_mgr.blocked_ips
    assert mock_request.client.host not in security_mgr.failed_attempts

@pytest.mark.asyncio
async def test_jwt_bearer():
    # Create a valid JWT tokeni
    print(f"JWT_SECRET_KEY={JWT_SECRET_KEY}")
    payload = {
        "sub": "user_id",
        "exp": int((datetime.utcnow() + timedelta(minutes=1)).timestamp())  # UNIX timestamp
    }
    token = jwt.encode(payload, JWT_SECRET_KEY , algorithm=JWT_ALGORITHM)

    jwt_bearer = JWTBearer()

    # Mock a FastAPI request with the Authorization header
    mock_request = Mock()
    mock_request.headers = {"Authorization": f"Bearer {token}"}

    # Ensure the bearer logic unpacks and validates the token correctly
    result = await jwt_bearer(mock_request)
    assert result["sub"] == payload["sub"] 

@pytest.mark.asyncio
async def test_jwt_bearer_invalid_scheme():
    # Create a token but simulate an invalid scheme (e.g., "Token" instead of "Bearer")
    payload = {"sub": "user_id", "exp": datetime.utcnow() + timedelta(minutes=1)}
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    jwt_bearer = JWTBearer()

    # Mock a FastAPI request with an invalid Authorization scheme
    mock_request = Mock()
    mock_request.headers = {"Authorization": f"Token {token}"}

    # It should raise an HTTPException for an invalid scheme
    with pytest.raises(HTTPException) as exc_info:
        await jwt_bearer(mock_request)
    assert exc_info.value.status_code == 403
    assert "Invalid authentication scheme" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_jwt_bearer_expired_token():
    # Create an expired token
    payload = {"sub": "user_id", "exp": datetime.utcnow() - timedelta(minutes=1)}
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    jwt_bearer = JWTBearer()

    # Mock a FastAPI request with an expired token
    mock_request = Mock()
    mock_request.headers = {"Authorization": f"Bearer {token}"}

    # It should raise an HTTPException for expired tokens
    with pytest.raises(HTTPException) as exc_info:
        await jwt_bearer(mock_request)
    assert exc_info.value.status_code == 401
    assert "Token has expired" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_rate_limit_decorator():
    @rate_limit(limit="2/minute", duration=60)
    async def test_endpoint(request: Request):
        return {"message": "success"}
    
    mock_request = MockRequest()
    
    # First two calls should succeed
    result1 = await test_endpoint(mock_request)
    assert result1["message"] == "success"
    
    result2 = await test_endpoint(mock_request)
    assert result2["message"] == "success"
    
    # Third call should fail
    with pytest.raises(RateLimitExceeded):
        await test_endpoint(mock_request)

@pytest.mark.asyncio
async def test_concurrent_requests(security_mgr):
    mock_requests = [MockRequest(client_host=f"192.168.1.{i}") for i in range(10)]
    
    # Test concurrent rate limit checks
    tasks = [
        security_mgr.check_rate_limit(req, "10/minute", 60)
        for req in mock_requests
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # All should succeed as they're from different IPs
    assert all(not isinstance(r, Exception) for r in results)

@pytest.mark.asyncio
async def test_cleanup(security_mgr):
    # Add some expired data
    old_time = datetime.utcnow() - timedelta(hours=1)
    security_mgr.api_key_cache["test"] = old_time
    security_mgr.blocked_ips["192.168.1.1"] = old_time
    
    # Run cleanup (assuming there's a cleanup method)
    await security_mgr.cleanup()
    
    # Verify expired data is removed
    assert "test" not in security_mgr.api_key_cache
    assert "192.168.1.1" not in security_mgr.blocked_ips

@pytest.mark.asyncio
async def test_rate_limit_burst(security_mgr, mock_request):
    # Test burst handling
    for _ in range(5):
        await security_mgr.check_rate_limit(request=mock_request, limit="5/second", duration=1)
        
    with pytest.raises(RateLimitExceeded):
        await security_mgr.check_rate_limit(request=mock_request, limit="5/second", duration=1)

@pytest.mark.asyncio
async def test_blocked_ip_multiple_attempts(security_mgr, mock_request):
    # Block IP
    await security_mgr.record_failed_attempt(mock_request)
    await security_mgr.record_failed_attempt(mock_request)
    await security_mgr.record_failed_attempt(mock_request)
    await security_mgr.record_failed_attempt(mock_request)
    await security_mgr.record_failed_attempt(mock_request)
    
    # Verify multiple checks while blocked
    for _ in range(3):
        with pytest.raises(HTTPException) as exc:
            await security_mgr.check_blocked_ip(mock_request)
        assert exc.value.status_code == 403
