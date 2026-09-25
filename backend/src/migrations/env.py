"""
Alembic environment configuration for the Utility Billing backend.

This module configures the Alembic environment for managing database migrations
with support for both PostgreSQL (production) and SQLite (development).
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import text

from alembic import context
from alembic.environment import EnvironmentContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from alembic.script.base import _get_revisions

# Add the backend.src directory to the Python path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Load environment variables
from backend.src.db import DATABASE_URL

# Configure logging
fileConfig(context.config.config_file_name)
logger = context.logger.getChild("alembic")

# Create declarative base for models
from backend.src.models import Base

# Set the target metadata for autogenerate
metadata = Base.metadata

# Import all models to ensure they are registered with the metadata
from backend.src.models.base import (
    IdCreatedAtMixin,
    OrgScopedMixin,
    UpdatedAtMixin,
    IdCreatedAtOrgScopedUpdatedAtMixin,
    IdCreatedAtOrgScopedMixin,
    IdCreatedAtUpdatedAtMixin,
)
from backend.src.models.org import Organization, Property, Room
from backend.src.models.tenancy import Tenancy, Tenant, SenderAlias
from backend.src.models.identity import AdminUser, TenantAccessCredential, TenantSession
from backend.src.models.billing_config import BillingConfig, BillingOverride, StandardAmountChange
from backend.src.models.billing_ledger import MonthlyBill, PaymentAllocation, BillAdjustment
from backend.src.models.ledger import Transaction, AdvanceMovement
from backend.src.models.utility import UtilityProvider, UtilityBillPayment
from backend.src.models.ingestion import ImportProfile, ImportChannelCategoryMapping, ImportBatch, StagedImportRow
from backend.src.models.settings import PortalSetting, AuditLog

# Define custom import path for autogenerate
import backend.src.models as models_module


def include_object(object, name, type_, reflected, compare_to):
    """
    Custom filter for which objects to include in autogenerate.

    This is used to exclude certain objects from auto-migration generation.
    """
    if type_ == "table":
        # Exclude temporary/test tables
        if name.startswith("test_") or name.startswith("tmp_"):
            return False
    return True


def pre migrate(context, revision, directives):
    pass


def post migrate(context, revision, directives):
    pass


def get_env_options():
    return {
        "compare_type": True,
        "compare_server_default": True,
    }


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        **get_env_options(),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    # Configure connection
    config = context.config.get_section(context.config.config_ini_section, {})
    config["sqlalchemy.url"] = DATABASE_URL

    # Create engine
    connectable = engine_from_config(
        config,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Establish connection and run migrations
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
