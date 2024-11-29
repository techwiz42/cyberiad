# tests/conftest.py
import pytest
import asyncio
import asyncpg
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "backend"))
sys.path.append(str(Path(__file__).resolve().parent.parent))

from models import Base, UserRole

# Database configuration (keep your existing configuration)
DB_HOST = os.getenv('TEST_DB_HOST', 'localhost')
DB_PORT = os.getenv('TEST_DB_PORT', '5432')
DB_USER = os.getenv('TEST_DB_USER', 'postgres')
DB_PASS = os.getenv('TEST_DB_PASS', 'postgres')
DB_NAME = os.getenv('TEST_DB_NAME', 'cyberiad_test')

POSTGRES_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/postgres"
TEST_DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

async def create_test_database():
    """Create test database if it doesn't exist."""
    try:
        conn = await asyncpg.connect(POSTGRES_URL)
        result = await conn.fetchrow(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            DB_NAME
        )
        if not result:
            await conn.execute(f'CREATE DATABASE {DB_NAME}')
        await conn.close()
    except Exception as e:
        print(f"Error creating test database: {e}")
        raise

async def drop_test_database():
    """Drop test database if it exists."""
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
    except Exception as e:
        print(f"Error dropping test database: {e}")
        raise

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database and return a SQLAlchemy engine."""
    await create_test_database()
    
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    
    # Create tables and types
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Create enum types if they don't exist
        await conn.execute(text("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
                    CREATE TYPE user_role AS ENUM ('admin', 'user');
                END IF;
            END $$;
        """))
    
    try:
        yield engine
    finally:
        await engine.dispose()
        await drop_test_database()

@pytest.fixture
async def test_db_session(test_engine):
    """Create a new database session for a test."""
    # Get the engine (not a generator anymore)
    engine = test_engine
    
    # Create session
    async_session = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.rollback()

@pytest.fixture
async def reset_db(test_engine):
    """Reset the database between tests."""
    engine = test_engine
    async with AsyncSession(engine) as session:
        async with session.begin():
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(text(f'TRUNCATE TABLE {table.name} CASCADE'))
