"""US1: organization and admin_user (docs/04 §6.2, §6.1)."""

from __future__ import annotations

import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, validates

from .base import Base, IdCreatedAt, UpdatedAt


class Organization(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    timezone: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        default="Africa/Lagos",
        server_default=sa.text("'Africa/Lagos'"),
    )

    @validates("timezone")
    def _validate_timezone(self, key: str, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"invalid IANA timezone: {value!r}") from exc
        return value


class AdminUser(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "admin_user"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
