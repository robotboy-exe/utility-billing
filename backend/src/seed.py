"""US7: Idempotent seed for the docs/04 §12 reference rows (D-2, FR-024).

Deployment values come from the environment (``ORG_NAME``, ``ADMIN_EMAIL``,
``ADMIN_PASSWORD_HASH``, ``STANDARD_AMOUNT_MINOR``); the seed fails loudly when
any is missing. Tests call :func:`seed` directly with fixed values.
"""

from __future__ import annotations

import os

from sqlalchemy.orm import Session

from .db import create_db_engine, create_session_factory
from .models import (
    AdminUser,
    BillingConfig,
    ImportChannelCategoryMapping,
    ImportProfile,
    Organization,
    PortalSetting,
    UtilityProvider,
)

REQUIRED_ENV_VARS = (
    "ORG_NAME",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD_HASH",
    "STANDARD_AMOUNT_MINOR",
)

PAYVICE_AVANTUS_CODE = "PAYVICE_AVANTUS"
BEDC_CODE = "BEDC"

# docs/06 §11.1 channel/direction -> category mapping.
PAYVICE_AVANTUS_MAPPINGS: tuple[tuple[str, str | None, str], ...] = (
    ("FUNDING", "credit", "tenant_payment"),
    ("BEDC", "debit", "utility_bill_payment"),
    ("TRANSFER", "debit", "ignored"),
    ("CHARGE", "debit", "ignored"),
    ("VAT", "debit", "ignored"),
    ("COMMISSION", None, "excluded"),
)

# docs/04 §12 default portal settings (organization scope).
DEFAULT_PORTAL_SETTINGS: tuple[tuple[str, str], ...] = (
    ("default_view", "property"),
    ("allow_other_room_amount_due", "false"),
    ("allow_property_utility_spend", "true"),
    ("allow_other_room_tenant_names", "false"),
)


def seed(
    session: Session,
    *,
    org_name: str,
    admin_email: str,
    admin_password_hash: str,
    standard_amount_minor: int,
) -> Organization:
    """Insert the docs/04 §12 rows idempotently and return the organization."""
    organization = session.query(Organization).first()
    if organization is None:
        organization = Organization(name=org_name)
        session.add(organization)
        session.flush()

    admin = session.query(AdminUser).filter_by(email=admin_email).one_or_none()
    if admin is None:
        session.add(
            AdminUser(
                organization_id=organization.id,
                email=admin_email,
                password_hash=admin_password_hash,
            )
        )

    profile = (
        session.query(ImportProfile)
        .filter_by(code=PAYVICE_AVANTUS_CODE)
        .one_or_none()
    )
    if profile is None:
        profile = ImportProfile(
            organization_id=None,
            code=PAYVICE_AVANTUS_CODE,
            display_name="Payvice Avantus",
            source_type="pdf",
        )
        session.add(profile)
        session.flush()

    for channel, direction, category in PAYVICE_AVANTUS_MAPPINGS:
        exists = (
            session.query(ImportChannelCategoryMapping)
            .filter_by(
                import_profile_id=profile.id,
                channel=channel,
                direction=direction,
            )
            .first()
        )
        if exists is None:
            session.add(
                ImportChannelCategoryMapping(
                    import_profile_id=profile.id,
                    channel=channel,
                    direction=direction,
                    category=category,
                )
            )

    provider = (
        session.query(UtilityProvider).filter_by(code=BEDC_CODE).one_or_none()
    )
    if provider is None:
        session.add(
            UtilityProvider(
                organization_id=None,
                code=BEDC_CODE,
                display_name="BEDC",
                channel_signature="BEDC",
                reference_label="Meter number",
            )
        )

    config = (
        session.query(BillingConfig)
        .filter_by(organization_id=organization.id, property_id=None)
        .one_or_none()
    )
    if config is None:
        session.add(
            BillingConfig(
                organization_id=organization.id,
                standard_amount_minor=standard_amount_minor,
            )
        )

    for setting_key, setting_value in DEFAULT_PORTAL_SETTINGS:
        exists = (
            session.query(PortalSetting)
            .filter_by(
                scope_type="organization",
                scope_id=organization.id,
                setting_key=setting_key,
            )
            .first()
        )
        if exists is None:
            session.add(
                PortalSetting(
                    scope_type="organization",
                    scope_id=organization.id,
                    setting_key=setting_key,
                    setting_value=setting_value,
                )
            )

    session.commit()
    return organization


def main() -> None:
    values = {name: os.environ.get(name) for name in REQUIRED_ENV_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise SystemExit(
            "missing required environment variables: " + ", ".join(missing)
        )

    engine = create_db_engine()
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed(
            session,
            org_name=values["ORG_NAME"],
            admin_email=values["ADMIN_EMAIL"],
            admin_password_hash=values["ADMIN_PASSWORD_HASH"],
            standard_amount_minor=int(values["STANDARD_AMOUNT_MINOR"]),
        )


if __name__ == "__main__":
    main()
