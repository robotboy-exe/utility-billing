"""baseline: full MVP schema (docs/04 §6, §9, §11)

Revision ID: 0001
Revises:
Create Date: 2026-10-15

Frozen snapshot: explicit table/index DDL that does not import the models, so
later model changes cannot alter what 0001 creates (29 tables). Generated from
the models by alembic autogenerate output, then written out literally. The
eight append-only triggers use the shared per-engine SQL function with the
table list written out here (D-8, R-5); ``op.create_table`` does not fire the
metadata ``after_create`` listener, so triggers are emitted exactly once.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.src.models.base import (
    immutable_trigger_create_sql,
    immutable_trigger_drop_sql,
)

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

IMMUTABLE_TABLES = [
    "transaction",
    "transaction_match",
    "payment_allocation",
    "advance_movement",
    "bill_adjustment",
    "standard_amount_change",
    "utility_bill_payment",
    "audit_log",
]


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), server_default=sa.text("'Africa/Lagos'"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "portal_setting",
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("setting_key", sa.Text(), nullable=False),
        sa.Column("setting_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope_type IN ('organization', 'property')", name="ck_scope_type_values"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_type", "scope_id", "setting_key"),
    )
    op.create_table(
        "admin_user",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "audit_log",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column(
            "metadata", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('admin', 'system', 'tenant_session')", name="ck_actor_type_values"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"], unique=False)
    op.create_index(
        "ix_audit_log_org_created", "audit_log", ["organization_id", "created_at"], unique=False
    )
    op.create_table(
        "import_profile",
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column(
            "detection_config",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "parse_config", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True
        ),
        sa.Column(
            "file_limits", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "property",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "utility_provider",
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("channel_signature", sa.Text(), nullable=False),
        sa.Column("reference_label", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "admin_login_attempt",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("admin_user_id", sa.Uuid(), nullable=True),
        sa.Column("source_ip", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["admin_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_login_attempt_admin_time",
        "admin_login_attempt",
        ["admin_user_id", "attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_login_attempt_ip_time",
        "admin_login_attempt",
        ["source_ip", "attempted_at"],
        unique=False,
    )
    op.create_table(
        "admin_session",
        sa.Column("admin_user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("device_info", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["admin_user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "billing_config",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("property_id", sa.Uuid(), nullable=True),
        sa.Column("standard_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["property.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_admin_id"],
            ["admin_user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_billing_config_org_wide",
        "billing_config",
        ["organization_id"],
        unique=True,
        sqlite_where=sa.text("property_id IS NULL"),
        postgresql_where=sa.text("property_id IS NULL"),
    )
    op.create_table(
        "import_batch",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("import_profile_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'parsing'"), nullable=False),
        sa.Column("statement_account_holder", sa.Text(), nullable=True),
        sa.Column("statement_account_number", sa.Text(), nullable=True),
        sa.Column("statement_start_date", sa.Date(), nullable=True),
        sa.Column("statement_end_date", sa.Date(), nullable=True),
        sa.Column("source_file_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("source_filename", sa.Text(), nullable=True),
        sa.Column("source_page_count", sa.Integer(), nullable=True),
        sa.Column("currency", sa.CHAR(length=3), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("totals_status", sa.Text(), nullable=True),
        sa.Column("statement_fingerprint", sa.Text(), nullable=True),
        sa.Column(
            "ignored_summary",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("tenant_payment_row_count", sa.Integer(), nullable=True),
        sa.Column("tenant_payment_total_minor", sa.BigInteger(), nullable=True),
        sa.Column("utility_payment_row_count", sa.Integer(), nullable=True),
        sa.Column("utility_payment_total_minor", sa.BigInteger(), nullable=True),
        sa.Column("duplicate_row_count", sa.Integer(), nullable=True),
        sa.Column("invalid_row_count", sa.Integer(), nullable=True),
        sa.Column("unrecognized_row_count", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('parsing', 'staged', 'duplicate_statement', 'totals_mismatch', 'confirmed', 'rejected', 'completed', 'failed')",
            name="ck_status_values",
        ),
        sa.CheckConstraint(
            "totals_status IN ('valid', 'mismatch', 'missing')", name="ck_totals_status_values"
        ),
        sa.ForeignKeyConstraint(
            ["import_profile_id"],
            ["import_profile.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_import_batch_statement_fingerprint",
        "import_batch",
        ["statement_fingerprint"],
        unique=False,
    )
    op.create_index(
        "uq_import_batch_fingerprint_confirmed",
        "import_batch",
        ["statement_fingerprint"],
        unique=True,
        sqlite_where=sa.text("status IN ('confirmed', 'completed')"),
        postgresql_where=sa.text("status IN ('confirmed', 'completed')"),
    )
    op.create_table(
        "import_channel_category_mapping",
        sa.Column("import_profile_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "category IN ('tenant_payment', 'utility_bill_payment', 'ignored', 'excluded', 'unrecognized')",
            name="ck_category_values",
        ),
        sa.CheckConstraint("direction IN ('credit', 'debit')", name="ck_direction_values"),
        sa.ForeignKeyConstraint(
            ["import_profile_id"],
            ["import_profile.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_channel_mapping_profile_channel_direction",
        "import_channel_category_mapping",
        ["import_profile_id", "channel", sa.text("COALESCE(direction, 'ANY')")],
        unique=True,
    )
    op.create_table(
        "room",
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["property.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "standard_amount_change",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("previous_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("new_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("auto_note", sa.Text(), nullable=False),
        sa.Column("custom_note", sa.Text(), nullable=True),
        sa.Column("admin_id", sa.Uuid(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admin_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tenancy",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'active', 'closed')", name="ck_status_values"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["room.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_tenancy_room_active",
        "tenancy",
        ["room_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "transaction",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
        sa.Column("record_category", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("transaction_time", sa.Time(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("description_raw", sa.Text(), nullable=False),
        sa.Column("counterparty_name", sa.Text(), nullable=True),
        sa.Column("counterparty_name_normalized", sa.Text(), nullable=True),
        sa.Column("counterparty_reference", sa.Text(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("duplicate_key", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("direction IN ('credit', 'debit')", name="ck_direction_values"),
        sa.CheckConstraint(
            "record_category IN ('tenant_payment', 'utility_bill_payment')",
            name="ck_record_category_values",
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batch.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("duplicate_key"),
    )
    op.create_index("ix_transaction_batch", "transaction", ["import_batch_id"], unique=False)
    op.create_index("ix_transaction_category", "transaction", ["record_category"], unique=False)
    op.create_index(
        "ix_transaction_org_date",
        "transaction",
        ["organization_id", "transaction_date"],
        unique=False,
    )
    op.create_table(
        "billing_override",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenancy_id", sa.Uuid(), nullable=False),
        sa.Column("billing_month", sa.Date(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("decision IN ('bill', 'skip')", name="ck_decision_values"),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"],
            ["admin_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenancy_id"],
            ["tenancy.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenancy_id", "billing_month"),
    )
    op.create_table(
        "monthly_bill",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenancy_id", sa.Uuid(), nullable=False),
        sa.Column("billing_month", sa.Date(), nullable=False),
        sa.Column("standard_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("final_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("is_adjusted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenancy_id"],
            ["tenancy.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenancy_id", "billing_month"),
    )
    op.create_index("ix_monthly_bill_month", "monthly_bill", ["billing_month"], unique=False)
    op.create_index(
        "ix_monthly_bill_org_month",
        "monthly_bill",
        ["organization_id", "billing_month"],
        unique=False,
    )
    op.create_table(
        "sender_alias",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenancy_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenancy_id"],
            ["tenancy.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenancy_id", "normalized_name"),
    )
    op.create_index(
        "ix_sender_alias_organization_id_normalized_name",
        "sender_alias",
        ["organization_id", "normalized_name"],
        unique=False,
    )
    op.create_table(
        "staged_import_row",
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("row_category", sa.Text(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("transaction_time", sa.Time(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("description_raw", sa.Text(), nullable=False),
        sa.Column("counterparty_name", sa.Text(), nullable=True),
        sa.Column("counterparty_reference", sa.Text(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("duplicate_key", sa.Text(), nullable=False),
        sa.Column("parse_status", sa.Text(), nullable=False),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("committed_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("direction IN ('credit', 'debit')", name="ck_direction_values"),
        sa.CheckConstraint(
            "parse_status IN ('valid', 'duplicate', 'invalid', 'unrecognized')",
            name="ck_parse_status_values",
        ),
        sa.CheckConstraint(
            "row_category IN ('tenant_payment', 'utility_bill_payment')",
            name="ck_row_category_values",
        ),
        sa.ForeignKeyConstraint(
            ["committed_transaction_id"],
            ["transaction.id"],
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batch.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_staged_import_row_batch", "staged_import_row", ["import_batch_id"], unique=False
    )
    op.create_table(
        "tenant",
        sa.Column("tenancy_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenancy_id"],
            ["tenancy.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tenant_access_credential",
        sa.Column("tenancy_id", sa.Uuid(), nullable=False),
        sa.Column("access_code_hash", sa.Text(), nullable=False),
        sa.Column("credential_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenancy_id"],
            ["tenancy.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenancy_id"),
    )
    op.create_table(
        "tenant_login_attempt",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenancy_id", sa.Uuid(), nullable=True),
        sa.Column("source_ip", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenancy_id"],
            ["tenancy.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tenant_login_attempt_ip_time",
        "tenant_login_attempt",
        ["source_ip", "attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_tenant_login_attempt_tenancy_time",
        "tenant_login_attempt",
        ["tenancy_id", "attempted_at"],
        unique=False,
    )
    op.create_table(
        "transaction_match",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("tenancy_id", sa.Uuid(), nullable=False),
        sa.Column("match_type", sa.Text(), nullable=False),
        sa.Column("reverses_match_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(match_type = 'reversal' AND reverses_match_id IS NOT NULL) OR (match_type <> 'reversal' AND reverses_match_id IS NULL)",
            name="ck_transaction_match_reversal_reference",
        ),
        sa.CheckConstraint(
            "match_type IN ('automatic', 'manual', 'reversal')", name="ck_match_type_values"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reverses_match_id"],
            ["transaction_match.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenancy_id"],
            ["tenancy.id"],
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transaction.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transaction_match_tenancy", "transaction_match", ["tenancy_id"], unique=False
    )
    op.create_index(
        "ix_transaction_match_transaction_created",
        "transaction_match",
        ["transaction_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_transaction_match_reverses",
        "transaction_match",
        ["reverses_match_id"],
        unique=True,
        sqlite_where=sa.text("reverses_match_id IS NOT NULL"),
        postgresql_where=sa.text("reverses_match_id IS NOT NULL"),
    )
    op.create_table(
        "utility_bill_payment",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("customer_reference", sa.Text(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("payment_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("spend_month", sa.Date(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batch.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["utility_provider.id"],
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transaction.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id"),
    )
    op.create_index(
        "ix_utility_spend_org_month",
        "utility_bill_payment",
        ["organization_id", "spend_month"],
        unique=False,
    )
    op.create_index(
        "ix_utility_spend_provider_month",
        "utility_bill_payment",
        ["provider_id", "spend_month"],
        unique=False,
    )
    op.create_table(
        "bill_adjustment",
        sa.Column("monthly_bill_id", sa.Uuid(), nullable=False),
        sa.Column("adjustment_type", sa.Text(), nullable=False),
        sa.Column("previous_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("new_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("public_note", sa.Text(), nullable=True),
        sa.Column("custom_note", sa.Text(), nullable=True),
        sa.Column("internal_reason", sa.Text(), nullable=True),
        sa.Column("admin_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "adjustment_type IN ('rate_change', 'write_off')", name="ck_adjustment_type_values"
        ),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admin_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["monthly_bill_id"],
            ["monthly_bill.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "payment_allocation",
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("monthly_bill_id", sa.Uuid(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column(
            "allocation_type", sa.Text(), server_default=sa.text("'automatic'"), nullable=False
        ),
        sa.Column("reverses_allocation_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "allocation_type IN ('automatic', 'manual', 'correction', 'reversal')",
            name="ck_allocation_type_values",
        ),
        sa.ForeignKeyConstraint(
            ["monthly_bill_id"],
            ["monthly_bill.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reverses_allocation_id"],
            ["payment_allocation.id"],
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transaction.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_allocation_bill", "payment_allocation", ["monthly_bill_id"], unique=False)
    op.create_index(
        "ix_allocation_transaction", "payment_allocation", ["transaction_id"], unique=False
    )
    op.create_table(
        "tenant_session",
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("device_info", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["tenant_access_credential.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "advance_movement",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("tenancy_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.Text(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("monthly_bill_id", sa.Uuid(), nullable=True),
        sa.Column("allocation_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "movement_type IN ('created', 'applied', 'reversed')", name="ck_movement_type_values"
        ),
        sa.ForeignKeyConstraint(
            ["allocation_id"],
            ["payment_allocation.id"],
        ),
        sa.ForeignKeyConstraint(
            ["monthly_bill_id"],
            ["monthly_bill.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenancy_id"],
            ["tenancy.id"],
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transaction.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_advance_tenancy_occurred",
        "advance_movement",
        ["tenancy_id", "occurred_at"],
        unique=False,
    )
    op.create_index("ix_advance_transaction", "advance_movement", ["transaction_id"], unique=False)
    # ### end Alembic commands ###

    bind = op.get_bind()
    for statement in immutable_trigger_create_sql(bind.dialect.name, tables=IMMUTABLE_TABLES):
        op.execute(statement)


def downgrade() -> None:
    bind = op.get_bind()
    for statement in immutable_trigger_drop_sql(bind.dialect.name):
        op.execute(statement)
    op.drop_table("advance_movement")
    op.drop_table("tenant_session")
    op.drop_table("payment_allocation")
    op.drop_table("bill_adjustment")
    op.drop_table("utility_bill_payment")
    op.drop_table("transaction_match")
    op.drop_table("tenant_login_attempt")
    op.drop_table("tenant_access_credential")
    op.drop_table("tenant")
    op.drop_table("staged_import_row")
    op.drop_table("sender_alias")
    op.drop_table("monthly_bill")
    op.drop_table("billing_override")
    op.drop_table("transaction")
    op.drop_table("tenancy")
    op.drop_table("standard_amount_change")
    op.drop_table("room")
    op.drop_table("import_channel_category_mapping")
    op.drop_table("import_batch")
    op.drop_table("billing_config")
    op.drop_table("admin_session")
    op.drop_table("admin_login_attempt")
    op.drop_table("utility_provider")
    op.drop_table("property")
    op.drop_table("import_profile")
    op.drop_table("audit_log")
    op.drop_table("admin_user")
    op.drop_table("portal_setting")
    op.drop_table("organization")
