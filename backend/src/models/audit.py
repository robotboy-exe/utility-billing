"""US6: audit_log, admin_session, admin_login_attempt, tenant_login_attempt
(docs/04 §6.9, §6.1)."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdCreatedAt, UTCDateTime, jsonb


class AuditLog(IdCreatedAt, Base):
    """Append-only audit trail; no updated_at (docs/04 §6.9, §11.1)."""

    __tablename__ = "audit_log"
    __table_args__ = (
        sa.CheckConstraint(
            "actor_type IN ('admin', 'system', 'tenant_session')",
            name="ck_actor_type_values",
        ),
        sa.Index("ix_audit_log_org_created", "organization_id", "created_at"),
        sa.Index("ix_audit_log_entity", "entity_type", "entity_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    actor_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True)
    action: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True)
    audit_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        jsonb(),
        nullable=True,
    )


class AdminSession(IdCreatedAt, Base):
    """Write-once admin session rows (docs/04 §6.1, §11.2)."""

    __tablename__ = "admin_session"

    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("admin_user.id"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    device_info: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class AdminLoginAttempt(IdCreatedAt, Base):
    """Operational, prunable admin rate-limiting data (docs/04 §6.1, §11.6)."""

    __tablename__ = "admin_login_attempt"
    __table_args__ = (
        sa.Index("ix_admin_login_attempt_admin_time", "admin_user_id", "attempted_at"),
        sa.Index("ix_admin_login_attempt_ip_time", "source_ip", "attempted_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    admin_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("admin_user.id"),
        nullable=True,
        default=None,
    )
    source_ip: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    succeeded: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)


class TenantLoginAttempt(IdCreatedAt, Base):
    """Operational, prunable tenant rate-limiting data (docs/04 §6.1, §11.6)."""

    __tablename__ = "tenant_login_attempt"
    __table_args__ = (
        sa.Index("ix_tenant_login_attempt_tenancy_time", "tenancy_id", "attempted_at"),
        sa.Index("ix_tenant_login_attempt_ip_time", "source_ip", "attempted_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    tenancy_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("tenancy.id"),
        nullable=True,
        default=None,
    )
    source_ip: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    succeeded: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
