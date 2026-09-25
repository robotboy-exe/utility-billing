"""Tenancy and tenant models for User Story 1.

This module defines the tenancy.py models required for User Story 1:
- tenancy
- tenant
- sender_alias

These models establish the tenancy/tenant hierarchy and the active tenancy
constraint (one-active-tenancy-per-room) which is a core invariant of the system.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from .base import IdCreatedAtMixin, OrgScopedMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from .org import Organization, Property, Room


class Tenancy(IdCreatedAtMixin, UpdatedAtMixin):
    """
    Occupancy period and tenant-portal privacy boundary.

    Properties:
    - Denormalized organization_id for scoping
    - Partial unique active-tenancy constraint (one-active-tenancy-per-room)
    - Status transitions: draft → active → closed
    - Closed tenancies lose portal access (ADR-026)
    """

    __tablename__ = "tenancy"

    organization_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("organization.id"),
        nullable=False,
    )

    room_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("room.id"),
        nullable=False,
    )

    status: Mapped[str] = sa.Column(
        sa.Enum("draft", "active", "closed", name="tenancy_status"),
        default="draft",
        nullable=False,
    )

    start_date: Mapped[datetime.date] = sa.Column(sa.Date, nullable=False)
    end_date: Mapped[datetime.date] = sa.Column(sa.Date, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = sa.orm.relationship(
        "Organization", backref="tenancies"
    )
    room: Mapped["Room"] = sa.orm.relationship(
        "Room", back_populates="tenancies"
    )

    # In a real implementation, partial unique index would be defined in the
    # migration using postgresql_where="status='active'"

    def __repr__(self) -> str:
        return f"Tenancy(id={self.id}, room={self.room_id}, status={self.status})"


class Tenant(IdCreatedAtMixin, UpdatedAtMixin):
    """Occupant(s) of a tenancy; no individual logins."""

    __tablename__ = "tenant"

    tenancy_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("tenancy.id"),
        nullable=False,
    )

    name: Mapped[str] = sa.Column(sa.String, nullable=False)
    email: Mapped[str] = sa.Column(sa.String, nullable=True)
    phone: Mapped[str] = sa.Column(sa.String, nullable=True)

    # Relationships
    tenancy: Mapped["Tenancy"] = sa.orm.relationship(
        "Tenancy", backref="tenants"
    )

    def __repr__(self) -> str:
        return f"Tenant(id={self.id}, tenancy={self.tenancy_id}, name={self.name})"


class SenderAlias(IdCreatedAtMixin, UpdatedAtMixin):
    """
    Accepted bank sender name for tenancy matching.

    Properties:
    - Normalized sender name for matching consistency
    - Unique per tenancy: (tenancy_id, normalized_name) UNIQUE
    - Organization-scoped for matching visibility
    """

    __tablename__ = "sender_alias"

    organization_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("organization.id"),
        nullable=False,
    )

    tenancy_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("tenancy.id"),
        nullable=False,
    )

    display_name: Mapped[str] = sa.Column(sa.String, nullable=False)
    normalized_name: Mapped[str] = sa.Column(sa.String, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = sa.orm.relationship(
        "Organization", backref="sender_aliases"
    )
    tenancy: Mapped["Tenancy"] = sa.orm.relationship(
        "Tenancy", backref="sender_aliases"
    )

    def __repr__(self) -> str:
        return f"SenderAlias(id={self.id}, tenancy={self.tenancy_id}, normalized_name={self.normalized_name})"
