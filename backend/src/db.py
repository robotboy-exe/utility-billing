"""Database configuration and engine setup for the Utility Billing backend.

This module provides the core database infrastructure including:
- SQLAlchemy engine configuration with support for PostgreSQL (production) and SQLite (development/testing)
- Session factory for database operations
- Database URL configuration with environment variable support

The configuration follows the constitution Database & Schema discipline:
- PostgreSQL for production
- SQLite for local development
- Connection pooling and timeout settings
"""

import os
from typing import Generator

import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import SQLAlchemyError

from .enums import (
    TenancyStatus,
    RecordCategory,
    Direction,
    MatchingStatus,
    AllocationType,
    AdvanceMovementType,
    ImportBatchStatus,
    TotalsStatus,
)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./utility_billing_dev.db",  # Default to SQLite for development
)

# SQLAlchemy engine configuration
if DATABASE_URL.startswith("sqlite://"):
    # SQLite configuration for development/testing
    engine = sa.create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,  # Set to True for debugging
    )
else:
    # PostgreSQL configuration for production
    engine = sa.create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=3600,
        echo=False,  # Set to True for debugging
    )

# Session factory for dependency injection
session_local = sa.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Generator[Session, None, None]:
    """
    Provide a database session for a request.

    This function is intended for use with FastAPI dependency injection.
    Yields a database session and ensures it's properly closed after use.
    """
    session = session_local()
    try:
        yield session
    except SQLAlchemyError as e:
        session.rollback()
        raise e
    finally:
        session.close()


def init_database() -> None:
    """
    Initialize the database by creating all tables.

    This function should be called during application startup to ensure
    all tables are created if they don't already exist.
    """
    from .models import Base
    Base.metadata.create_all(bind=engine)


def get_engine() -> sa.engine.Engine:
    """Get the SQLAlchemy engine instance."""
    return engine


def get_session_local() -> sa.orm.sessionmaker:
    """Get the session local factory."""
    return session_local


# Convenience function for database health check
def check_database_connection() -> bool:
    """
    Check if the database is accessible.

    Returns:
        True if the database is accessible, False otherwise.
    """
    try:
        with engine.connect() as connection:
            connection.execute(sa.text("SELECT 1"))
        return True
    except Exception:
        return False


# Database diagnostics
def get_database_info() -> dict:
    """
    Get information about the database connection.

    Returns:
        Dictionary with database connection information.
    """
    return {
        "database_url": DATABASE_URL,
        "database_type": "postgresql" if DATABASE_URL.startswith("postgresql://") else "sqlite",
        "connection_available": check_database_connection(),
        "pool_size": engine.pool.size() if hasattr(engine.pool, 'size') else None,
    }
