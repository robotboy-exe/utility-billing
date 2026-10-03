"""Tests for the 04-database 0.5.0 schema deltas (User Story 1 subset).

Covers the brief's requested tests:
- ``organization.timezone`` defaults to ``Africa/Lagos`` and an invalid IANA name
  is rejected in application code (D1).
- a ``tenant_login_attempt`` row can be recorded with and without a tenancy (D2).
- two tenancies can hold credentials with the same ``access_code_hash`` value —
  there is no global uniqueness over the hash (D2).
- ``tenant_session.expires_at`` stays fixed after the session is used (D2).

These tests build their own fresh in-memory SQLite database and do **not** depend
on the dev-file database used by the pre-existing US1 tests, so they cannot be
contaminated by leaked rows across runs.

Test file: tests/test_schema_deltas.py
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.src.models.base import Base
from backend.src.models.org import (
    Organization,
    Property,
    Room,
    is_valid_iana_timezone,
)
from backend.src.models.tenancy import Tenancy
from backend.src.models.identity import (
    TenantAccessCredential,
    TenantLoginAttempt,
    TenantSession,
)


@pytest.fixture(scope="module")
def engine():
    """A fresh in-memory SQLite engine with the full US1 metadata applied."""
    eng = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    """A transactional session over the fresh in-memory database."""
    with engine.connect() as connection:
        trans = connection.begin()
        session = Session(bind=connection)
        yield session
        trans.rollback()
        session.close()


@pytest.fixture
def org(db_session):
    organization = Organization(name="Test Org")
    db_session.add(organization)
    db_session.commit()
    return organization


def _make_room(db_session, organization):
    prop = Property(
        id=uuid.uuid4(),
        organization_id=organization.id,
        name="Test Property",
    )
    room = Room(id=uuid.uuid4(), property_id=prop.id, label="Room 101")
    db_session.add_all([prop, room])
    db_session.commit()
    return room


def _make_tenancy(db_session, organization, room, status="active"):
    tenancy = Tenancy(
        id=uuid.uuid4(),
        organization_id=organization.id,
        room_id=room.id,
        status=status,
        start_date=datetime.now(timezone.utc).date(),
    )
    db_session.add(tenancy)
    db_session.commit()
    return tenancy


# --- D1: organization.timezone --------------------------------------------


def test_org_timezone_default_applies(db_session, org):
    """The default ``Africa/Lagos`` applies when the column is not set."""
    assert org.timezone == "Africa/Lagos"
    # A fresh read from the DB still carries the default.
    db_session.expire_all()
    fetched = db_session.get(Organization, org.id)
    assert fetched.timezone == "Africa/Lagos"


def test_org_explicit_timezone_round_trips(db_session, org):
    org.timezone = "Asia/Tokyo"
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(Organization, org.id).timezone == "Asia/Tokyo"


def test_invalid_iana_timezone_rejected_in_app_code():
    """Invalid IANA names are rejected by the application validation."""
    assert not is_valid_iana_timezone("Not/AZone")
    assert not is_valid_iana_timezone("Africa/Nowhere")
    assert not is_valid_iana_timezone("")
    assert is_valid_iana_timezone("Africa/Lagos")
    assert is_valid_iana_timezone("UTC")


def test_invalid_timezone_fails_flush(db_session):
    """Setting an invalid timezone is rejected at the application layer."""
    with pytest.raises(ValueError, match="invalid IANA timezone"):
        Organization(name="Bad TZ", timezone="Mars/Olympus")


def test_invalid_timezone_on_assignment_rejected(db_session, org):
    with pytest.raises(ValueError, match="invalid IANA timezone"):
        org.timezone = "Mars/Olympus"


# --- D2: tenant_login_attempt ----------------------------------------------


def test_login_attempt_recorded_without_tenancy(db_session, org):
    attempt = TenantLoginAttempt(
        organization_id=org.id,
        tenancy_id=None,
        source_ip="203.0.113.5",
        attempted_at=datetime.now(timezone.utc),
        succeeded=False,
    )
    db_session.add(attempt)
    db_session.commit()

    fetched = db_session.get(TenantLoginAttempt, attempt.id)
    assert fetched is not None
    assert fetched.organization_id == org.id
    assert fetched.tenancy_id is None
    assert fetched.source_ip == "203.0.113.5"
    assert fetched.succeeded is False


def test_login_attempt_recorded_with_tenancy(db_session, org):
    room = _make_room(db_session, org)
    tenancy = _make_tenancy(db_session, org, room)

    attempt = TenantLoginAttempt(
        organization_id=org.id,
        tenancy_id=tenancy.id,
        source_ip="203.0.113.9",
        attempted_at=datetime.now(timezone.utc),
        succeeded=True,
    )
    db_session.add(attempt)
    db_session.commit()

    fetched = db_session.get(TenantLoginAttempt, attempt.id)
    assert fetched.tenancy_id == tenancy.id
    assert fetched.succeeded is True


# --- D2: no global uniqueness over access_code_hash ------------------------


def test_two_tenancies_can_share_same_hash(db_session, org):
    """Two tenancies can hold credentials with the same hash value."""
    room1 = _make_room(db_session, org)
    room2 = _make_room(db_session, org)
    tenancy1 = _make_tenancy(db_session, org, room1)
    tenancy2 = _make_tenancy(db_session, org, room2)

    h = "same-hashed-code-for-two-tenancies"
    cred1 = TenantAccessCredential(
        tenancy_id=tenancy1.id,
        access_code_hash=h,
        credential_version=1,
        is_active=True,
    )
    cred2 = TenantAccessCredential(
        tenancy_id=tenancy2.id,
        access_code_hash=h,  # identical hash, different tenancy
        credential_version=1,
        is_active=True,
    )
    db_session.add_all([cred1, cred2])
    db_session.commit()  # no IntegrityError

    hashes = [
        db_session.get(TenantAccessCredential, cred1.id).access_code_hash,
        db_session.get(TenantAccessCredential, cred2.id).access_code_hash,
    ]
    assert hashes == [h, h]


# --- D2: tenant_session.expires_at is fixed at issuance ---------------------


def test_session_expires_at_fixed_after_use(db_session, org):
    room = _make_room(db_session, org)
    tenancy = _make_tenancy(db_session, org, room)
    credential = TenantAccessCredential(
        tenancy_id=tenancy.id,
        access_code_hash="hashed-code",
        credential_version=1,
        is_active=True,
    )
    db_session.add(credential)
    db_session.commit()  # flush so credential.id is populated

    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    tenant_session = TenantSession(
        credential_id=credential.id,
        credential_version=1,
        token_hash="session-token-hash",
        device_info="Test Device",
        issued_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )
    db_session.add(tenant_session)
    db_session.commit()

    # A fixed reference so the assertion is not affected by test execution time.
    original_expires_at = expires_at

    # "Using" the session (evaluating the validity rule, checking fields) must
    # not move expires_at forward.
    _ = tenant_session.is_valid
    _ = tenant_session.credential_version == credential.credential_version
    _ = tenant_session.token_hash
    db_session.commit()

    # Same stored instant after the round-trip through SQLite (naive on reload).
    reloaded = tenant_session.expires_at
    if reloaded.tzinfo is None:
        reloaded = reloaded.replace(tzinfo=timezone.utc)
    assert reloaded == original_expires_at
