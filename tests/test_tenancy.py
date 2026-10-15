"""US2: Property, room, tenancy, tenant access (docs/04 §6.1–§6.3;
FR-002, FR-008, FR-011, FR-012, FR-019, FR-020)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.src.models import (
    Organization,
    Property,
    Room,
    SenderAlias,
    Tenancy,
    Tenant,
    TenantAccessCredential,
    TenantSession,
)
from backend.src.models.base import UTCDateTime

SESSION_VALIDITY_PREDICATE = """
SELECT ts.id
FROM tenant_session ts
JOIN tenant_access_credential c ON c.id = ts.credential_id
WHERE ts.revoked_at IS NULL
  AND ts.expires_at > :now
  AND ts.credential_version = c.credential_version
  AND c.is_active = true
"""


def _make_organization(session: Session) -> Organization:
    organization = Organization(name="Acme Properties")
    session.add(organization)
    session.commit()
    return organization


def _make_property(session: Session, organization: Organization) -> Property:
    prop = Property(organization_id=organization.id, name="Block A")
    session.add(prop)
    session.commit()
    return prop


def _make_room(session: Session, prop: Property, label: str = "Room 1") -> Room:
    room = Room(property_id=prop.id, label=label)
    session.add(room)
    session.commit()
    return room


def _make_tenancy(
    session: Session,
    organization: Organization,
    room: Room,
    status: str = "active",
) -> Tenancy:
    tenancy = Tenancy(
        organization_id=organization.id,
        room_id=room.id,
        status=status,
        start_date=datetime(2026, 1, 1).date(),
    )
    session.add(tenancy)
    session.commit()
    return tenancy


def test_property_room_tenancy_tenant_sender_alias_access_tables_exist(db_engine):
    inspector = sa.inspect(db_engine)
    expected = {
        "property",
        "room",
        "tenancy",
        "tenant",
        "sender_alias",
        "tenant_access_credential",
        "tenant_session",
    }
    assert expected <= set(inspector.get_table_names())


def test_one_active_tenancy_per_room_partial_unique_index(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        room = _make_room(session, _make_property(session, organization))
        _make_tenancy(session, organization, room, status="active")

        session.add(
            Tenancy(
                organization_id=organization.id,
                room_id=room.id,
                status="active",
                start_date=datetime(2026, 2, 1).date(),
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_closed_tenancy_does_not_block_new_active_tenancy(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        room = _make_room(session, _make_property(session, organization))
        first = _make_tenancy(session, organization, room, status="active")

        first.status = "closed"
        session.commit()

        second = _make_tenancy(session, organization, room, status="active")
        assert second.id != first.id
        assert second.status == "active"


def test_sender_alias_unique_per_tenancy_normalized_name(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        prop = _make_property(session, organization)
        room_one = _make_room(session, prop, label="Room 1")
        room_two = _make_room(session, prop, label="Room 2")
        tenancy_one = _make_tenancy(session, organization, room_one)
        tenancy_two = _make_tenancy(session, organization, room_two)

        session.add(
            SenderAlias(
                organization_id=organization.id,
                tenancy_id=tenancy_one.id,
                display_name="John Okafor",
                normalized_name="JOHN OKAFOR",
            )
        )
        session.commit()

        session.add(
            SenderAlias(
                organization_id=organization.id,
                tenancy_id=tenancy_one.id,
                display_name="john okafor",
                normalized_name="JOHN OKAFOR",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()

        # Same normalized name under a different tenancy is allowed.
        session.add(
            SenderAlias(
                organization_id=organization.id,
                tenancy_id=tenancy_two.id,
                display_name="John Okafor",
                normalized_name="JOHN OKAFOR",
            )
        )
        session.commit()


def test_tenant_access_credential_tenancy_id_unique(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        room = _make_room(session, _make_property(session, organization))
        tenancy = _make_tenancy(session, organization, room)

        session.add(
            TenantAccessCredential(
                tenancy_id=tenancy.id,
                access_code_hash="hash-one",
            )
        )
        session.commit()

        session.add(
            TenantAccessCredential(
                tenancy_id=tenancy.id,
                access_code_hash="hash-two",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_access_code_hash_not_globally_unique_across_tenancies(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        prop = _make_property(session, organization)
        tenancy_one = _make_tenancy(session, organization, _make_room(session, prop, "Room 1"))
        tenancy_two = _make_tenancy(session, organization, _make_room(session, prop, "Room 2"))

        session.add(
            TenantAccessCredential(
                tenancy_id=tenancy_one.id,
                access_code_hash="shared-hash",
            )
        )
        session.add(
            TenantAccessCredential(
                tenancy_id=tenancy_two.id,
                access_code_hash="shared-hash",
            )
        )
        session.commit()

        assert session.query(TenantAccessCredential).count() == 2


def test_tenant_session_validity_predicate_from_columns(db_engine):
    now = datetime.now(timezone.utc)

    with Session(db_engine) as session:
        organization = _make_organization(session)
        prop = _make_property(session, organization)
        room = _make_room(session, prop)
        tenancy = _make_tenancy(session, organization, room)

        credential = TenantAccessCredential(
            tenancy_id=tenancy.id,
            access_code_hash="code-hash",
            credential_version=1,
            is_active=True,
        )
        session.add(credential)
        session.flush()

        valid_expires_at = now + timedelta(days=30)
        valid = TenantSession(
            credential_id=credential.id,
            credential_version=1,
            token_hash="token-valid",
            issued_at=now,
            expires_at=valid_expires_at,
        )
        revoked = TenantSession(
            credential_id=credential.id,
            credential_version=1,
            token_hash="token-revoked",
            issued_at=now,
            expires_at=now + timedelta(days=30),
            revoked_at=now,
        )
        expired = TenantSession(
            credential_id=credential.id,
            credential_version=1,
            token_hash="token-expired",
            issued_at=now - timedelta(days=60),
            expires_at=now - timedelta(days=1),
        )
        stale_version = TenantSession(
            credential_id=credential.id,
            credential_version=999,
            token_hash="token-stale",
            issued_at=now,
            expires_at=now + timedelta(days=30),
        )

        room_two = _make_room(session, prop, label="Room 2")
        tenancy_two = _make_tenancy(session, organization, room_two)
        inactive_credential = TenantAccessCredential(
            tenancy_id=tenancy_two.id,
            access_code_hash="code-hash-2",
            credential_version=1,
            is_active=False,
        )
        session.add(inactive_credential)
        session.flush()
        inactive_credential_session = TenantSession(
            credential_id=inactive_credential.id,
            credential_version=1,
            token_hash="token-inactive-credential",
            issued_at=now,
            expires_at=now + timedelta(days=30),
        )

        session.add_all([valid, revoked, expired, stale_version, inactive_credential_session])
        session.commit()

        query = sa.text(SESSION_VALIDITY_PREDICATE).bindparams(
            sa.bindparam("now", value=now, type_=UTCDateTime)
        )
        rows = session.execute(query).fetchall()
        found = {uuid.UUID(str(row[0])) for row in rows}
        assert found == {valid.id}

        # expires_at is fixed at issuance and never slides forward.
        session.refresh(valid)
        assert valid.expires_at == valid_expires_at


def test_tenancy_status_check_rejects_unknown_value(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        room = _make_room(session, _make_property(session, organization))

        session.add(
            Tenancy(
                organization_id=organization.id,
                room_id=room.id,
                status="bogus",
                start_date=datetime(2026, 1, 1).date(),
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()
