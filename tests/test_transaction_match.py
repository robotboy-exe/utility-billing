"""US4 Design B: append-only transaction_match history (docs/04 §6.5, §7.9, §8,
§9, §11; FR-012, FR-016, FR-019, FR-020, FR-021, FR-027)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.src.models import (
    Organization,
    Property,
    Room,
    Tenancy,
    Transaction,
    TransactionMatch,
)

MATCH_COLUMNS = {
    "id": False,
    "organization_id": False,
    "transaction_id": False,
    "tenancy_id": False,
    "match_type": False,
    "reverses_match_id": True,
    "note": True,
    "created_at": False,
}


def _make_org(session: Session, name: str = "Acme Properties") -> Organization:
    org = Organization(name=name)
    session.add(org)
    session.commit()
    return org


def _make_chain(session: Session):
    org = _make_org(session)
    prop = Property(organization_id=org.id, name="Block A")
    session.add(prop)
    session.commit()
    room = Room(property_id=prop.id, label="Room 1")
    session.add(room)
    session.commit()
    tenancy = Tenancy(
        organization_id=org.id,
        room_id=room.id,
        status="active",
        start_date=date(2026, 1, 1),
    )
    session.add(tenancy)
    session.commit()
    return org, tenancy


def _make_transaction(session: Session, org: Organization, **overrides) -> Transaction:
    values = {
        "organization_id": org.id,
        "record_category": "tenant_payment",
        "source": "PAYVICE_AVANTUS",
        "transaction_date": date(2026, 1, 5),
        "channel": "FUNDING",
        "direction": "credit",
        "description_raw": "TRANSFER FROM JOHN OKAFOR",
        "amount_minor": 100000,
        "duplicate_key": f"txn-{uuid.uuid4().hex}",
    }
    values.update(overrides)
    txn = Transaction(**values)
    session.add(txn)
    session.commit()
    return txn


def _make_match(
    session: Session,
    org: Organization,
    txn: Transaction,
    tenancy: Tenancy,
    match_type: str = "automatic",
    reverses: TransactionMatch | None = None,
    note: str | None = None,
) -> TransactionMatch:
    match = TransactionMatch(
        organization_id=org.id,
        transaction_id=txn.id,
        tenancy_id=tenancy.id,
        match_type=match_type,
        reverses_match_id=reverses.id if reverses is not None else None,
        note=note,
    )
    session.add(match)
    session.commit()
    return match


def test_transaction_match_table_exists_with_columns(db_engine):
    inspector = sa.inspect(db_engine)
    assert "transaction_match" in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns("transaction_match")}
    assert set(columns) == set(MATCH_COLUMNS)
    for name, nullable in MATCH_COLUMNS.items():
        assert columns[name]["nullable"] is nullable, name


def test_match_type_check_rejects_unknown(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        txn = _make_transaction(session, org)
        session.add(
            TransactionMatch(
                organization_id=org.id,
                transaction_id=txn.id,
                tenancy_id=tenancy.id,
                match_type="bogus",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_reversal_requires_reverses_match_id(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        txn = _make_transaction(session, org)
        session.add(
            TransactionMatch(
                organization_id=org.id,
                transaction_id=txn.id,
                tenancy_id=tenancy.id,
                match_type="reversal",
                reverses_match_id=None,
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_non_reversal_rejects_reverses_match_id(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        txn = _make_transaction(session, org)
        original = _make_match(session, org, txn, tenancy, match_type="automatic")

        session.add(
            TransactionMatch(
                organization_id=org.id,
                transaction_id=txn.id,
                tenancy_id=tenancy.id,
                match_type="automatic",
                reverses_match_id=original.id,
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_reverses_match_id_unique_partial_index(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        txn = _make_transaction(session, org)
        original = _make_match(session, org, txn, tenancy, match_type="automatic")

        # Several non-reversal rows with reverses_match_id NULL are allowed
        # (the original plus the two added here).
        _make_match(session, org, txn, tenancy, match_type="automatic")
        _make_match(session, org, txn, tenancy, match_type="manual")
        assert (
            session.query(TransactionMatch)
            .filter(
                TransactionMatch.transaction_id == txn.id,
                TransactionMatch.reverses_match_id.is_(None),
            )
            .count()
            == 3
        )

        # A first reversal of the original is accepted.
        _make_match(session, org, txn, tenancy, match_type="reversal", reverses=original)

        # A second reversal of the same match is rejected by the partial unique index.
        session.add(
            TransactionMatch(
                organization_id=org.id,
                transaction_id=txn.id,
                tenancy_id=tenancy.id,
                match_type="reversal",
                reverses_match_id=original.id,
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_transaction_match_foreign_keys(db_engine):
    targets = {fk.column.table.name for fk in TransactionMatch.__table__.foreign_keys}
    assert targets == {"organization", "transaction", "tenancy", "transaction_match"}


def test_transaction_match_indexes_exist(db_engine):
    inspector = sa.inspect(db_engine)
    indexed = [tuple(i["column_names"]) for i in inspector.get_indexes("transaction_match")]
    assert ("transaction_id", "created_at") in indexed
    assert ("tenancy_id",) in indexed


def test_transaction_match_partial_unique_predicate_declared():
    candidates = [
        index
        for index in TransactionMatch.__table__.indexes
        if index.unique and tuple(c.name for c in index.columns) == ("reverses_match_id",)
    ]
    assert candidates, "no unique index on reverses_match_id"
    predicate = "reverses_match_id IS NOT NULL"
    sqlite_where = candidates[0].dialect_options["sqlite"].get("where")
    postgresql_where = candidates[0].dialect_options["postgresql"].get("where")
    assert sqlite_where is not None and predicate in str(sqlite_where)
    assert postgresql_where is not None and predicate in str(postgresql_where)


def test_transaction_match_append_only(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        txn = _make_transaction(session, org)
        match = _make_match(session, org, txn, tenancy, match_type="automatic")

        match.note = "edited note"
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            session.commit()
        session.rollback()

        session.delete(session.get(TransactionMatch, match.id))
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            session.commit()
        session.rollback()


def test_transaction_has_no_tenancy_id_or_matching_status_columns(db_engine):
    columns = {c["name"] for c in sa.inspect(db_engine).get_columns("transaction")}
    assert "tenancy_id" not in columns
    assert "matching_status" not in columns
    indexed = [
        tuple(i["column_names"]) for i in sa.inspect(db_engine).get_indexes("transaction")
    ]
    assert ("tenancy_id",) not in indexed
