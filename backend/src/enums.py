"""Enumeration definitions for the Utility Billing database schema.

This module defines all enum.StrEnum classes used throughout the database
schema, following the requirements in docs/04 §4. Each enum is implemented as
a Python StrEnum and a SQLAlchemy Enum column for database validation.

The enum values are the contract and must match the values specified in
`docs/04` and `contracts/schema.md`.
"""

from enum import Enum


class TenancyStatus(str, Enum):
    """Status of a tenancy — draft, active, or closed."""

    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class RecordCategory(str, Enum):
    """Persisted transaction types — tenant_payment or utility_bill_payment only."""

    TENANT_PAYMENT = "tenant_payment"
    UTILITY_BILL_PAYMENT = "utility_bill_payment"


class Direction(str, Enum):
    """Transaction direction — credit or debit."""

    CREDIT = "credit"
    DEBIT = "debit"


class MatchingStatus(str, Enum):
    """How a tenant payment matches to a utility bill payment.

    Unmatched, ambiguous, matched (system), manually_matched (admin), or not_applicable.
    """

    UNMATCHED = "unmatched"
    AMBIGUOUS = "ambiguous"
    MATCHED = "matched"
    MANUALLY_MATCHED = "manually_matched"
    NOT_APPLICABLE = "not_applicable"


class AllocationType(str, Enum):
    """How a tenant payment is allocated to a bill."""

    AUTOMATIC = "automatic"
    MANUAL = "manual"
    CORRECTION = "correction"
    REVERSAL = "reversal"


class AdvanceMovementType(str, Enum):
    """Type of advance movement — created (credit), applied (to bill), or reversed."""

    CREATED = "created"
    APPLIED = "applied"
    REVERSED = "reversed"


class ImportBatchStatus(str, Enum):
    """Processing status of an import batch — parsing, staged, duplicate_statement, etc."""

    PARSING = "parsing"
    STAGED = "staged"
    DUPLICATE_STATEMENT = "duplicate_statement"
    TOTALS_MISMATCH = "totals_mismatch"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class TotalsStatus(str, Enum):
    """Status of control totals validation — valid, mismatch, or missing."""

    VALID = "valid"
    MISMATCH = "mismatch"
    MISSING = "missing"
