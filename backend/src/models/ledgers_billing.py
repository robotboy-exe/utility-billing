"""US4: billing_config, billing_override, standard_amount_change (docs/04 §6.4),
transaction, monthly_bill, payment_allocation, advance_movement,
bill_adjustment (docs/04 §6.5), utility_provider, utility_bill_payment
(docs/04 §6.6)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..enums import (
    ADVANCE_MOVEMENT_TYPE,
    ALLOCATION_TYPE,
    BILL_ADJUSTMENT_TYPE,
    BILLING_OVERRIDE_DECISION,
    DIRECTION,
    MATCHING_STATUS,
    RECORD_CATEGORY,
    enum_check,
)
from .base import Base, IdCreatedAt, UpdatedAt, UTCDateTime, currency, money, utcnow


class BillingConfig(IdCreatedAt, Base):
    __tablename__ = "billing_config"
    __table_args__ = (
        sa.Index(
            "uq_billing_config_org_wide",
            "organization_id",
            unique=True,
            sqlite_where=sa.text("property_id IS NULL"),
            postgresql_where=sa.text("property_id IS NULL"),
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    property_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("property.id"),
        nullable=True,
        default=None,
    )
    standard_amount_minor: Mapped[int] = money("standard_amount_minor")
    currency: Mapped[str] = currency()
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
    updated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("admin_user.id"),
        nullable=True,
        default=None,
    )


class BillingOverride(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "billing_override"
    __table_args__ = (
        sa.UniqueConstraint("tenancy_id", "billing_month"),
        enum_check("decision", BILLING_OVERRIDE_DECISION),
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
    billing_month: Mapped[date] = mapped_column(sa.Date, nullable=False)
    decision: Mapped[str] = mapped_column(sa.Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("admin_user.id"),
        nullable=True,
        default=None,
    )


class StandardAmountChange(IdCreatedAt, Base):
    """Append-only rate-change history; no updated_at (docs/04 §11.1)."""

    __tablename__ = "standard_amount_change"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    previous_amount_minor: Mapped[int] = money("previous_amount_minor")
    new_amount_minor: Mapped[int] = money("new_amount_minor")
    currency: Mapped[str] = currency()
    auto_note: Mapped[str] = mapped_column(sa.Text, nullable=False)
    custom_note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    admin_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("admin_user.id"),
        nullable=False,
    )
    effective_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class Transaction(IdCreatedAt, Base):
    """Append-only persisted transactions, both ledgers (docs/04 §6.5, §11.1)."""

    __tablename__ = "transaction"
    __table_args__ = (
        enum_check("record_category", RECORD_CATEGORY),
        enum_check("direction", DIRECTION),
        enum_check("matching_status", MATCHING_STATUS),
        sa.Index("ix_transaction_org_date", "organization_id", "transaction_date"),
        sa.Index("ix_transaction_tenancy", "tenancy_id"),
        sa.Index("ix_transaction_batch", "import_batch_id"),
        sa.Index("ix_transaction_category", "record_category"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("import_batch.id"),
        nullable=True,
        default=None,
    )
    record_category: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source: Mapped[str] = mapped_column(sa.Text, nullable=False)
    transaction_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    transaction_time: Mapped[time | None] = mapped_column(sa.Time, nullable=True)
    channel: Mapped[str] = mapped_column(sa.Text, nullable=False)
    direction: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description_raw: Mapped[str] = mapped_column(sa.Text, nullable=False)
    counterparty_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    counterparty_name_normalized: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    counterparty_reference: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    amount_minor: Mapped[int] = money("amount_minor", positive=True)
    currency: Mapped[str] = currency()
    tenancy_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("tenancy.id"),
        nullable=True,
        default=None,
    )
    matching_status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        default="unmatched",
        server_default=sa.text("'unmatched'"),
    )
    duplicate_key: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)


class MonthlyBill(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "monthly_bill"
    __table_args__ = (
        sa.UniqueConstraint("tenancy_id", "billing_month"),
        sa.Index("ix_monthly_bill_month", "billing_month"),
        sa.Index("ix_monthly_bill_org_month", "organization_id", "billing_month"),
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
    billing_month: Mapped[date] = mapped_column(sa.Date, nullable=False)
    standard_amount_minor: Mapped[int] = money("standard_amount_minor")
    final_amount_minor: Mapped[int] = money("final_amount_minor")
    currency: Mapped[str] = currency()
    is_adjusted: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )


class PaymentAllocation(IdCreatedAt, Base):
    """Append-only allocations; corrections are reversal/correction rows (docs/04 §11.1)."""

    __tablename__ = "payment_allocation"
    __table_args__ = (
        enum_check("allocation_type", ALLOCATION_TYPE),
        sa.Index("ix_allocation_transaction", "transaction_id"),
        sa.Index("ix_allocation_bill", "monthly_bill_id"),
    )

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("transaction.id"),
        nullable=False,
    )
    monthly_bill_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("monthly_bill.id"),
        nullable=False,
    )
    amount_minor: Mapped[int] = money("amount_minor", positive=True)
    currency: Mapped[str] = currency()
    allocation_type: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        default="automatic",
        server_default=sa.text("'automatic'"),
    )
    reverses_allocation_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("payment_allocation.id"),
        nullable=True,
        default=None,
    )


class AdvanceMovement(IdCreatedAt, Base):
    """Append-only advance-credit events; the balance stays derived (docs/04 §7.4–§7.5)."""

    __tablename__ = "advance_movement"
    __table_args__ = (
        enum_check("movement_type", ADVANCE_MOVEMENT_TYPE),
        sa.Index("ix_advance_transaction", "transaction_id"),
        sa.Index("ix_advance_tenancy_occurred", "tenancy_id", "occurred_at"),
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
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("transaction.id"),
        nullable=False,
    )
    movement_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    amount_minor: Mapped[int] = money("amount_minor", positive=True)
    currency: Mapped[str] = currency()
    monthly_bill_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("monthly_bill.id"),
        nullable=True,
        default=None,
    )
    allocation_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("payment_allocation.id"),
        nullable=True,
        default=None,
    )
    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class BillAdjustment(IdCreatedAt, Base):
    """Append-only bill adjustments: rate_change or write_off (docs/04 §11.1)."""

    __tablename__ = "bill_adjustment"
    __table_args__ = (enum_check("adjustment_type", BILL_ADJUSTMENT_TYPE),)

    monthly_bill_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("monthly_bill.id"),
        nullable=False,
    )
    adjustment_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    previous_amount_minor: Mapped[int] = money("previous_amount_minor")
    new_amount_minor: Mapped[int] = money("new_amount_minor")
    currency: Mapped[str] = currency()
    public_note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    custom_note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    internal_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    admin_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("admin_user.id"),
        nullable=False,
    )


class UtilityProvider(IdCreatedAt, UpdatedAt, Base):
    __tablename__ = "utility_provider"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=True,
        default=None,
    )
    code: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    channel_signature: Mapped[str] = mapped_column(sa.Text, nullable=False)
    reference_label: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )


class UtilityBillPayment(IdCreatedAt, Base):
    """Append-only provider payments; no tenancy-matching column (docs/04 §6.6, §8.3)."""

    __tablename__ = "utility_bill_payment"
    __table_args__ = (
        sa.Index("ix_utility_spend_provider_month", "provider_id", "spend_month"),
        sa.Index("ix_utility_spend_org_month", "organization_id", "spend_month"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("organization.id"),
        nullable=False,
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("transaction.id"),
        nullable=False,
        unique=True,
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("utility_provider.id"),
        nullable=False,
    )
    customer_reference: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    amount_minor: Mapped[int] = money("amount_minor", positive=True)
    currency: Mapped[str] = currency()
    payment_datetime: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    spend_month: Mapped[date] = mapped_column(sa.Date, nullable=False)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("import_batch.id"),
        nullable=True,
        default=None,
    )
