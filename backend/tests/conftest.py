import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
import asyncio
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from uuid import uuid4
from datetime import datetime, UTC
from models import Base, User, Thread, ThreadParticipant, UserRole, ThreadStatus


# Database configuration
DB_HOST = os.getenv('TEST_DB_HOST', 'localhost')
DB_PORT = os.getenv('TEST_DB_PORT', '5432')
DB_USER = os.getenv('TEST_DB_USER', 'postgres')
DB_PASS = os.getenv('TEST_DB_PASS', 'postgres')
DB_NAME = os.getenv('TEST_DB_NAME', 'cyberiad_test')

POSTGRES_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/postgres"
TEST_DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

@pytest.fixture
def mock_message(mock_user):
    """Fixture to provide a mock message for tests."""
    return Message(
        id=uuid4(),
        content="Test message",
        created_at=datetime.now(timezone.utc),  # Timezone-aware
        user_id=mock_user.id,
        thread_id=uuid4(),
        message_metadata={}
    )

async def create_test_database():
    """Create the test database and tables."""
    print(f"Creating test database {DB_NAME}...")  # Debug print
    try:
        conn = await asyncpg.connect(POSTGRES_URL)
        result = await conn.fetchrow(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            DB_NAME
        )
        if not result:
            await conn.execute(f'CREATE DATABASE {DB_NAME}')
        await conn.close()
        print(f"Database {DB_NAME} created successfully")  # Debug print
    except Exception as e:
        print(f"Error creating database: {e}")
        raise

@pytest.fixture
async def test_engine():
    """Create test engine instance."""
    return engine

@pytest.fixture
async def reset_db(test_engine):
    """Reset database state between tests."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return True  # Return a simple value instead of the engine

@pytest.fixture
async def test_thread(test_db_session):
    """Create a test thread with owner for testing."""
    async with test_db_session as session:
        # Create a test user
        test_user = User(
            id=uuid4(),
            username=f"testuser_{uuid4().hex[:8]}",
            email=f"test_{uuid4().hex[:8]}@example.com",
            hashed_password="test_password",
            role=UserRole.USER,
            created_at=datetime.now(UTC)
        )
        session.add(test_user)
        await session.flush()

        # Create a test thread
        test_thread = Thread(
            id=uuid4(),
            title="Test Thread",
            owner_id=test_user.id,
            status=ThreadStatus.ACTIVE,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        session.add(test_thread)
        await session.flush()

        # Add user as thread participant
        thread_participant = ThreadParticipant(
            thread_id=test_thread.id,
            user_id=test_user.id,
            joined_at=datetime.now(UTC),
            is_active=True
        )
        session.add(thread_participant)
        
        await session.commit()
        return test_thread.id, test_user.id

async def setup_tables():
    """Create all tables in the test database."""
    print("Creating tables...")  # Debug print
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tables created successfully")  # Debug print

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

def pytest_configure(config):
    """Run database setup when pytest starts."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_test_database())
    loop.run_until_complete(setup_tables())

def pytest_unconfigure(config):
    """Clean up database when pytest exits."""
    async def cleanup():
        try:
            conn = await asyncpg.connect(POSTGRES_URL)
            await conn.execute(f'''
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{DB_NAME}'
                AND pid <> pg_backend_pid()
            ''')
            await conn.execute(f'DROP DATABASE IF EXISTS {DB_NAME}')
            await conn.close()
            print(f"Test database {DB_NAME} dropped successfully")  # Debug print
        except Exception as e:
            print(f"Error dropping database: {e}")
            raise

    loop = asyncio.get_event_loop()
    loop.run_until_complete(cleanup())

# Create engine for sessions
engine = create_async_engine(TEST_DATABASE_URL, echo=True)

@pytest.fixture
async def test_db_session():
    """Create test session."""
    TestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as session:
        yield session
        await session.rollback()
