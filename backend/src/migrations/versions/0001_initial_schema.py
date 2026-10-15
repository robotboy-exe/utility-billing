"""baseline: full MVP schema (docs/04 §6, §9, §11)

Revision ID: 0001
Revises:
Create Date: 2026-10-15

Single reversible baseline. Tables, constraints and indexes come straight from
``Base.metadata`` (no hand-written DDL, so the migration cannot drift from the
models). The eight append-only triggers are emitted through the same per-engine
function ``create_all`` uses (D-8, R-5 with A2/A3/A4).
"""

from __future__ import annotations

from alembic import op

from backend.src.models import Base
from backend.src.models.base import (
    immutable_trigger_create_sql,
    immutable_trigger_drop_sql,
)

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    for statement in immutable_trigger_create_sql(bind.dialect.name):
        op.execute(statement)


def downgrade() -> None:
    bind = op.get_bind()
    for statement in immutable_trigger_drop_sql(bind.dialect.name):
        op.execute(statement)
    Base.metadata.drop_all(bind=bind)
