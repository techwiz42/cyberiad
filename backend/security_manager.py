from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import Optional, Dict
import time
import jwt
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Rate limiting setup
limiter = Limiter(key_func=get_remote_address)

class RateLimitExceeded(HTTPException):
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=429, detail=detail)

class SecurityManager:
    def __init__(self):
        self.api_key_cache: Dict[str, datetime] = {}
        self.failed_attempts: Dict[str, int] = {}
        self.blocked_ips: Dict[str, datetime] = {}

    async def check_rate_limit(self, request: Request, limit: str, duration: int):
        """Check rate limit for request."""
        client_ip = request.client.host
        cache_key = f"{client_ip}:{request.url.path}"
        
        current_time = datetime.utcnow()
        if cache_key in self.api_key_cache:
            time_diff = (current_time - self.api_key_cache[cache_key]).total_seconds()
            if time_diff < duration:
                raise RateLimitExceeded()
        
        self.api_key_cache[cache_key] = current_time

    async def check_blocked_ip(self, request: Request):
        """Check if IP is blocked."""
        client_ip = request.client.host
        if client_ip in self.blocked_ips:
            if datetime.utcnow() < self.blocked_ips[client_ip]:
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
            self.blocked_ips[client_ip] = datetime.utcnow() + timedelta(minutes=15)
            del self.failed_attempts[client_ip]

class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)
        
        if not credentials:
            raise HTTPException(
                status_code=403,
                detail="Invalid authorization code."
            )
            
        if not credentials.scheme == "Bearer":
            raise HTTPException(
                status_code=403,
                detail="Invalid authentication scheme."
            )
            
        try:
            payload = jwt.decode(
                credentials.credentials,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=403,
                detail="Token has expired."
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=403,
                detail="Invalid token."
            )
            
        return payload

# Rate limit decorators
def rate_limit(limit: str, duration: int):
    """Rate limit decorator."""
    def decorator(func):
        async def wrapper(*args, request: Request, **kwargs):
            await security_manager.check_rate_limit(request, limit, duration)
            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator

# Create security manager instance
security_manager = SecurityManager()
