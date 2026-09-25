"""Utility bill payment models for User Story 4.

This module defines the utility.py models required for User Story 4:
- utility_provider
- utility_bill_payment

These models implement the strictly separate second ledger for global utility provider registry and outgoing provider payments.
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped

from .base import IdCreatedAtMixin, OrgScopedMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from .ledger import Transaction
    from .tenancy import Tenancy


class UtilityProvider(IdCreatedAtMixin, UpdatedAtMixin):
    """
    Global/system-wide utility provider registry.

    Properties:
    - Global scope: organization_id nullable = null for global providers
    - Unique code per provider (e.g. BEDC)
    - Active status for provider lifecycle
    """

    __tablename__ = "utility_provider"

    organization_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("organization.id"),
        nullable=True,  # Can be null for global providers
    )

    code: Mapped[str] = sa.Column(sa.String, unique=True, nullable=False)
    display_name: Mapped[str] = sa.Column(sa.String, nullable=False)
    channel_signature: Mapped[str] = sa.Column(sa.String, nullable=False)
    reference_label: Mapped[str] = sa.Column(sa.String, nullable=False)
    is_active: Mapped[bool] = sa.Column(sa.Boolean, default=True)

    # Relationships
    organization: Mapped["Organization"] = sa.orm.relationship(
        "Organization", backref="utility_providers"
    )

    # Utility bill payments related to this provider
    bill_payments: Mapped[list["UtilityBillPayment"]] = sa.orm.relationship(
        "UtilityBillPayment", back_populates="provider"
    )

    def __repr__(self) -> str:
        return f"UtilityProvider(id={self.id}, code={self.code}, name={self.display_name})"


class UtilityBillPayment(IdCreatedAtMixin):
    """
    Outgoing provider payment; never settles tenant bills.

    Properties:
    - One-to-one with a transaction (UNIQUE transaction_id)
    - References a global utility provider
    - Month-bounded spend tracking
    - No tenancy matching state or tenant balance reconciliation
    """

    __tablename__ = "utility_bill_payment"

    organization_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("organization.id"),
        nullable=False,
    )

    transaction_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("transaction.id"),
        unique=True,
        nullable=False,
    )

    provider_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("utility_provider.id"),
        nullable=False,
    )

    customer_reference: Mapped[str] = sa.Column(sa.String, nullable=False)
    amount_minor: Mapped[int] = sa.Column(
        sa.BigInteger,
        sa.CheckConstraint("amount_minor > 0", name="ubp_amount_minor_positive_check"),
        nullable=False,
    )
    currency: Mapped[str] = sa.Column(
        sa.CHAR(3),
        default="NGN",
        nullable=False,
    )
    payment_datetime: Mapped[datetime] = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
    spend_month: Mapped[datetime.date] = sa.Column(
        sa.Date,
        nullable=False,
    )
    import_batch_id: Mapped[uuid.UUID] = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("import_batch.id"),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = sa.orm.relationship(
        "Organization", backref="utility_bill_payments"
    )
    transaction: Mapped["Transaction"] = sa.orm.relationship(
        "Transaction", back_populates="utility_bill_payment"
    )
    provider: Mapped["UtilityProvider"] = sa.orm.relationship(
        "UtilityProvider", back_populates="bill_payments"
    )

    @property
    def is_matching_eligible(self) -> bool:
        """
        Check if this utility bill payment can participate in tenancy matching.

        Returns False - utility bill payments never carry tenancy matching state
        as per User Story 4 requirements.
        """
        return False

    @property
    def spend_year(self) -> int:
        """Extract year from spend_month for reporting."""
        return self.spend_month.year

    @property
    def spend_quarter(self) -> int:
        """Extract quarter from spend_month for reporting."""
        return (self.spend_month.month - 1) // 3 + 1

    def __repr__(self) -> str:
        return f"UtilityBillPayment(id={self.id}, provider={self.provider_id}, amount={self.amount_minor})"
