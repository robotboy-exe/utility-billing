"""US7: Seed data (docs/04 §12; FR-024)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.src.models import (
    AdminUser,
    BillingConfig,
    ImportChannelCategoryMapping,
    ImportProfile,
    Organization,
    PortalSetting,
    UtilityProvider,
)
from backend.src.seed import DEFAULT_PORTAL_SETTINGS, PAYVICE_AVANTUS_MAPPINGS, seed

SEED_KWARGS = {
    "org_name": "Acme Properties",
    "admin_email": "admin@example.com",
    "admin_password_hash": "hashed-password",
    "standard_amount_minor": 50000,
}


def test_seed_creates_exactly_docs04_reference_rows(db_engine):
    with Session(db_engine) as session:
        seed(session, **SEED_KWARGS)

        assert session.query(Organization).count() == 1
        assert session.query(AdminUser).count() == 1
        assert session.query(ImportProfile).count() == 1
        assert session.query(ImportChannelCategoryMapping).count() == len(
            PAYVICE_AVANTUS_MAPPINGS
        )
        assert session.query(UtilityProvider).count() == 1
        assert session.query(BillingConfig).count() == 1
        assert session.query(PortalSetting).count() == len(DEFAULT_PORTAL_SETTINGS)

        mapping = (
            session.query(ImportChannelCategoryMapping)
            .filter_by(channel="FUNDING", direction="credit")
            .one()
        )
        assert mapping.category == "tenant_payment"
        commission = (
            session.query(ImportChannelCategoryMapping)
            .filter_by(channel="COMMISSION")
            .one()
        )
        assert commission.category == "excluded"


def test_seed_is_idempotent(db_engine):
    with Session(db_engine) as session:
        seed(session, **SEED_KWARGS)
        first = {
            "organization": session.query(Organization).count(),
            "admin_user": session.query(AdminUser).count(),
            "import_profile": session.query(ImportProfile).count(),
            "import_channel_category_mapping": session.query(
                ImportChannelCategoryMapping
            ).count(),
            "utility_provider": session.query(UtilityProvider).count(),
            "billing_config": session.query(BillingConfig).count(),
            "portal_setting": session.query(PortalSetting).count(),
        }

        seed(session, **SEED_KWARGS)
        second = {
            "organization": session.query(Organization).count(),
            "admin_user": session.query(AdminUser).count(),
            "import_profile": session.query(ImportProfile).count(),
            "import_channel_category_mapping": session.query(
                ImportChannelCategoryMapping
            ).count(),
            "utility_provider": session.query(UtilityProvider).count(),
            "billing_config": session.query(BillingConfig).count(),
            "portal_setting": session.query(PortalSetting).count(),
        }
        assert first == second


def test_seeded_global_rows_have_null_organization_id(db_engine):
    with Session(db_engine) as session:
        seed(session, **SEED_KWARGS)
        profile = session.query(ImportProfile).one()
        provider = session.query(UtilityProvider).one()
        assert profile.organization_id is None
        assert provider.organization_id is None


def test_default_billing_config_is_org_wide(db_engine):
    with Session(db_engine) as session:
        seed(session, **SEED_KWARGS)
        config = session.query(BillingConfig).one()
        assert config.property_id is None
        assert config.standard_amount_minor == SEED_KWARGS["standard_amount_minor"]
