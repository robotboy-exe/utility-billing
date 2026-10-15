"""Shared schema infrastructure (research.md R-2, R-3, R-5, R-6, R-8).

- Base: declarative base for every model.
- UTCDateTime: the single shared UTC-aware datetime TypeDecorator (R-2).
- Mixins: UUID PK + created_at, organization scoping, updated_at.
- money()/currency(): integer minor-unit helpers (R-3).
- Immutable-table trigger DDL (R-5): one function producing the per-engine
  SQL, run by ``create_all`` via an ``after_create`` listener (D-8).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """Timezone-aware UTC now — the only clock used by *_at columns (D-6)."""
    return datetime.now(timezone.utc)


class UTCDateTime(sa.TypeDecorator):
    """Shared UTC-aware datetime column type (R-2).

    Binds coerce to timezone-aware UTC; results always come back as
    timezone-aware UTC, on both PostgreSQL and SQLite.
    """

    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: sa.Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: sa.Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class IdCreatedAt:
    """UUID primary key (app-side uuid4, R-6) + created_at (docs/04 §3.1–§3.2)."""

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)


class OrgScoped:
    """Optional organization scoping (nullable; override with NOT NULL where docs/04 requires)."""

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=True,
        default=None,
    )


class UpdatedAt:
    """updated_at, applied only to the mutable tables of docs/04 §11.2 (D-6)."""

    updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
        default=utcnow,
        onupdate=utcnow,
    )


def money(column_name: str, *, positive: bool = False) -> sa.Column:
    """Integer minor-unit money column (R-3).

    ``positive=True`` emits CHECK (> 0); otherwise CHECK (>= 0).
    """
    symbol = ">" if positive else ">="
    return sa.Column(
        column_name,
        sa.BigInteger,
        sa.CheckConstraint(
            f"{column_name} {symbol} 0",
            name=f"ck_{column_name}_{'positive' if positive else 'non_negative'}",
        ),
        nullable=False,
    )


def currency(column_name: str = "currency") -> sa.Column:
    """currency CHAR(3) NOT NULL defaulting to the MVP currency (docs/04 §3.5)."""
    return sa.Column(
        column_name,
        sa.CHAR(3),
        nullable=False,
        default="NGN",
        server_default=sa.text("'NGN'"),
    )


IMMUTABLE_TABLES: tuple[str, ...] = (
    "transaction",
    "payment_allocation",
    "advance_movement",
    "bill_adjustment",
    "standard_amount_change",
    "utility_bill_payment",
    "audit_log",
)

_PG_GUARD_FUNCTION = (
    "CREATE OR REPLACE FUNCTION ub_append_only_guard() RETURNS trigger AS $$\n"
    "BEGIN\n"
    "    RAISE EXCEPTION '% is append-only: % rejected', TG_TABLE_NAME, TG_OP;\n"
    "END;\n"
    "$$ LANGUAGE plpgsql"
)


def immutable_trigger_create_sql(
    dialect_name: str,
    tables: Iterable[str] | None = None,
) -> list[str]:
    """Per-engine trigger SQL blocking UPDATE/DELETE on the append-only tables (R-5).

    One DDL source for both engines; ``tables`` defaults to every immutable
    table (migration path) and is filtered by existence on the create_all path.
    """
    if tables is None:
        names = list(IMMUTABLE_TABLES)
    else:
        present = set(tables)
        names = [name for name in IMMUTABLE_TABLES if name in present]
    if not names:
        return []

    if dialect_name == "postgresql":
        statements = [_PG_GUARD_FUNCTION]
        for table in names:
            statements.append(
                f'CREATE TRIGGER trg_{table}_immutable '
                f'BEFORE UPDATE OR DELETE ON "{table}" '
                "FOR EACH ROW EXECUTE FUNCTION ub_append_only_guard()"
            )
        return statements

    if dialect_name == "sqlite":
        statements = []
        for table in names:
            for operation in ("UPDATE", "DELETE"):
                statements.append(
                    f'CREATE TRIGGER IF NOT EXISTS "trg_{table}_immutable_{operation.lower()}" '
                    f'BEFORE {operation} ON "{table}" '
                    "BEGIN "
                    f"SELECT RAISE(ABORT, '{table} is append-only: {operation} rejected'); "
                    "END"
                )
        return statements

    raise ValueError(f"unsupported dialect for immutable triggers: {dialect_name}")


def immutable_trigger_drop_sql(dialect_name: str) -> list[str]:
    """Per-engine SQL dropping the immutable-table triggers (D-8, for migrations)."""
    if dialect_name == "postgresql":
        statements = []
        for table in IMMUTABLE_TABLES:
            statements.append(f'DROP TRIGGER IF EXISTS trg_{table}_immutable ON "{table}"')
        statements.append("DROP FUNCTION IF EXISTS ub_append_only_guard()")
        return statements

    if dialect_name == "sqlite":
        statements = []
        for table in IMMUTABLE_TABLES:
            for operation in ("update", "delete"):
                statements.append(f'DROP TRIGGER IF EXISTS "trg_{table}_immutable_{operation}"')
        return statements

    raise ValueError(f"unsupported dialect for immutable triggers: {dialect_name}")


@event.listens_for(Base.metadata, "after_create")
def _create_immutable_triggers(target, connection, **kw):
    """Emit the immutable-table trigger DDL whenever create_all runs (D-8)."""
    for statement in immutable_trigger_create_sql(
        connection.dialect.name,
        tables=target.tables.keys(),
    ):
        connection.execute(sa.text(statement))


__all__ = [
    "Base",
    "IMMUTABLE_TABLES",
    "IdCreatedAt",
    "OrgScoped",
    "UpdatedAt",
    "UTCDateTime",
    "currency",
    "immutable_trigger_create_sql",
    "immutable_trigger_drop_sql",
    "money",
    "utcnow",
]
