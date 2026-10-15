"""US8: Baseline migration (docs/04 §6, §9, §11, §12; FR-007, FR-020, FR-021,
FR-023, FR-025)."""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from backend.src.models import Base
from backend.src.models.base import IMMUTABLE_TABLES

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = REPO_ROOT / "backend" / "src" / "migrations" / "alembic.ini"

EXPECTED_TABLES = {
    "admin_login_attempt",
    "admin_session",
    "admin_user",
    "advance_movement",
    "audit_log",
    "bill_adjustment",
    "billing_config",
    "billing_override",
    "import_batch",
    "import_channel_category_mapping",
    "import_profile",
    "monthly_bill",
    "organization",
    "payment_allocation",
    "portal_setting",
    "property",
    "room",
    "sender_alias",
    "staged_import_row",
    "standard_amount_change",
    "tenancy",
    "tenant",
    "tenant_access_credential",
    "tenant_login_attempt",
    "tenant_session",
    "transaction",
    "transaction_match",
    "utility_bill_payment",
    "utility_provider",
}

EXPECTED_INDEXES = {
    "transaction": [
        ("organization_id", "transaction_date"),
        ("import_batch_id",),
        ("record_category",),
    ],
    "transaction_match": [("transaction_id", "created_at"), ("tenancy_id",)],
    "monthly_bill": [("billing_month",), ("organization_id", "billing_month")],
    "payment_allocation": [("transaction_id",), ("monthly_bill_id",)],
    "advance_movement": [("transaction_id",), ("tenancy_id", "occurred_at")],
    "utility_bill_payment": [
        ("provider_id", "spend_month"),
        ("organization_id", "spend_month"),
    ],
    "sender_alias": [("organization_id", "normalized_name")],
    "staged_import_row": [("import_batch_id",)],
    "audit_log": [("organization_id", "created_at"), ("entity_type", "entity_id")],
    "import_batch": [("statement_fingerprint",)],
    "billing_config": [("organization_id",)],
    "tenant_login_attempt": [("tenancy_id", "attempted_at"), ("source_ip", "attempted_at")],
    "admin_login_attempt": [
        ("admin_user_id", "attempted_at"),
        ("source_ip", "attempted_at"),
    ],
}

FORBIDDEN_MODULE_NAMES = {
    "api.py",
    "auth.py",
    "authentication.py",
    "billing.py",
    "parser.py",
    "parsing.py",
    "reporting.py",
    "reports.py",
    "worker.py",
    "scheduler.py",
    "ui.py",
}


def _upgrade(db_path: Path, monkeypatch, revision: str = "head") -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, revision)


def _downgrade(db_path: Path, monkeypatch, revision: str = "base") -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.downgrade(cfg, revision)


def test_baseline_upgrade_then_downgrade_then_reapply(tmp_path, monkeypatch):
    db_path = tmp_path / "baseline.db"

    _upgrade(db_path, monkeypatch)
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        first = set(sa.inspect(conn).get_table_names())
    assert first - {"alembic_version"} == EXPECTED_TABLES

    _downgrade(db_path, monkeypatch)
    with engine.connect() as conn:
        after_downgrade = set(sa.inspect(conn).get_table_names())
    assert after_downgrade - {"alembic_version"} == set()

    _upgrade(db_path, monkeypatch)
    with engine.connect() as conn:
        reapplied = set(sa.inspect(conn).get_table_names())
    assert reapplied - {"alembic_version"} == EXPECTED_TABLES
    engine.dispose()


def test_schema_has_exactly_29_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "tables.db"
    _upgrade(db_path, monkeypatch)
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        tables = set(sa.inspect(conn).get_table_names())
    domain = tables - {"alembic_version"}
    assert domain - EXPECTED_TABLES == set()
    assert EXPECTED_TABLES - domain == set()
    assert len(domain) == 29
    engine.dispose()


def test_engine_equivalence_partial_indexes_and_triggers(db_engine):
    inspector = sa.inspect(db_engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES <= tables

    tenancy_indexes = [
        (tuple(i["column_names"]), i["unique"]) for i in inspector.get_indexes("tenancy")
    ]
    assert (("room_id",), True) in tenancy_indexes

    match_indexes = [
        (tuple(i["column_names"]), i["unique"])
        for i in inspector.get_indexes("transaction_match")
    ]
    assert (("reverses_match_id",), True) in match_indexes

    with Session(db_engine) as session:
        session.execute(
            sa.text(
                'INSERT INTO organization (id, name, timezone, created_at) '
                "VALUES (:id, 'Org', 'Africa/Lagos', :now)"
            ).bindparams(
                sa.bindparam("id", value="org-1"),
                sa.bindparam("now", value="2026-01-01 00:00:00"),
            )
        )
        session.execute(
            sa.text(
                'INSERT INTO "transaction" (id, organization_id, record_category, source, '
                "transaction_date, channel, direction, description_raw, amount_minor, "
                "currency, duplicate_key, created_at) "
                "VALUES ('t-1', 'org-1', 'tenant_payment', 'manual', '2026-01-05', "
                "'FUNDING', 'credit', 'TRANSFER', 1000, 'NGN', 'dup-1', '2026-01-05 00:00:00')"
            )
        )
        session.commit()
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            session.execute(
                sa.text('UPDATE "transaction" SET channel = \'X\' WHERE id = \'t-1\'')
            )
        session.rollback()


def test_all_recommended_indexes_created(tmp_path, monkeypatch):
    db_path = tmp_path / "indexes.db"
    _upgrade(db_path, monkeypatch)
    engine = sa.create_engine(f"sqlite:///{db_path}")
    inspector = sa.inspect(engine)
    for table, indexes in EXPECTED_INDEXES.items():
        present = [tuple(i["column_names"]) for i in inspector.get_indexes(table)]
        for columns in indexes:
            assert columns in present, (table, columns, present)
    engine.dispose()


def test_all_tables_have_uuid_pk_and_created_at(tmp_path, monkeypatch):
    db_path = tmp_path / "pk.db"
    _upgrade(db_path, monkeypatch)
    engine = sa.create_engine(f"sqlite:///{db_path}")
    inspector = sa.inspect(engine)
    for table in EXPECTED_TABLES:
        pk = inspector.get_pk_constraint(table)
        assert pk["constrained_columns"] == ["id"], table
        columns = {c["name"] for c in inspector.get_columns(table)}
        assert "created_at" in columns, table
    engine.dispose()

    for table in Base.metadata.tables.values():
        assert isinstance(table.c.id.type, sa.Uuid), table.name


def test_scope_guard_no_forbidden_modules():
    src = REPO_ROOT / "backend" / "src"
    top_level = {p.name for p in src.iterdir() if p.is_file() and p.suffix == ".py"}
    assert top_level <= {"__init__.py", "db.py", "enums.py", "seed.py"}

    model_modules = {
        p.name for p in (src / "models").iterdir() if p.is_file() and p.suffix == ".py"
    }
    assert model_modules == {
        "__init__.py",
        "audit.py",
        "base.py",
        "identity.py",
        "ingestion.py",
        "ledgers_billing.py",
        "settings.py",
        "tenancy.py",
    }

    for path in src.rglob("*.py"):
        assert path.name not in FORBIDDEN_MODULE_NAMES, path
