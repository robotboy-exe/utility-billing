"""Identity and authentication models for User Story 1.

This module defines the identity.py models required for User Story 1:
- admin_user
- tenant_access_credential
- tenant_session

These models provide the identity and authentication foundation for the system,
including credential rotation and session validity rules.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from .base import IdCreatedAtMixin, OrgScopedMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from .tenancy import Tenancy


class AdminUser(IdCreatedAtMixin, UpdatedAtMixin):
    """
    Represents the administrator login (MVP: one admin per org).

    Fields:
    - id: UUID PK
    - organization_id: FK→organization (NOT NULL)
    - email: TEXT NOT NULL UNIQUE
    - password_hash: TEXT NOT NULL, never plaintext
    - is_active: BOOL NOT NULL DEFAULT true
    - created_at, updated_at
    """

    __tablename__ = "admin_user"

    organization_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("organization.id"),
        nullable=False,
    )

    email: Mapped[str] = sa.Column(sa.String, unique=True, nullable=False)
    password_hash: Mapped[str] = sa.Column(sa.Text, nullable=False)
    is_active: Mapped[bool] = sa.Column(sa.Boolean, default=True, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = sa.orm.relationship(
        "Organization", backref="admin_users"
    )

    def __repr__(self) -> str:
        return f"AdminUser(id={self.id}, email={self.email})"


class TenantAccessCredential(IdCreatedAtMixin, UpdatedAtMixin):
    """
    Hashed shared access code per tenancy.

    Hashed shared access code per tenancy.

    Fields:
    - id
    - tenancy_id: FK→tenancy NOT NULL UNIQUE
    - access_code_hash: TEXT NOT NULL
    - credential_version: INT NOT NULL DEFAULT 1
    - is_active: BOOL NOT NULL DEFAULT true
    - created_at, updated_at, rotated_at (semantic)

    State transition (rotation): reset → increment credential_version,
    update hash, set rotated_at; prior sessions invalid.
    """

    __tablename__ = "tenant_access_credential"

    tenancy_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("tenancy.id"),
        unique=True,
        nullable=False,
    )

    access_code_hash: Mapped[str] = sa.Column(sa.Text, nullable=False)
    credential_version: Mapped[int] = sa.Column(
        sa.Integer, default=1, nullable=False
    )
    is_active: Mapped[bool] = sa.Column(sa.Boolean, default=True, nullable=False)
    rotated_at: Mapped[datetime] = sa.Column(
        sa.DateTime(timezone=True), nullable=True
    )  # semantic

    # Relationships
    tenancy: Mapped["Tenancy"] = sa.orm.relationship(
        "Tenancy", backref="tenant_access_credentials"
    )

    @property
    def is_rotated(self) -> bool:
        """Check if this credential has been rotated."""
        return self.rotated_at is not None

    def __repr__(self) -> str:
        return f"TenantAccessCredential(id={self.id}, tenancy={self.tenancy_id}, version={self.credential_version})"


class TenantSession(IdCreatedAtMixin):
    """
    Read-only session token snapshot for the tenant portal.

    Fields:
    - id
    - credential_id: FK→tenant_access_credential NOT NULL
    - credential_version: INT NOT NULL snapshot
    - token_hash: TEXT NOT NULL
    - device_info: TEXT
    - issued_at
    - expires_at
    - revoked_at
    - created_at

    Validity rule (derived): revoked_at IS NULL AND expires_at > now()
        AND credential_version = credential.credential_version
        AND credential.is_active = true
    """

    __tablename__ = "tenant_session"

    credential_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("tenant_access_credential.id"),
        nullable=False,
    )

    credential_version: Mapped[int] = sa.Column(sa.Integer, nullable=False)
    token_hash: Mapped[str] = sa.Column(sa.Text, nullable=False)
    device_info: Mapped[str] = sa.Column(sa.Text, nullable=True)

    issued_at: Mapped[datetime] = sa.Column(sa.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = sa.Column(sa.DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = sa.Column(
        sa.DateTime(timezone=True), nullable=True
    )  # semantic

    # Relationships
    credential: Mapped["TenantAccessCredential"] = sa.orm.relationship(
        "TenantAccessCredential", backref="tenant_sessions"
    )

    @property
    def is_valid(self) -> bool:
        """
        Derived validity rule for tenant_session.

        Session is valid if:
        1. Not revoked (revoked_at IS NULL)
        2. Not expired (expires_at > now())
        3. Credential version matches (credential_version = credential.credential_version)
        4. Credential is active (credential.is_active = true)
        """
        return (
            self.revoked_at is None
            and self.expires_at > datetime.now(timezone.utc)
            and self.credential_version == self.credential.credential_version
            and self.credential.is_active is True
        )

    def __repr__(self) -> str:
        return f"TenantSession(id={self.id}, credential={self.credential_id}, valid={self.is_valid})"
