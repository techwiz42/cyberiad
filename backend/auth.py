from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from pydantic import BaseModel
import os

# Models
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str

class UserAuth(BaseModel):
    username: str
    email: str
    password: str

# Constants
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class AuthManager:
    def __init__(self):
        self.pwd_context = pwd_context
        
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)
        
    def get_password_hash(self, password: str) -> str:
        return self.pwd_context.hash(password)
        
    def create_access_token(self, data: Dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
    async def authenticate_user(self, db: AsyncSession, username: str, password: str):
        user = await db.get_user_by_username(username)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user
        
    async def get_current_user(self, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(lambda: None)):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            username = payload.get("sub")
            if username is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
            
        user = await db.get_user_by_username(username)
        if user is None:
            raise credentials_exception
        return user

# Create auth manager instance
auth_manager = AuthManager()