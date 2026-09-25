"""Tests for User Story 1 - Structural & Identity Foundation uniqueness constraints.

This module implements the uniqueness and constraint tests required for User Story 1.

Test file: tests/test_uniqueness.py
Task: T008 [P] [US1] Uniqueness/constraint tests in tests/test_uniqueness.py

Tests cover:
- active tenancy per room (`UNIQUE (room_id) WHERE status='active'`)
- sender_alias (`UNIQUE (tenancy_id, normalized_name)`)
- UUID PK + org scoping presence on org-hierarchy tables

All tests must FAIL before implementation is started (Test-Driven Development).
"""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from backend.src.db import get_session
from backend.src.models.org import Organization, Property, Room
from backend.src.models.tenancy import Tenancy, Tenant, SenderAlias
from backend.src.models.identity import AdminUser, TenantAccessCredential, TenantSession


@pytest.fixture
def db_session():
    """Provide a database session for testing."""
    session = next(get_session())
    try:
        yield session
    finally:
        session.close()


def test_active_tenancy_per_room_uniqueness(db_session):
    """
    Test: active tenancy per room (`UNIQUE (room_id) WHERE status='active'`)

    GIVEN: A room and an active tenancy for that room
    WHEN: Attempt to create another active tenancy for the same room
    THEN: Should raise an IntegrityError due to uniqueness constraint
    """
    # Create org
    org = Organization(
        id=uuid.uuid4(),
        name="Test Org",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(org)
    db_session.commit()

    # Create property and room
    property = Property(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Test Property",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(property)
    db_session.commit()

    room = Room(
        id=uuid.uuid4(),
        property_id=property.id,
        label="Room 101",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(room)
    db_session.commit()

    # Create first active tenancy
    tenancy1 = Tenancy(
        id=uuid.uuid4(),
        organization_id=org.id,
        room_id=room.id,
        status="active",
        start_date=datetime.now(timezone.utc).date(),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenancy1)
    db_session.commit()

    # Attempt to create second active tenancy for same room
    tenancy2 = Tenancy(
        id=uuid.uuid4(),
        organization_id=org.id,
        room_id=room.id,
        status="active",
        start_date=datetime.now(timezone.utc).date(),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenancy2)

    # Should raise IntegrityError due to unique constraint
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()

    # Rollback the failed transaction
    db_session.rollback()

    # Verify error message indicates constraint violation
    assert "UNIQUE constraint failed" in str(exc_info.value) or "UNIQUE" in str(exc_info.value).upper()


def test_sender_alias_uniqueness_per_tenancy(db_session):
    """
    Test: sender_alias (`UNIQUE (tenancy_id, normalized_name)`)

    GIVEN: A tenancy and a sender alias with normalized name "Acme Bank"
    WHEN: Attempt to create another sender alias with same tenancy_id and normalized_name
    THEN: Should raise an IntegrityError due to uniqueness constraint
    """
    # Create org
    org = Organization(
        id=uuid.uuid4(),
        name="Test Org",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(org)
    db_session.commit()

    # Create property and room
    property = Property(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Test Property",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(property)
    db_session.commit()

    room = Room(
        id=uuid.uuid4(),
        property_id=property.id,
        label="Room 101",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(room)
    db_session.commit()

    # Create tenancy
    tenancy = Tenancy(
        id=uuid.uuid4(),
        organization_id=org.id,
        room_id=room.id,
        status="active",
        start_date=datetime.now(timezone.utc).date(),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenancy)
    db_session.commit()

    # Create first sender alias
    sender_alias1 = SenderAlias(
        id=uuid.uuid4(),
        organization_id=org.id,
        tenancy_id=tenancy.id,
        display_name="Acme Bank",
        normalized_name="acme-bank",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sender_alias1)
    db_session.commit()

    # Attempt to create second sender alias with same tenancy_id and normalized_name
    sender_alias2 = SenderAlias(
        id=uuid.uuid4(),
        organization_id=org.id,
        tenancy_id=tenancy.id,
        display_name="Acme Bank Inc.",
        normalized_name="acme-bank",  # Same normalized_name as first
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(sender_alias2)

    # Should raise IntegrityError due to unique constraint
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()

    # Rollback the failed transaction
    db_session.rollback()

    # Verify error message indicates constraint violation
    assert "UNIQUE constraint failed" in str(exc_info.value) or "UNIQUE" in str(exc_info.value).upper()


def test_organization_uuid_primary_key(db_session):
    """
    Test: UUID PK presence on org-hierarchy tables

    GIVEN: An organization record
    WHEN: Query for the organization
    THEN: Should successfully retrieve the organization using UUID
    """
    # Create organization
    org = Organization(
        id=uuid.uuid4(),
        name="Test Org",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(org)
    db_session.commit()

    # Retrieve organization by UUID
    retrieved_org = db_session.query(Organization).filter_by(id=org.id).first()

    # Should successfully retrieve the organization
    assert retrieved_org is not None
    assert retrieved_org.id == org.id
    assert retrieved_org.name == "Test Org"


def test_property_org_scoping(db_session):
    """
    Test: org scoping: property.organization_id FK NOT NULL

    GIVEN: An organization
    WHEN: Create a property without organization_id
    THEN: Should raise an error or fail validation
    """
    # Create property without organization_id (should fail)
    property = Property(
        id=uuid.uuid4(),
        organization_id=None,  # Missing organization_id
        name="Test Property",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(property)

    # Attempt to commit should fail due to NOT NULL constraint
    with pytest.raises(Exception) as exc_info:
        db_session.commit()

    # Rollback
    db_session.rollback()

    # Verify error
    assert exc_info is not None