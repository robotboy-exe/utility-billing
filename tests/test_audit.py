"""US6: Audit and security tables (docs/04 §6.9, §6.1; FR-006, FR-011, FR-012, FR-016)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.src.models import (
    AdminLoginAttempt,
    AdminSession,
    AdminUser,
    AuditLog,
    Organization,
    TenantLoginAttempt,
)
from backend.src.models.base import UTCDateTime


def _make_org(session: Session, name: str = "Acme Properties") -> Organization:
    org = Organization(name=name)
    session.add(org)
    session.commit()
    return org


def _make_admin(
    session: Session, org: Organization, email: str = "admin@example.com"
) -> AdminUser:
    admin = AdminUser(organization_id=org.id, email=email, password_hash="hashed")
    session.add(admin)
    session.commit()
    return admin


def test_audit_log_append_only_no_updated_at(db_engine):
    columns = {c["name"] for c in sa.inspect(db_engine).get_columns("audit_log")}
    assert "updated_at" not in columns

    with Session(db_engine) as session:
        org = _make_org(session)
        entry = AuditLog(
            organization_id=org.id,
            actor_type="admin",
            actor_id=None,
            action="bill.adjust",
            entity_type="monthly_bill",
            entity_id=None,
            audit_metadata={"reason": "rate change"},
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        assert entry.audit_metadata == {"reason": "rate change"}

        entry.action = "tenancy.close"
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            session.commit()
        session.rollback()

        session.delete(session.get(AuditLog, entry.id))
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            session.commit()
        session.rollback()


def test_audit_log_actor_type_check(db_engine):
    with Session(db_engine) as session:
        org = _make_org(session)
        session.add(
            AuditLog(
                organization_id=org.id,
                actor_type="robot",
                action="bill.adjust",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_admin_session_validity_predicate_and_scoping(db_engine):
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    with Session(db_engine) as session:
        org = _make_org(session)
        admin = _make_admin(session, org)
        session.add_all(
            [
                AdminSession(
                    admin_user_id=admin.id,
                    token_hash="hashed-token",
                    issued_at=now,
                    expires_at=now + timedelta(hours=1),
                ),
                AdminSession(
                    admin_user_id=admin.id,
                    token_hash="expired-token",
                    issued_at=now - timedelta(hours=2),
                    expires_at=now - timedelta(hours=1),
                ),
                AdminSession(
                    admin_user_id=admin.id,
                    token_hash="revoked-token",
                    issued_at=now,
                    expires_at=now + timedelta(hours=1),
                    revoked_at=now,
                ),
            ]
        )
        session.commit()

        valid = (
            session.query(AdminSession)
            .filter(
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at
                > sa.bindparam("now", value=now, type_=UTCDateTime),
            )
            .one()
        )
        assert valid.token_hash == "hashed-token"
        assert valid.expires_at == now + timedelta(hours=1)

        joined = sa.text(
            "SELECT COUNT(*) FROM admin_session s "
            "JOIN admin_user a ON a.id = s.admin_user_id "
            "WHERE s.revoked_at IS NULL AND s.expires_at > :now AND a.is_active = true"
        ).bindparams(sa.bindparam("now", value=now, type_=UTCDateTime))
        assert session.execute(joined).scalar() == 1

        admin.is_active = False
        session.commit()
        assert session.execute(joined).scalar() == 0

        fk_targets = {fk.column.table.name for fk in AdminSession.__table__.foreign_keys}
        assert fk_targets == {"admin_user"}


def test_admin_login_attempt_nullable_admin_user_id(db_engine):
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    with Session(db_engine) as session:
        org = _make_org(session)
        attempt = AdminLoginAttempt(
            organization_id=org.id,
            admin_user_id=None,
            source_ip="203.0.113.10",
            attempted_at=now,
            succeeded=False,
        )
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
        assert attempt.admin_user_id is None
        assert attempt.attempted_at == now
        assert attempt.attempted_at.tzinfo is not None
        columns = {
            c["name"]: c for c in sa.inspect(db_engine).get_columns("admin_login_attempt")
        }
        assert columns["admin_user_id"]["nullable"] is True
        indexes = [
            tuple(i["column_names"])
            for i in sa.inspect(db_engine).get_indexes("admin_login_attempt")
        ]
        assert ("admin_user_id", "attempted_at") in indexes
        assert ("source_ip", "attempted_at") in indexes


def test_tenant_login_attempt_nullable_tenancy_id_and_utc(db_engine):
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    with Session(db_engine) as session:
        org = _make_org(session)
        attempt = TenantLoginAttempt(
            organization_id=org.id,
            tenancy_id=None,
            source_ip="203.0.113.11",
            attempted_at=now,
            succeeded=False,
        )
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
        assert attempt.tenancy_id is None
        assert attempt.attempted_at == now
        assert attempt.attempted_at.tzinfo is not None
        indexes = [
            tuple(i["column_names"])
            for i in sa.inspect(db_engine).get_indexes("tenant_login_attempt")
        ]
        assert ("tenancy_id", "attempted_at") in indexes
        assert ("source_ip", "attempted_at") in indexes


def test_login_attempt_tables_are_prunable_not_append_only(db_engine):
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    inspector = sa.inspect(db_engine)
    for table in ("admin_login_attempt", "tenant_login_attempt"):
        assert "updated_at" not in {c["name"] for c in inspector.get_columns(table)}, table

    with Session(db_engine) as session:
        org = _make_org(session)
        attempt = AdminLoginAttempt(
            organization_id=org.id,
            admin_user_id=None,
            source_ip="203.0.113.12",
            attempted_at=now,
            succeeded=False,
        )
        session.add(attempt)
        session.commit()

        attempt.source_ip = "198.51.100.5"
        session.commit()

        session.delete(session.get(AdminLoginAttempt, attempt.id))
        session.commit()
        assert session.query(AdminLoginAttempt).count() == 0
