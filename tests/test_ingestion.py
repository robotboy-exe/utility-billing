"""US3: Transaction ingestion staging (docs/04 §6.7;
FR-003, FR-010, FR-012, FR-015, FR-018, FR-019, FR-020)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.src.models import (
    ImportBatch,
    ImportChannelCategoryMapping,
    ImportProfile,
    Organization,
    StagedImportRow,
)


def _make_organization(session: Session, name: str = "Acme Properties") -> Organization:
    organization = Organization(name=name)
    session.add(organization)
    session.commit()
    return organization


def _make_profile(
    session: Session,
    code: str = "PAYVICE_AVANTUS",
    organization_id=None,
) -> ImportProfile:
    profile = ImportProfile(
        organization_id=organization_id,
        code=code,
        display_name="Payvice Avantus",
        source_type="pdf",
    )
    session.add(profile)
    session.commit()
    return profile


def _make_batch(
    session: Session,
    organization: Organization,
    profile: ImportProfile,
    status: str = "parsing",
    fingerprint: str | None = "fp-1",
) -> ImportBatch:
    batch = ImportBatch(
        organization_id=organization.id,
        import_profile_id=profile.id,
        status=status,
        statement_fingerprint=fingerprint,
        uploaded_at=datetime.now(timezone.utc),
    )
    session.add(batch)
    session.commit()
    return batch


def _make_row(session: Session, batch: ImportBatch, **overrides) -> StagedImportRow:
    values = {
        "row_category": "tenant_payment",
        "transaction_date": datetime(2026, 1, 5).date(),
        "channel": "FUNDING",
        "direction": "credit",
        "description_raw": "TRANSFER FROM JOHN OKAFOR",
        "amount_minor": 100000,
        "duplicate_key": f"dup-{batch.id}-{StagedImportRow.__name__}",
        "parse_status": "valid",
    }
    values.update(overrides)
    row = StagedImportRow(import_batch_id=batch.id, **values)
    session.add(row)
    session.commit()
    return row


def test_ingestion_tables_exist(db_engine):
    inspector = sa.inspect(db_engine)
    expected = {
        "import_profile",
        "import_channel_category_mapping",
        "import_batch",
        "staged_import_row",
    }
    assert expected <= set(inspector.get_table_names())


def test_channel_category_mapping_category_check_rejects_unknown(db_engine):
    with Session(db_engine) as session:
        profile = _make_profile(session)
        session.add(
            ImportChannelCategoryMapping(
                import_profile_id=profile.id,
                channel="FUNDING",
                direction="credit",
                category="commission",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_channel_category_mapping_unique_profile_channel_direction(db_engine):
    with Session(db_engine) as session:
        profile = _make_profile(session)
        session.add(
            ImportChannelCategoryMapping(
                import_profile_id=profile.id,
                channel="FUNDING",
                direction=None,
                category="tenant_payment",
            )
        )
        session.commit()

        # Same profile + channel + NULL direction is a duplicate.
        session.add(
            ImportChannelCategoryMapping(
                import_profile_id=profile.id,
                channel="FUNDING",
                direction=None,
                category="ignored",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()

        # Explicit directions are distinct from NULL and from each other.
        session.add(
            ImportChannelCategoryMapping(
                import_profile_id=profile.id,
                channel="FUNDING",
                direction="credit",
                category="tenant_payment",
            )
        )
        session.add(
            ImportChannelCategoryMapping(
                import_profile_id=profile.id,
                channel="FUNDING",
                direction="debit",
                category="ignored",
            )
        )
        session.commit()
        assert (
            session.query(ImportChannelCategoryMapping)
            .filter_by(import_profile_id=profile.id, channel="FUNDING")
            .count()
            == 3
        )

        # Same channel/direction under a different profile is allowed.
        other = _make_profile(session, code="OTHER_PROFILE")
        session.add(
            ImportChannelCategoryMapping(
                import_profile_id=other.id,
                channel="FUNDING",
                direction=None,
                category="tenant_payment",
            )
        )
        session.commit()


def test_import_batch_fingerprint_partial_unique_confirmed_completed(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        profile = _make_profile(session)
        _make_batch(session, organization, profile, status="confirmed", fingerprint="fp-abc")

        session.add(
            ImportBatch(
                organization_id=organization.id,
                import_profile_id=profile.id,
                status="confirmed",
                statement_fingerprint="fp-abc",
                uploaded_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            ImportBatch(
                organization_id=organization.id,
                import_profile_id=profile.id,
                status="completed",
                statement_fingerprint="fp-abc",
                uploaded_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_rejected_batch_allows_reimport_same_fingerprint(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        profile = _make_profile(session)
        _make_batch(session, organization, profile, status="rejected", fingerprint="fp-retry")

        # Rejected/failed batches never block a re-import of the same statement.
        _make_batch(session, organization, profile, status="rejected", fingerprint="fp-retry")
        _make_batch(session, organization, profile, status="failed", fingerprint="fp-retry")

        # A later confirmed batch with the same fingerprint commits once.
        confirmed = _make_batch(
            session, organization, profile, status="confirmed", fingerprint="fp-retry"
        )
        assert confirmed.status == "confirmed"
        assert (
            session.query(ImportBatch)
            .filter_by(statement_fingerprint="fp-retry")
            .count()
            == 4
        )


def test_staged_row_category_check_rejects_nonpersistable(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        batch = _make_batch(session, organization, _make_profile(session))
        session.add(
            StagedImportRow(
                import_batch_id=batch.id,
                row_category="ignored",
                transaction_date=datetime(2026, 1, 5).date(),
                channel="TRANSFER",
                direction="debit",
                description_raw="TRANSFER CHARGE",
                amount_minor=500,
                duplicate_key="dup-ignored-1",
                parse_status="valid",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_staged_row_parse_status_check(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        batch = _make_batch(session, organization, _make_profile(session))
        session.add(
            StagedImportRow(
                import_batch_id=batch.id,
                row_category="tenant_payment",
                transaction_date=datetime(2026, 1, 5).date(),
                channel="FUNDING",
                direction="credit",
                description_raw="TRANSFER",
                amount_minor=100000,
                duplicate_key="dup-parse-1",
                parse_status="bogus",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_staged_row_rejects_unrecognized_parse_status(db_engine):
    """Unrecognized rows are not staged (docs/04 §6.7, 0.9.1)."""
    with Session(db_engine) as session:
        organization = _make_organization(session)
        batch = _make_batch(session, organization, _make_profile(session))
        session.add(
            StagedImportRow(
                import_batch_id=batch.id,
                row_category="tenant_payment",
                transaction_date=datetime(2026, 1, 5).date(),
                channel="MYSTERY",
                direction="credit",
                description_raw="UNKNOWN CHANNEL",
                amount_minor=100000,
                duplicate_key="dup-unrec-1",
                parse_status="unrecognized",
            )
        )
        with pytest.raises(sa.exc.IntegrityError) as excinfo:
            session.commit()
        assert "ck_parse_status_values" in str(excinfo.value)
        session.rollback()


def test_import_batch_unrecognized_rows_round_trip(db_engine):
    """unrecognized_rows stores a list of dicts; the count is independent."""
    details = [
        {
            "row_number": 4,
            "transaction_date": "2026-01-05",
            "channel": "MYSTERY",
            "direction": "credit",
            "amount_minor": 150000,
            "description_raw": "UNKNOWN CHANNEL A",
        },
        {
            "row_number": 9,
            "transaction_date": "2026-01-07",
            "channel": "OTHER",
            "direction": "debit",
            "amount_minor": 25000,
            "description_raw": "UNKNOWN CHANNEL B",
        },
    ]
    with Session(db_engine) as session:
        organization = _make_organization(session)
        batch = _make_batch(session, organization, _make_profile(session))
        batch_id = batch.id
        batch.unrecognized_rows = details
        batch.unrecognized_row_count = 5
        session.commit()
    with Session(db_engine) as session:
        stored = session.get(ImportBatch, batch_id)
        assert stored.unrecognized_rows == details
        assert len(stored.unrecognized_rows) == 2
        assert stored.unrecognized_row_count == 5


def test_import_batch_unrecognized_rows_nullable(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        batch = _make_batch(session, organization, _make_profile(session))
        assert batch.unrecognized_rows is None


def test_staged_row_duplicate_key_not_unique(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        batch = _make_batch(session, organization, _make_profile(session))
        _make_row(session, batch, duplicate_key="dup-shared-1", parse_status="valid")
        _make_row(session, batch, duplicate_key="dup-shared-1", parse_status="duplicate")
        assert (
            session.query(StagedImportRow)
            .filter_by(import_batch_id=batch.id, duplicate_key="dup-shared-1")
            .count()
            == 2
        )


def test_commission_channel_never_staged_or_persisted(db_engine):
    """The schema rejects the non-persisted `commission` category in both
    `staged_import_row` and `transaction` via their category CHECKs. The
    channel-level commission ban (docs/04 §8 item 4) is a service-layer rule,
    not a schema constraint, so this test proves only the category CHECKs and
    that a COMMISSION channel may be mapped to `excluded`."""
    from backend.src.models.ledgers_billing import Transaction

    with Session(db_engine) as session:
        organization = _make_organization(session)
        profile = _make_profile(session)
        # The schema permits configuring a COMMISSION channel as `excluded`.
        session.add(
            ImportChannelCategoryMapping(
                import_profile_id=profile.id,
                channel="COMMISSION",
                direction=None,
                category="excluded",
            )
        )
        session.commit()
        mapping = (
            session.query(ImportChannelCategoryMapping)
            .filter_by(import_profile_id=profile.id, channel="COMMISSION")
            .one()
        )
        assert mapping.category == "excluded"

        batch = _make_batch(session, organization, profile)
        # `commission` is not a persistable staged-row category.
        session.add(
            StagedImportRow(
                import_batch_id=batch.id,
                row_category="commission",
                transaction_date=datetime(2026, 1, 5).date(),
                channel="COMMISSION",
                direction="debit",
                description_raw="COMMISSION CHARGE",
                amount_minor=250,
                duplicate_key="dup-commission-1",
                parse_status="valid",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()

        # `commission` is not a persistable transaction category either.
        session.add(
            Transaction(
                organization_id=organization.id,
                record_category="commission",
                source="PAYVICE_AVANTUS",
                transaction_date=datetime(2026, 1, 5).date(),
                channel="COMMISSION",
                direction="debit",
                description_raw="COMMISSION CHARGE",
                amount_minor=250,
                duplicate_key="dup-commission-txn-1",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_staged_row_direction_check_rejects_unknown(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        batch = _make_batch(session, organization, _make_profile(session))
        session.add(
            StagedImportRow(
                import_batch_id=batch.id,
                row_category="tenant_payment",
                transaction_date=datetime(2026, 1, 5).date(),
                channel="FUNDING",
                direction="sideways",
                description_raw="TRANSFER",
                amount_minor=100000,
                duplicate_key="dup-direction-1",
                parse_status="valid",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_import_batch_status_check_rejects_unknown(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        profile = _make_profile(session)
        session.add(
            ImportBatch(
                organization_id=organization.id,
                import_profile_id=profile.id,
                status="bogus",
                statement_fingerprint="fp-bogus",
                uploaded_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_import_batch_totals_status_check_rejects_unknown(db_engine):
    with Session(db_engine) as session:
        organization = _make_organization(session)
        profile = _make_profile(session)
        session.add(
            ImportBatch(
                organization_id=organization.id,
                import_profile_id=profile.id,
                status="staged",
                totals_status="bogus",
                statement_fingerprint="fp-totals-bogus",
                uploaded_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_import_profile_code_unique(db_engine):
    with Session(db_engine) as session:
        _make_profile(session, code="PAYVICE_AVANTUS")
        session.add(
            ImportProfile(
                organization_id=None,
                code="PAYVICE_AVANTUS",
                display_name="Duplicate profile",
                source_type="pdf",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_import_batch_unrecognized_rows_is_jsonb_on_postgresql(db_engine):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("JSONB rendering is PostgreSQL-only")
    with db_engine.connect() as connection:
        data_type = connection.execute(
            sa.text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = 'import_batch' "
                "AND column_name = 'unrecognized_rows'"
            )
        ).scalar_one()
    assert data_type == "jsonb"
