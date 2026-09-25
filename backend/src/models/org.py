"""Organization and property models for User Story 1.

This module defines the org.py models required for User Story 1:
- organization
- property
- room

These models establish the org/property/room hierarchy that forms the foundation
for all financial records.

Test file: tests/test_uniqueness.py
Task: T010 [P] [US1] Create organization, property, room models in backend/src/models/org.py
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped

from .base import IdCreatedAtMixin, OrgScopedMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from .tenancy import Tenancy


class Organization(IdCreatedAtMixin):
    """Root isolation boundary (ADR-001); owns all scoped records."""

    __tablename__ = "organization"

    name: Mapped[str] = sa.Column(sa.String, nullable=False)
    # Additional org-specific fields can be added here as needed

    # Relationship to properties
    properties: Mapped[list["Property"]] = sa.orm.relationship(
        "Property", back_populates="organization"
    )

    def __repr__(self) -> str:
        return f"Organization(id={self.id}, name={self.name})"


class Property(IdCreatedAtMixin, OrgScopedMixin):
    """Physical building; belongs to one organization and contains rooms."""

    __tablename__ = "property"

    organization_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("organization.id"),
        nullable=False,
    )

    name: Mapped[str] = sa.Column(sa.String, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = sa.orm.relationship(
        "Organization", back_populates="properties"
    )
    rooms: Mapped[list["Room"]] = sa.orm.relationship(
        "Room", back_populates="parent_property"
    )

    def __repr__(self) -> str:
        return f"Property(id={self.id}, name={self.name})"


class Room(IdCreatedAtMixin, UpdatedAtMixin):
    """
    Physical space, persists across tenancies.

    Properties:
    - Belongs to a property (organization scoping through property.organization_id)
    - Can have only one active tenancy at a time (enforced by Tenancy model)
    - Has room-level fields
    """

    __tablename__ = "room"

    property_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("property.id"),
        nullable=False,
    )

    label: Mapped[str] = sa.Column(sa.String, nullable=False)
    is_active: Mapped[bool] = sa.Column(sa.Boolean, default=True)

    # Relationships
    parent_property: Mapped["Property"] = sa.orm.relationship(
        "Property", back_populates="rooms"
    )

    # Tenancy relationship - reverse lookup
    tenancies: Mapped[list["Tenancy"]] = sa.orm.relationship(
        "Tenancy", back_populates="room"
    )

    @property
    def organization_id(self) -> uuid.UUID:
        """Get organization_id from property (organization scoping)."""
        return self.parent_property.organization_id

    @property
    def organization(self):
        """Get organization from property (organization scoping)."""
        return self.parent_property.organization

    def __repr__(self) -> str:
        return f"Room(id={self.id}, label={self.label})"
