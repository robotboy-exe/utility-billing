import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects import postgresql

from ..enums import (
    TenancyStatus,
    RecordCategory,
    Direction,
    MatchingStatus,
    AllocationType,
    AdvanceMovementType,
    ImportBatchStatus,
    TotalsStatus,
)


class Base(DeclarativeBase):
    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id})"


def money(column_name: str = "amount_minor", *, positive: bool = False) -> sa.Column:
    """
    Create a money column helper.

    Args:
        column_name: Name of the column to create
        positive: If True, create CHECK (> 0), otherwise CHECK (>= 0)

    Returns:
        SQLAlchemy Column definition with appropriate CHECK constraint
    """
    if positive:
        return sa.Column(
            column_name,
            sa.BigInteger,
            sa.CheckConstraint(f"{column_name} > 0", name=f"{column_name}_check_positive"),
            nullable=False,
        )
    else:
        return sa.Column(
            column_name,
            sa.BigInteger,
            sa.CheckConstraint(f"{column_name} >= 0", name=f"{column_name}_check_non_negative"),
            nullable=False,
        )


def currency(column_name: str = "currency") -> sa.Column:
    """
    Create a currency column helper.

    Args:
        column_name: Name of the column to create

    Returns:
        SQLAlchemy Column definition with default currency
    """
    return sa.Column(
        column_name,
        sa.CHAR(3),
        default="NGN",
        nullable=False,
    )


class IdCreatedAtMixin(Base):
    """Mixin for models that need UUID id and created_at."""
    __abstract__ = True
    pass


class OrgScopedMixin(Base):
    """Mixin for models that need organization_id foreign key."""
    __abstract__ = True
    organization_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("organization.id"),
        nullable=False,
    )


class UpdatedAtMixin(Base):
    """Mixin for mutable tables that need updated_at."""
    __abstract__ = True
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class IdCreatedAtOrgScopedUpdatedAtMixin(IdCreatedAtMixin, OrgScopedMixin, UpdatedAtMixin):
    """Combined mixin for models with id, created_at, org_id, and updated_at."""
    __abstract__ = True
    pass


class IdCreatedAtOrgScopedMixin(IdCreatedAtMixin, OrgScopedMixin):
    """Combined mixin for models with id, created_at, and org_id."""
    __abstract__ = True
    pass


class IdCreatedAtUpdatedAtMixin(IdCreatedAtMixin, UpdatedAtMixin):
    """Combined mixin for models with id, created_at, and updated_at."""
    __abstract__ = True
    pass
