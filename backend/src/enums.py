"""docs/04-database.md §4 enumeration value sets (TEXT + CHECK behavior, R-1).

The values are the contract. Every enumeration column is TEXT with a CHECK
constraint listing its allowed values, on both engines.
"""

from __future__ import annotations

import sqlalchemy as sa

TENANCY_STATUS = ("draft", "active", "closed")
RECORD_CATEGORY = ("tenant_payment", "utility_bill_payment")
DIRECTION = ("credit", "debit")
MATCHING_STATUS = (
    "unmatched",
    "ambiguous",
    "matched",
    "manually_matched",
    "not_applicable",
)
ALLOCATION_TYPE = ("automatic", "manual", "correction", "reversal")
ADVANCE_MOVEMENT_TYPE = ("created", "applied", "reversed")
IMPORT_BATCH_STATUS = (
    "parsing",
    "staged",
    "duplicate_statement",
    "totals_mismatch",
    "confirmed",
    "rejected",
    "completed",
    "failed",
)
TOTALS_STATUS = ("valid", "mismatch", "missing")

# Inline value sets from docs/04 §6 (research.md R-1).
BILLING_OVERRIDE_DECISION = ("bill", "skip")
BILL_ADJUSTMENT_TYPE = ("rate_change", "write_off")
STAGED_ROW_PARSE_STATUS = ("valid", "duplicate", "invalid", "unrecognized")
AUDIT_ACTOR_TYPE = ("admin", "system", "tenant_session")
CHANNEL_CATEGORY = (
    "tenant_payment",
    "utility_bill_payment",
    "ignored",
    "excluded",
    "unrecognized",
)


def enum_check(
    column: str,
    values: tuple[str, ...],
    *,
    name: str | None = None,
) -> sa.CheckConstraint:
    """TEXT column CHECK constraint listing the allowed values (R-1)."""
    allowed = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(
        f"{column} IN ({allowed})",
        name=name or f"ck_{column}_values",
    )
