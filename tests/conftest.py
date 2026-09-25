import os
import tempfile
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import Engine

from backend.src.db import init_database

# Environment variable for database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///:memory:")

@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Create all tables once per test session (models define the schema for
    the SQLite pass; Alembic baseline migration / Postgres validation are CI)."""
    init_database()
    yield

@pytest.fixture(scope="session")
def db_url():
    """Provide the database URL for the test session."""
    return DATABASE_URL

@pytest.fixture(scope="function")
def db_engine(db_url):
    """Create a fresh database engine for each test function."""
    if db_url.startswith("sqlite://"):
        # SQLite in-memory database with connection sharing
        engine = sa.create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # PostgreSQL - let the connection pool handle everything
        engine = sa.create_engine(db_url)

    yield engine

    # Cleanup
    engine.dispose()

@pytest.fixture(scope="function")
def db_session(db_engine):
    """Provide a transactional database session for each test."""
    with db_engine.connect() as connection:
        # Start a transaction
        trans = connection.begin()

        # Create a session
        session = Session(bind=connection)

        yield session

        # Rollback the transaction (don't commit)
        trans.rollback()
        session.close()

@pytest.fixture(scope="function")
def test_db_path():
    """Create a temporary file path for SQLite file-based testing."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        yield Path(path)
    finally:
        if os.path.exists(path):
            os.unlink(path)

@pytest.fixture(scope="session")
def is_postgresql():
    """Check if PostgreSQL is being used for this test session."""
    return DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgresql+psycopg2://")

@pytest.fixture
def cleanup_database(db_session):
    """Clean up database state after each test if needed."""
    yield
    # Additional cleanup can be added here if needed
    db_session.expire_all()

# Make common fixtures available to all test modules
pytest_plugins = ()
