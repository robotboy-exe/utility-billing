"""Models package: exports the declarative Base and registers model modules.

Model modules for the current pass (User Story 1: org, tenancy, identity) are
imported here so that ``Base.metadata`` is fully populated for ``create_all`` /
Alembic autogenerate. Later-story modules (billing_config, billing_ledger,
ledger, utility, ingestion, settings) are added by their tasks as they land —
their tables (e.g. transaction, import_batch) do not exist yet, so importing
them here would break metadata construction.
"""

from .base import (
    Base,
    IdCreatedAtMixin,
    OrgScopedMixin,
    UpdatedAtMixin,
    IdCreatedAtOrgScopedUpdatedAtMixin,
    IdCreatedAtOrgScopedMixin,
    IdCreatedAtUpdatedAtMixin,
)

from . import org  # noqa: F401  (registers Organization, Property, Room)
from . import tenancy  # noqa: F401  (registers Tenancy, Tenant, SenderAlias)
from . import identity  # noqa: F401  (registers AdminUser, TenantAccessCredential, TenantSession)

__all__ = [
    "Base",
    "IdCreatedAtMixin",
    "OrgScopedMixin",
    "UpdatedAtMixin",
    "IdCreatedAtOrgScopedUpdatedAtMixin",
    "IdCreatedAtOrgScopedMixin",
    "IdCreatedAtUpdatedAtMixin",
]