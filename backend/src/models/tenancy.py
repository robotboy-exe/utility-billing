"""US2: property, room, tenancy, tenant, sender_alias, tenant access (docs/04 §6.2, §6.3, §6.1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import TENANCY_STATUS, enum_check
from .base import Base, IdCreatedAt, UpdatedAt, UTCDateTime


class Property(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "property"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)


class Room(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "room"

    property_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("property.id"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )


class Tenancy(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "tenancy"
    __table_args__ = (
        enum_check("status", TENANCY_STATUS),
        sa.Index(
            "uq_tenancy_room_active",
            "room_id",
            unique=True,
            sqlite_where=sa.text("status = 'active'"),
            postgresql_where=sa.text("status = 'active'"),
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("room.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        default="draft",
        server_default=sa.text("'draft'"),
    )
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)


class Tenant(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "tenant"

    tenancy_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("tenancy.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    email: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class SenderAlias(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "sender_alias"
    __table_args__ = (
        sa.UniqueConstraint("tenancy_id", "normalized_name"),
        sa.Index(
            "ix_sender_alias_organization_id_normalized_name",
            "organization_id",
            "normalized_name",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    tenancy_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("tenancy.id"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(sa.Text, nullable=False)


class TenantAccessCredential(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "tenant_access_credential"

    tenancy_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("tenancy.id"),
        nullable=False,
        unique=True,
    )
    access_code_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    credential_version: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=1,
        server_default=sa.text("1"),
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    rotated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
    )


class TenantSession(IdCreatedAt, Base):
    """Write-once session rows; validity is a predicate over stored columns (D-7)."""

    __tablename__ = "tenant_session"

    credential_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("tenant_access_credential.id"),
        nullable=False,
    )
    credential_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    token_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    device_info: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
    )
