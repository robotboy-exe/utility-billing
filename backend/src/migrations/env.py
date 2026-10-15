"""Alembic environment: upgrade/downgrade run against Base.metadata.

The URL comes from DATABASE_URL (PostgreSQL production/CI, SQLite local).
The immutable-table trigger DDL is applied by the baseline migration itself,
which calls the same per-engine function ``create_all`` uses (D-8, R-5, R-10).
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

import sqlalchemy as sa
from alembic import context
from sqlalchemy import pool

# Repository root on sys.path so `backend.src.*` imports resolve regardless of
# how the alembic CLI was invoked.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.src.db import enable_sqlite_foreign_keys, get_database_url  # noqa: E402
from backend.src.models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = sa.create_engine(get_database_url(), poolclass=pool.NullPool)
    if connectable.dialect.name == "sqlite":
        # Alembic's own engine must enforce foreign keys exactly like the app
        # engine (db.py) so migrations and create_all behave identically.
        enable_sqlite_foreign_keys(connectable)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
