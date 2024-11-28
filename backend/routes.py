from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import json

from database import db_manager
from auth import auth_manager, Token, UserAuth
from agent_system import agent_manager, AgentRole, AgentResponse

# Create routers
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
thread_router = APIRouter(prefix="/api/threads", tags=["threads"])
message_router = APIRouter(prefix="/api/messages", tags=["messages"])
agent_router = APIRouter(prefix="/api/agents", tags=["agents"])

# Auth routes
@auth_router.post("/register", response_model=Token)
async def register_user(user_data: UserAuth, db: AsyncSession = Depends(db_manager.get_session)):
    # Check if user exists
    existing_user = await db.get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Create user
    hashed_password = auth_manager.get_password_hash(user_data.password)
    user = await db.create_user(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )

    # Create access token
    access_token = auth_manager.create_access_token(
        data={"sub": user.username, "user_id": str(user.id)}
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=str(user.id),
        username=user.username
    )

@auth_router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(db_manager.get_session)
):
    user = await auth_manager.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    access_token = auth_manager.create_access_token(
        data={"sub": user.username, "user_id": str(user.id)}
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=str(user.id),
        username=user.username
    )

# Thread routes
@thread_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_thread(
    title: str,
    description: Optional[str] = None,
    agent_roles: Optional[List[AgentRole]] = None,
    db: AsyncSession = Depends(db_manager.get_session),
    current_user = Depends(auth_manager.get_current_user)
):
    thread = await db.create_thread(
        owner_id=current_user.id,
        title=title,
        description=description
    )

    # Add selected agents to thread
    if agent_roles:
        for role in agent_roles:
            await db.add_agent_to_thread(thread.id, role)

    return thread

@thread_router.get("/")
async def get_threads(
    db: AsyncSession = Depends(db_manager.get_session),
    current_user = Depends(auth_manager.get_current_user)
):
    return await db.get_user_threads(current_user.id)

@thread_router.post("/{thread_id}/invite")
async def invite_to_thread(
    thread_id: UUID,
    username: str,
    db: AsyncSession = Depends(db_manager.get_session),
    current_user = Depends(auth_manager.get_current_user)
):
    thread = await db.get_thread(thread_id)
    if thread.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only thread owner can invite participants"
        )

    invited_user = await db.get_user_by_username(username)
    if not invited_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    await db.add_thread_participant(thread_id, invited_user.id)
    return {"message": "User invited successfully"}

# Message routes
@message_router.post("/{thread_id}")
async def send_message(
    thread_id: UUID,
    content: str,
    db: AsyncSession = Depends(db_manager.get_session),
    current_user = Depends(auth_manager.get_current_user)
):
    # Verify thread participation
    if not await db.is_thread_participant(thread_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a thread participant"
        )

    # Create user message
    message = await db.create_message(
        thread_id=thread_id,
        user_id=current_user.id,
        content=content
    )

    # Get thread agents and generate their responses
    thread_agents = await db.get_thread_agents(thread_id)
    thread_context = await db.get_thread_context(thread_id)

    agent_responses = []
    for agent in thread_agents:
        if agent.is_active:
            response = await agent_manager.get_response(
                role=agent.agent_type,
                message=content,
                thread_context=thread_context
            )
            
            agent_message = await db.create_message(
                thread_id=thread_id,
                agent_id=agent.id,
                content=response.content,
                metadata=response.metadata
            )
            agent_responses.append(agent_message)

    return {
        "user_message": message,
        "agent_responses": agent_responses
    }

@message_router.get("/{thread_id}")
async def get_messages(
    thread_id: UUID,
    limit: int = 50,
    before: Optional[datetime] = None,
    db: AsyncSession = Depends(db_manager.get_session),
    current_user = Depends(auth_manager.get_current_user)
):
    if not await db.is_thread_participant(thread_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a thread participant"
        )

    return await db.get_thread_messages(thread_id, limit, before)

# Agent routes
@agent_router.get("/roles")
async def get_available_agents():
    return [role.value for role in AgentRole]

@agent_router.post("/{thread_id}/toggle")
async def toggle_agent(
    thread_id: UUID,
    agent_role: AgentRole,
    is_active: bool,
    db: AsyncSession = Depends(db_manager.get_session),
    current_user = Depends(auth_manager.get_current_user)
):
    thread = await db.get_thread(thread_id)
    if thread.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only thread owner can modify agents"
        )

    await db.update_thread_agent(thread_id, agent_role, is_active)
    return {"message": "Agent status updated successfully"}

# WebSocket connection for real-time updates
@thread_router.websocket("/{thread_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    thread_id: UUID,
    token: str,
    db: AsyncSession = Depends(db_manager.get_session)
):
    try:
        # Verify token and get user
        user = await auth_manager.get_current_user(token, db)
        if not await db.is_thread_participant(thread_id, user.id):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        
        # Add connection to thread's active connections
        await db.add_active_connection(thread_id, user.id, websocket)
        
        try:
            while True:
                data = await websocket.receive_text()
                # Process received data
                # Broadcast updates to other participants
                await db.broadcast_to_thread(thread_id, user.id, data)
        except WebSocketDisconnect:
            # Remove connection from active connections
            await db.remove_active_connection(thread_id, user.id)
    except Exception as e:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
