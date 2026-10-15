"""Engine/session/config resolution from DATABASE_URL (constitution Database & Schema).

PostgreSQL for production/CI, SQLite for local development.
"""

from __future__ import annotations

import os

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models.base import Base

DEFAULT_DATABASE_URL = "sqlite:///./utility_billing_dev.db"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_db_engine(url: str | None = None) -> sa.Engine:
    resolved = url or get_database_url()
    if resolved.startswith("sqlite"):
        engine = sa.create_engine(
            resolved,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # SQLite does not enforce foreign keys unless requested per connection.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return sa.create_engine(resolved)


def create_session_factory(engine: sa.Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_database(engine: sa.Engine | None = None) -> sa.Engine:
    """Create every registered table (the immutable triggers are emitted by the
    shared after_create listener, D-8)."""
    if engine is None:
        engine = create_db_engine()
    Base.metadata.create_all(engine)
    return engine
