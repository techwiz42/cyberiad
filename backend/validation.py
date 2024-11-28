from pydantic import BaseModel, Field, EmailStr, constr, validator
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID
from enum import Enum

class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50)
    email: EmailStr
    password: constr(min_length=8)

    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v

class ThreadCreate(BaseModel):
    title: constr(min_length=1, max_length=200)
    description: Optional[str] = None
    agent_roles: Optional[List[str]] = []

class MessageCreate(BaseModel):
    content: constr(min_length=1, max_length=10000)
    metadata: Optional[Dict] = Field(default_factory=dict)

class ThreadParticipantAdd(BaseModel):
    username: str

class AgentUpdate(BaseModel):
    is_active: bool

class ThreadResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    owner_id: UUID
    created_at: datetime
    updated_at: datetime
    participants: List[Dict]
    agents: List[Dict]

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: UUID
    thread_id: UUID
    user_id: Optional[UUID]
    agent_id: Optional[UUID]
    content: str
    metadata: Dict
    created_at: datetime

    class Config:
        from_attributes = True

class WebSocketMessage(BaseModel):
    type: str
    content: Dict

    @validator('type')
    def validate_message_type(cls, v):
        allowed_types = {'message', 'typing', 'read', 'join', 'leave'}
        if v not in allowed_types:
            raise ValueError(f'Message type must be one of {allowed_types}')
        return 
