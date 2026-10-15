"""US1: Organization and admin identity (docs/04 §6.1, §6.2; FR-001, FR-008, FR-011, FR-026)."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.src.models import AdminUser, Organization


def _make_organization(session: Session, name: str = "Acme Properties") -> Organization:
    organization = Organization(name=name)
    session.add(organization)
    session.commit()
    return organization


def test_organization_and_admin_user_exist_with_uuid_pk(db_engine):
    inspector = sa.inspect(db_engine)
    assert {"organization", "admin_user"} <= set(inspector.get_table_names())
    for table in ("organization", "admin_user"):
        pk = inspector.get_pk_constraint(table)
        assert pk["constrained_columns"] == ["id"]

    with Session(db_engine) as session:
        organization = _make_organization(session)
        admin = AdminUser(
            organization_id=organization.id,
            email="admin@example.com",
            password_hash="not-plaintext",
        )
        session.add(admin)
        session.commit()
        assert isinstance(organization.id, uuid.UUID)
        assert isinstance(admin.id, uuid.UUID)


def test_admin_user_email_unique_rejects_duplicate(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        session.add(
            AdminUser(
                organization_id=organization.id,
                email="dup@example.com",
                password_hash="hash-1",
            )
        )
        session.commit()

        session.add(
            AdminUser(
                organization_id=organization.id,
                email="dup@example.com",
                password_hash="hash-2",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_admin_user_organization_id_fk_not_null_rejects_orphan(db_engine):
    with Session(db_engine) as session:
        session.add(
            AdminUser(
                organization_id=uuid.uuid4(),
                email="orphan@example.com",
                password_hash="hash",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            AdminUser(
                organization_id=None,  # type: ignore[arg-type]
                email="null-org@example.com",
                password_hash="hash",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_organization_timezone_defaults_to_africa_lagos(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        session.refresh(organization)
        assert organization.timezone == "Africa/Lagos"


def test_organization_timezone_rejects_invalid_iana_at_model_layer(db_engine):
    with pytest.raises(ValueError):
        Organization(name="Bad Zone", timezone="Not/ARealZone")

    valid = Organization(name="Good Zone", timezone="Africa/Lagos")
    assert valid.timezone == "Africa/Lagos"


def test_identity_tables_created_at_and_updated_at_conventions(db_engine):
    inspector = sa.inspect(db_engine)
    for table in ("organization", "admin_user"):
        columns = {column["name"]: column for column in inspector.get_columns(table)}
        assert "created_at" in columns
        assert "updated_at" in columns
        assert columns["created_at"]["nullable"] is False

    with Session(db_engine) as session:
        organization = _make_organization(session)
        admin = AdminUser(
            organization_id=organization.id,
            email="timestamps@example.com",
            password_hash="hash",
        )
        session.add(admin)
        session.commit()

        assert organization.created_at is not None
        assert organization.updated_at is not None
        assert admin.created_at is not None
        assert admin.updated_at is not None
