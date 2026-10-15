"""US3: import_profile, import_channel_category_mapping, import_batch,
staged_import_row (docs/04 §6.7)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import (
    CHANNEL_CATEGORY,
    DIRECTION,
    IMPORT_BATCH_STATUS,
    TOTALS_STATUS,
    enum_check,
)
from .base import Base, IdCreatedAt, UpdatedAt, UTCDateTime, currency, jsonb, money


class ImportProfile(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "import_profile"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=True,
        default=None,
    )
    code: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    detection_config: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)
    parse_config: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)
    file_limits: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )


class ImportChannelCategoryMapping(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "import_channel_category_mapping"
    __table_args__ = (
        enum_check("direction", DIRECTION),
        enum_check("category", CHANNEL_CATEGORY),
        sa.Index(
            "uq_channel_mapping_profile_channel_direction",
            "import_profile_id",
            "channel",
            sa.func.coalesce(sa.text("direction"), sa.text("'ANY'")),
            unique=True,
        ),
    )

    import_profile_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("import_profile.id"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(sa.Text, nullable=False)
    direction: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    category: Mapped[str] = mapped_column(sa.Text, nullable=False)


class ImportBatch(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "import_batch"
    __table_args__ = (
        enum_check("status", IMPORT_BATCH_STATUS),
        enum_check("totals_status", TOTALS_STATUS),
        sa.Index(
            "uq_import_batch_fingerprint_confirmed",
            "statement_fingerprint",
            unique=True,
            sqlite_where=sa.text("status IN ('confirmed', 'completed')"),
            postgresql_where=sa.text("status IN ('confirmed', 'completed')"),
        ),
        sa.Index("ix_import_batch_statement_fingerprint", "statement_fingerprint"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    import_profile_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("import_profile.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        default="parsing",
        server_default=sa.text("'parsing'"),
    )
    statement_account_holder: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    statement_account_number: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    statement_start_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    statement_end_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    source_file_sha256: Mapped[str | None] = mapped_column(sa.CHAR(64), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    source_page_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    currency: Mapped[str] = currency()
    totals_status: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    statement_fingerprint: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    ignored_summary: Mapped[dict | None] = mapped_column(jsonb(), nullable=True)
    tenant_payment_row_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    tenant_payment_total_minor: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True
    )
    utility_payment_row_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    utility_payment_total_minor: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True
    )
    duplicate_row_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    invalid_row_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    unrecognized_row_count: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    unrecognized_rows: Mapped[list | None] = mapped_column(jsonb(), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class StagedImportRow(IdCreatedAt, Base):
    """Write-once staging rows; no updated_at, no currency (docs/04 §3.5, §11.2)."""

    __tablename__ = "staged_import_row"
    __table_args__ = (
        enum_check("direction", DIRECTION),
        sa.CheckConstraint(
            "row_category IN ('tenant_payment', 'utility_bill_payment')",
            name="ck_row_category_values",
        ),
        sa.CheckConstraint(
            "parse_status IN ('valid', 'duplicate', 'invalid')",
            name="ck_parse_status_values",
        ),
        sa.Index("ix_staged_import_row_batch", "import_batch_id"),
    )

    import_batch_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("import_batch.id"),
        nullable=False,
    )
    row_category: Mapped[str] = mapped_column(sa.Text, nullable=False)
    transaction_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    transaction_time: Mapped[time | None] = mapped_column(sa.Time, nullable=True)
    channel: Mapped[str] = mapped_column(sa.Text, nullable=False)
    direction: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description_raw: Mapped[str] = mapped_column(sa.Text, nullable=False)
    counterparty_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    counterparty_reference: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    amount_minor: Mapped[int] = money("amount_minor", positive=True)
    duplicate_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    parse_status: Mapped[str] = mapped_column(sa.Text, nullable=False)
    parse_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    committed_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("transaction.id"),
        nullable=True,
        default=None,
    )
