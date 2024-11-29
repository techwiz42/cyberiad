# tests/test_models.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import uuid
from datetime import datetime, timedelta
from models import (
    Base, User, Thread, ThreadParticipant, ThreadAgent, Message,
    UserRole, AgentType, ThreadStatus
)

# Create test database engine
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/cyberiad_test"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def session(test_engine):
    async_session = sessionmaker(
        test_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def test_user(session):
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password_here",
        role=UserRole.USER
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

@pytest.fixture
async def test_thread(session, test_user):
    thread = Thread(
        title="Test Thread",
        description="Test Description",
        owner_id=test_user.id,
        status=ThreadStatus.ACTIVE
    )
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    return thread

@pytest.mark.asyncio
async def test_user_creation(session):
    user = User(
        username="newuser",
        email="new@example.com",
        hashed_password="hashed",
        role=UserRole.USER
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    assert isinstance(user.id, uuid.UUID)
    assert user.username == "newuser"
    assert user.email == "new@example.com"
    assert user.role == UserRole.USER
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)

@pytest.mark.asyncio
async def test_thread_creation(session, test_user):
    thread = Thread(
        title="Test Thread",
        description="Test Description",
        owner_id=test_user.id
    )
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    
    assert isinstance(thread.id, uuid.UUID)
    assert thread.title == "Test Thread"
    assert thread.description == "Test Description"
    assert thread.owner_id == test_user.id
    assert thread.status == ThreadStatus.ACTIVE
    assert isinstance(thread.created_at, datetime)
    assert isinstance(thread.updated_at, datetime)

@pytest.mark.asyncio
async def test_thread_participant(session, test_user, test_thread):
    participant = ThreadParticipant(
        thread_id=test_thread.id,
        user_id=test_user.id
    )
    session.add(participant)
    await session.commit()
    await session.refresh(participant)
    
    assert participant.thread_id == test_thread.id
    assert participant.user_id == test_user.id
    assert participant.is_active is True
    assert isinstance(participant.joined_at, datetime)

@pytest.mark.asyncio
async def test_thread_agent(session, test_thread):
    agent = ThreadAgent(
        thread_id=test_thread.id,
        agent_type=AgentType.LAWYER,
        settings={"response_style": "formal"}
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    
    assert isinstance(agent.id, uuid.UUID)
    assert agent.thread_id == test_thread.id
    assert agent.agent_type == AgentType.LAWYER
    assert agent.is_active is True
    assert agent.settings == {"response_style": "formal"}
    assert isinstance(agent.created_at, datetime)

@pytest.mark.asyncio
async def test_message(session, test_thread, test_user):
    message = Message(
        thread_id=test_thread.id,
        user_id=test_user.id,
        content="Test message content",
        message_metadata={"importance": "high"}
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    
    assert isinstance(message.id, uuid.UUID)
    assert message.thread_id == test_thread.id
    assert message.user_id == test_user.id
    assert message.content == "Test message content"
    assert message.message_metadata == {"importance": "high"}
    assert isinstance(message.created_at, datetime)

@pytest.mark.asyncio
async def test_relationships(session, test_user, test_thread):
    # Create thread participant
    participant = ThreadParticipant(
        thread_id=test_thread.id,
        user_id=test_user.id
    )
    session.add(participant)
    
    # Create message
    message = Message(
        thread_id=test_thread.id,
        user_id=test_user.id,
        content="Test message"
    )
    session.add(message)
    
    await session.commit()
    await session.refresh(test_thread)
    await session.refresh(test_user)
    
    # Test relationships
    assert test_thread.owner.id == test_user.id
    assert test_thread in test_user.owned_threads
    assert any(p.user_id == test_user.id for p in test_thread.participants)
    assert any(m.content == "Test message" for m in test_thread.messages)

@pytest.mark.asyncio
async def test_user_roles():
    assert UserRole.ADMIN.value == "admin"
    assert UserRole.USER.value == "user"

@pytest.mark.asyncio
async def test_agent_types():
    assert AgentType.LAWYER.value == "lawyer"
    assert AgentType.ACCOUNTANT.value == "accountant"
    assert AgentType.PSYCHOLOGIST.value == "psychologist"

@pytest.mark.asyncio
async def test_thread_statuses():
    assert ThreadStatus.ACTIVE.value == "active"
    assert ThreadStatus.ARCHIVED.value == "archived"
    assert ThreadStatus.CLOSED.value == "closed"

@pytest.mark.asyncio
async def test_cascade_deletes(session, test_thread):
    # Create related records
    agent = ThreadAgent(
        thread_id=test_thread.id,
        agent_type=AgentType.LAWYER
    )
    session.add(agent)
    
    message = Message(
        thread_id=test_thread.id,
        content="Test message"
    )
    session.add(message)
    
    await session.commit()
    
    # Delete thread and verify cascading deletes
    await session.delete(test_thread)
    await session.commit()
    
    # Verify related records are deleted
    result = await session.execute(
        "SELECT * FROM thread_agents WHERE thread_id = :thread_id",
        {"thread_id": str(test_thread.id)}
    )
    assert result.fetchone() is None
    
    result = await session.execute(
        "SELECT * FROM messages WHERE thread_id = :thread_id",
        {"thread_id": str(test_thread.id)}
    )
    assert result.fetchone() is None
