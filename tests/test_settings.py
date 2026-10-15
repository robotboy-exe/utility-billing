"""US5: Settings and visibility (docs/04 §6.8; FR-005, FR-012, FR-019)."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.src.models import PortalSetting


def _make_setting(session: Session, **overrides) -> PortalSetting:
    values = {
        "scope_type": "organization",
        "scope_id": uuid.uuid4(),
        "setting_key": "default_view",
        "setting_value": "property",
    }
    values.update(overrides)
    setting = PortalSetting(**values)
    session.add(setting)
    session.commit()
    return setting


def test_portal_setting_scope_unique(db_engine):
    with Session(db_engine) as session:
        scope_id = uuid.uuid4()
        _make_setting(session, scope_id=scope_id, setting_key="default_view")

        session.add(
            PortalSetting(
                scope_type="organization",
                scope_id=scope_id,
                setting_key="default_view",
                setting_value="room",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()

        # A different key under the same scope is allowed.
        _make_setting(session, scope_id=scope_id, setting_key="allow_property_utility_spend")
        # A different scope id under the same key is allowed.
        _make_setting(session, setting_key="default_view")


def test_portal_setting_scope_type_check(db_engine):
    with Session(db_engine) as session:
        session.add(
            PortalSetting(
                scope_type="tenant",
                scope_id=uuid.uuid4(),
                setting_key="default_view",
                setting_value="property",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()
