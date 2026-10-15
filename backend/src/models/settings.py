"""US5: portal_setting (docs/04 §6.8)."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdCreatedAt, UTCDateTime, utcnow


class PortalSetting(IdCreatedAt, Base):
    __tablename__ = "portal_setting"
    __table_args__ = (
        sa.UniqueConstraint("scope_type", "scope_id", "setting_key"),
        sa.CheckConstraint(
            "scope_type IN ('organization', 'property')",
            name="ck_scope_type_values",
        ),
    )

    scope_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    scope_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, nullable=False)
    setting_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    setting_value: Mapped[str] = mapped_column(sa.Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
