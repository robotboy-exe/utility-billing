"""Shared test fixtures (R-11, D-4, D-5).

Fresh in-memory SQLite per test, never the development database file.
PostgreSQL runs only when TEST_DATABASE_URL is set to a postgresql+psycopg://
URL; it never reads DATABASE_URL.
"""

from __future__ import annotations

import os

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from backend.src.models.base import Base

PG_URL_ENV = "TEST_DATABASE_URL"


def _configured_pg_url() -> str | None:
    url = os.environ.get(PG_URL_ENV)
    if url and url.startswith("postgresql+psycopg://"):
        return url
    return None


PG_URL = _configured_pg_url()


def create_schema(engine: Engine) -> None:
    """Reset state per test: drop_all + create_all (the shared immutable-trigger
    DDL is emitted by create_all's after_create listener, D-5/D-8)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _sqlite_engine() -> Engine:
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite does not enforce foreign keys unless requested per connection;
    # the contract tests require both engines to enforce the schema (FR-020).
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture
def sqlite_engine() -> Engine:
    engine = _sqlite_engine()
    create_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_engine() -> Engine:
    if PG_URL is None:
        pytest.skip("no PostgreSQL URL configured")
    engine = sa.create_engine(PG_URL)
    create_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture(params=["sqlite"] + (["postgresql"] if PG_URL else []))
def db_engine(request) -> Engine:
    """SQLite always; PostgreSQL only when TEST_DATABASE_URL is configured."""
    if request.param == "postgresql":
        engine = sa.create_engine(PG_URL)
    else:
        engine = _sqlite_engine()
    create_schema(engine)
    yield engine
    engine.dispose()
