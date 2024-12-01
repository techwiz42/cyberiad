from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta, UTC
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import Optional, Dict, List
import jwt
import logging
import os

logger = logging.getLogger(__name__)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

class RateLimitExceeded(HTTPException):
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=429, detail=detail)

class SecurityManager:
    def __init__(self):
        self.api_key_cache: Dict[str, List[datetime]] = {}  # Changed to store list of timestamps
        self.failed_attempts: Dict[str, int] = {}
        self.blocked_ips: Dict[str, datetime] = {}

    async def cleanup(self):
        """Remove expired entries from caches."""
        current_time = datetime.now(UTC)
        
        # Clean api_key_cache - remove old timestamps
        for key in list(self.api_key_cache.keys()):
            self.api_key_cache[key] = [
                ts for ts in self.api_key_cache[key]
                if (current_time - ts).total_seconds() < 3600
            ]
            if not self.api_key_cache[key]:
                del self.api_key_cache[key]
        
        # Clean blocked_ips
        self.blocked_ips = {
            k: v for k, v in self.blocked_ips.items()
            if v > current_time
        }

    async def check_rate_limit(self, request: Request, limit: str, duration: int):
        """
        Check rate limit for request.
        
        Args:
            request: FastAPI Request object
            limit: String in format "X/timeunit" (e.g. "5/second")
            duration: Time window in seconds
        """
        client_ip = request.client.host
        cache_key = f"{client_ip}:{request.url.path}"
        current_time = datetime.now(UTC)
        max_requests = int(limit.split('/')[0])

        # Initialize timestamps list if not exists
        if cache_key not in self.api_key_cache:
            self.api_key_cache[cache_key] = []
        
        # Clean old timestamps
        self.api_key_cache[cache_key] = [
            ts for ts in self.api_key_cache[cache_key]
            if (current_time - ts).total_seconds() < duration
        ]
        
        # Check if limit exceeded
        if len(self.api_key_cache[cache_key]) >= max_requests:
            raise RateLimitExceeded()
        
        # Record this request
        self.api_key_cache[cache_key].append(current_time)

    async def check_blocked_ip(self, request: Request):
        """Check if IP is blocked."""
        client_ip = request.client.host
        current_time = datetime.now(UTC)
        if client_ip in self.blocked_ips:
            if current_time < self.blocked_ips[client_ip]:
                raise HTTPException(
                    status_code=403,
                    detail="IP address is blocked"
                )
            else:
                del self.blocked_ips[client_ip]

    async def record_failed_attempt(self, request: Request):
        """Record failed authentication attempt."""
        client_ip = request.client.host
        self.failed_attempts[client_ip] = self.failed_attempts.get(client_ip, 0) + 1
        
        if self.failed_attempts[client_ip] >= 5:
            self.blocked_ips[client_ip] = datetime.now(UTC) + timedelta(minutes=15)
            del self.failed_attempts[client_ip]

class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            raise HTTPException(
                status_code=403,
                detail="Invalid authentication credentials"
            )

        scheme, _, token = auth_header.partition(" ")
        if not scheme or scheme.lower() != "bearer":
            raise HTTPException(
                status_code=403,
                detail="Invalid authentication scheme"
            )

        if not token:
            raise HTTPException(
                status_code=403,
                detail="Invalid authentication credentials"
            )
            
        try:
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired"
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=403,
                detail="Invalid token"
            )
            
        return payload

# Rate limit decorators
def rate_limit(limit: str, duration: int):
    """Rate limit decorator."""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            await security_manager.check_rate_limit(request, limit, duration)
            return await func(request=request, *args, **kwargs)
        return wrapper
    return decorator

# Create security manager instance
security_manager = SecurityManager()
