"""US4: Ledgers and billing tables (docs/04 §6.4–§6.6;
FR-004, FR-009, FR-010, FR-011, FR-013, FR-014, FR-016, FR-017, FR-019,
FR-020, FR-021, FR-022)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.src.models import (
    AdminUser,
    AdvanceMovement,
    BillAdjustment,
    BillingConfig,
    BillingOverride,
    ImportBatch,
    ImportProfile,
    MonthlyBill,
    Organization,
    PaymentAllocation,
    Property,
    Room,
    StandardAmountChange,
    Tenancy,
    Transaction,
    TransactionMatch,
    UtilityBillPayment,
    UtilityProvider,
)
from backend.src.models.base import IMMUTABLE_TABLES, UTCDateTime

JAN = date(2026, 1, 1)
FEB = date(2026, 2, 1)


def _make_org(session: Session, name: str = "Acme Properties") -> Organization:
    org = Organization(name=name)
    session.add(org)
    session.commit()
    return org


def _make_admin(session: Session, org: Organization, email: str = "admin@example.com") -> AdminUser:
    admin = AdminUser(organization_id=org.id, email=email, password_hash="hashed")
    session.add(admin)
    session.commit()
    return admin


def _make_property(session: Session, org: Organization, name: str = "Block A") -> Property:
    prop = Property(organization_id=org.id, name=name)
    session.add(prop)
    session.commit()
    return prop


def _make_room(session: Session, prop: Property, label: str = "Room 1") -> Room:
    room = Room(property_id=prop.id, label=label)
    session.add(room)
    session.commit()
    return room


def _make_tenancy(session: Session, org: Organization, room: Room) -> Tenancy:
    tenancy = Tenancy(
        organization_id=org.id,
        room_id=room.id,
        status="active",
        start_date=date(2026, 1, 1),
    )
    session.add(tenancy)
    session.commit()
    return tenancy


def _make_chain(session: Session):
    org = _make_org(session)
    tenancy = _make_tenancy(session, org, _make_room(session, _make_property(session, org)))
    return org, tenancy


def _make_profile(session: Session, code: str = "PAYVICE_AVANTUS") -> ImportProfile:
    profile = ImportProfile(
        organization_id=None,
        code=code,
        display_name="Payvice Avantus",
        source_type="pdf",
    )
    session.add(profile)
    session.commit()
    return profile


def _make_batch(
    session: Session,
    org: Organization,
    profile: ImportProfile,
    status: str = "confirmed",
    fingerprint: str | None = None,
) -> ImportBatch:
    batch = ImportBatch(
        organization_id=org.id,
        import_profile_id=profile.id,
        status=status,
        statement_fingerprint=fingerprint or f"fp-{uuid.uuid4().hex[:12]}",
        uploaded_at=datetime.now(timezone.utc),
    )
    session.add(batch)
    session.commit()
    return batch


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


def _make_bill(
    session: Session,
    org: Organization,
    tenancy: Tenancy,
    month: date,
    standard: int = 50000,
    final: int = 50000,
) -> MonthlyBill:
    bill = MonthlyBill(
        organization_id=org.id,
        tenancy_id=tenancy.id,
        billing_month=month,
        standard_amount_minor=standard,
        final_amount_minor=final,
    )
    session.add(bill)
    session.commit()
    return bill


def _make_allocation(
    session: Session,
    txn: Transaction,
    bill: MonthlyBill,
    amount: int,
    allocation_type: str = "automatic",
    reverses: PaymentAllocation | None = None,
) -> PaymentAllocation:
    alloc = PaymentAllocation(
        transaction_id=txn.id,
        monthly_bill_id=bill.id,
        amount_minor=amount,
        allocation_type=allocation_type,
        reverses_allocation_id=reverses.id if reverses is not None else None,
    )
    session.add(alloc)
    session.commit()
    return alloc


def _make_advance(
    session: Session,
    org: Organization,
    tenancy: Tenancy,
    txn: Transaction,
    movement_type: str,
    amount: int,
    bill: MonthlyBill | None = None,
    allocation: PaymentAllocation | None = None,
) -> AdvanceMovement:
    movement = AdvanceMovement(
        organization_id=org.id,
        tenancy_id=tenancy.id,
        transaction_id=txn.id,
        movement_type=movement_type,
        amount_minor=amount,
        monthly_bill_id=bill.id if bill is not None else None,
        allocation_id=allocation.id if allocation is not None else None,
        occurred_at=datetime.now(timezone.utc),
    )
    session.add(movement)
    session.commit()
    return movement


def _make_provider(session: Session, code: str = "BEDC") -> UtilityProvider:
    provider = UtilityProvider(
        organization_id=None,
        code=code,
        display_name="Benin Electricity",
        channel_signature="BEDC",
    )
    session.add(provider)
    session.commit()
    return provider


def _make_utility_payment(
    session: Session,
    org: Organization,
    txn: Transaction,
    provider: UtilityProvider,
) -> UtilityBillPayment:
    payment = UtilityBillPayment(
        organization_id=org.id,
        transaction_id=txn.id,
        provider_id=provider.id,
        amount_minor=txn.amount_minor,
        payment_datetime=datetime.now(timezone.utc),
        spend_month=date(2026, 1, 1),
    )
    session.add(payment)
    session.commit()
    return payment


def _signed_allocation_total(session: Session, transaction_id) -> int:
    signed = sa.case(
        (PaymentAllocation.allocation_type == "reversal", -PaymentAllocation.amount_minor),
        else_=PaymentAllocation.amount_minor,
    )
    return (
        session.query(sa.func.coalesce(sa.func.sum(signed), 0))
        .filter(PaymentAllocation.transaction_id == transaction_id)
        .scalar()
    )


def _logged_advance_total(session: Session, transaction_id) -> int:
    def _sum_of(movement_type: str) -> int:
        return (
            session.query(sa.func.coalesce(sa.func.sum(AdvanceMovement.amount_minor), 0))
            .filter(
                AdvanceMovement.transaction_id == transaction_id,
                AdvanceMovement.movement_type == movement_type,
            )
            .scalar()
        )

    return _sum_of("created") - _sum_of("applied") - _sum_of("reversed")


def test_billing_config_tables_exist_with_money_and_currency(db_engine):
    inspector = sa.inspect(db_engine)
    assert {"billing_config", "billing_override", "standard_amount_change"} <= set(
        inspector.get_table_names()
    )
    config_columns = {c["name"] for c in inspector.get_columns("billing_config")}
    assert {"standard_amount_minor", "currency"} <= config_columns
    change_columns = {c["name"] for c in inspector.get_columns("standard_amount_change")}
    assert {"previous_amount_minor", "new_amount_minor", "currency"} <= change_columns


def test_billing_config_one_org_wide_row_per_organization(db_engine):
    with Session(db_engine) as session:
        org = _make_org(session)
        other_org = _make_org(session, name="Other Org")
        prop = _make_property(session, org)

        session.add(BillingConfig(organization_id=org.id, standard_amount_minor=50000))
        session.commit()

        # A second org-wide row for the same organization is rejected.
        session.add(BillingConfig(organization_id=org.id, standard_amount_minor=60000))
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()

        # A property-scoped row does not collide with the org-wide row.
        session.add(
            BillingConfig(
                organization_id=org.id, property_id=prop.id, standard_amount_minor=55000
            )
        )
        session.commit()

        # Another organization gets its own org-wide row.
        session.add(BillingConfig(organization_id=other_org.id, standard_amount_minor=50000))
        session.commit()
        assert (
            session.query(BillingConfig)
            .filter_by(organization_id=org.id, property_id=None)
            .count()
            == 1
        )


def test_billing_override_unique_tenancy_month_and_decision_check(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        session.add(
            BillingOverride(
                organization_id=org.id,
                tenancy_id=tenancy.id,
                billing_month=JAN,
                decision="bill",
            )
        )
        session.commit()

        session.add(
            BillingOverride(
                organization_id=org.id,
                tenancy_id=tenancy.id,
                billing_month=JAN,
                decision="skip",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            BillingOverride(
                organization_id=org.id,
                tenancy_id=tenancy.id,
                billing_month=FEB,
                decision="frobnicate",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_standard_amount_change_append_only(db_engine):
    with Session(db_engine) as session:
        org = _make_org(session)
        admin = _make_admin(session, org)
        change = StandardAmountChange(
            organization_id=org.id,
            previous_amount_minor=50000,
            new_amount_minor=60000,
            auto_note="Standard amount changed from 50000 to 60000",
            admin_id=admin.id,
            effective_at=datetime.now(timezone.utc),
        )
        session.add(change)
        session.commit()

        change.custom_note = "edited"
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            session.commit()
        session.rollback()

        session.delete(session.get(StandardAmountChange, change.id))
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            session.commit()
        session.rollback()


def test_monthly_bill_unique_tenancy_month(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        _make_bill(session, org, tenancy, JAN)

        session.add(
            MonthlyBill(
                organization_id=org.id,
                tenancy_id=tenancy.id,
                billing_month=JAN,
                standard_amount_minor=50000,
                final_amount_minor=50000,
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()

        second = _make_bill(session, org, tenancy, FEB)
        assert second.billing_month == FEB


def test_transaction_record_category_check_rejects_commission(db_engine):
    with Session(db_engine) as session:
        org = _make_org(session)
        session.add(
            Transaction(
                organization_id=org.id,
                record_category="commission",
                source="PAYVICE_AVANTUS",
                transaction_date=date(2026, 1, 5),
                channel="COMMISSION",
                direction="debit",
                description_raw="COMMISSION",
                amount_minor=250,
                duplicate_key="txn-commission-1",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_transaction_duplicate_key_unique(db_engine):
    with Session(db_engine) as session:
        org = _make_org(session)
        _make_transaction(session, org, duplicate_key="txn-dup-1")
        session.add(
            Transaction(
                organization_id=org.id,
                record_category="tenant_payment",
                source="PAYVICE_AVANTUS",
                transaction_date=date(2026, 1, 5),
                channel="FUNDING",
                direction="credit",
                description_raw="TRANSFER",
                amount_minor=100000,
                duplicate_key="txn-dup-1",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_utility_bill_payment_transaction_id_unique(db_engine):
    with Session(db_engine) as session:
        org = _make_org(session)
        provider = _make_provider(session)
        txn = _make_transaction(
            session,
            org,
            record_category="utility_bill_payment",
            channel="BEDC",
            direction="debit",
        )
        _make_utility_payment(session, org, txn, provider)

        session.add(
            UtilityBillPayment(
                organization_id=org.id,
                transaction_id=txn.id,
                provider_id=provider.id,
                amount_minor=txn.amount_minor,
                payment_datetime=datetime.now(timezone.utc),
                spend_month=date(2026, 1, 1),
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_utility_provider_code_unique(db_engine):
    with Session(db_engine) as session:
        _make_provider(session, code="BEDC")
        session.add(
            UtilityProvider(
                organization_id=None,
                code="BEDC",
                display_name="Duplicate provider",
                channel_signature="BEDC",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_two_ledger_separation_has_no_cross_settle_paths(db_engine):
    payment_columns = set(sa.inspect(UtilityBillPayment).columns.keys())
    assert "tenancy_id" not in payment_columns
    assert "matching_status" not in payment_columns
    assert "monthly_bill_id" not in payment_columns
    payment_fks = {
        fk.column.table.name for fk in UtilityBillPayment.__table__.foreign_keys
    }
    assert payment_fks <= {"organization", "transaction", "utility_provider", "import_batch"}

    allocation_fks = {
        fk.column.table.name for fk in PaymentAllocation.__table__.foreign_keys
    }
    assert allocation_fks <= {"transaction", "monthly_bill", "payment_allocation"}

    with Session(db_engine) as session:
        org = _make_org(session)
        provider = _make_provider(session)
        utility_txn = _make_transaction(
            session,
            org,
            record_category="utility_bill_payment",
            channel="BEDC",
            direction="debit",
        )
        _make_utility_payment(session, org, utility_txn, provider)
        assert (
            session.query(PaymentAllocation)
            .filter_by(transaction_id=utility_txn.id)
            .count()
            == 0
        )


def test_money_columns_are_integer_minor_with_currency(db_engine):
    inspector = sa.inspect(db_engine)
    expected_minor = {
        "billing_config": ["standard_amount_minor"],
        "standard_amount_change": ["previous_amount_minor", "new_amount_minor"],
        "transaction": ["amount_minor"],
        "monthly_bill": ["standard_amount_minor", "final_amount_minor"],
        "payment_allocation": ["amount_minor"],
        "advance_movement": ["amount_minor"],
        "bill_adjustment": ["previous_amount_minor", "new_amount_minor"],
        "utility_bill_payment": ["amount_minor"],
        "import_batch": ["tenant_payment_total_minor", "utility_payment_total_minor"],
        "staged_import_row": ["amount_minor"],
    }
    with_currency = {
        "billing_config",
        "standard_amount_change",
        "transaction",
        "monthly_bill",
        "payment_allocation",
        "advance_movement",
        "bill_adjustment",
        "utility_bill_payment",
        "import_batch",
    }
    for table, minors in expected_minor.items():
        columns = {c["name"]: c for c in inspector.get_columns(table)}
        for minor in minors:
            assert isinstance(columns[minor]["type"], sa.BigInteger)
            if table == "import_batch":
                # Staged-row totals are populated at parse time, so they stay nullable.
                assert columns[minor]["nullable"] is True
            else:
                assert columns[minor]["nullable"] is False
        if table in with_currency:
            assert columns["currency"]["nullable"] is False
        else:
            assert "currency" not in columns

    for table in inspector.get_table_names():
        for column in inspector.get_columns(table):
            assert not isinstance(column["type"], (sa.Float, sa.Numeric))

    with Session(db_engine) as session:
        org = _make_org(session)
        session.add(BillingConfig(organization_id=org.id, standard_amount_minor=-1))
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            Transaction(
                organization_id=org.id,
                record_category="tenant_payment",
                source="manual",
                transaction_date=date(2026, 1, 5),
                channel="FUNDING",
                direction="credit",
                description_raw="TRANSFER",
                amount_minor=0,
                duplicate_key="txn-zero-1",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def _build_immutable_row(session: Session, table: str, tag: str):
    org = _make_org(session, name=f"Immutable {tag}")
    admin = _make_admin(session, org, email=f"{tag}@example.com")
    tenancy = _make_tenancy(session, org, _make_room(session, _make_property(session, org)))
    if table == "transaction":
        return _make_transaction(session, org, duplicate_key=f"imm-{tag}")
    if table == "standard_amount_change":
        change = StandardAmountChange(
            organization_id=org.id,
            previous_amount_minor=50000,
            new_amount_minor=60000,
            auto_note="rate change",
            admin_id=admin.id,
            effective_at=datetime.now(timezone.utc),
        )
        session.add(change)
        session.commit()
        return change
    if table == "utility_bill_payment":
        provider = _make_provider(session, code=f"PROV-{tag}")
        txn = _make_transaction(
            session,
            org,
            duplicate_key=f"imm-{tag}",
            record_category="utility_bill_payment",
            channel="BEDC",
            direction="debit",
        )
        return _make_utility_payment(session, org, txn, provider)
    bill = _make_bill(session, org, tenancy, JAN)
    if table == "monthly_bill":
        return bill
    if table == "bill_adjustment":
        adjustment = BillAdjustment(
            monthly_bill_id=bill.id,
            adjustment_type="rate_change",
            previous_amount_minor=50000,
            new_amount_minor=40000,
            admin_id=admin.id,
        )
        session.add(adjustment)
        session.commit()
        return adjustment
    txn = _make_transaction(session, org, duplicate_key=f"imm-{tag}")
    if table == "payment_allocation":
        return _make_allocation(session, txn, bill, 40000)
    if table == "advance_movement":
        return _make_advance(session, org, tenancy, txn, "created", 60000)
    if table == "transaction_match":
        match = TransactionMatch(
            organization_id=org.id,
            transaction_id=txn.id,
            tenancy_id=tenancy.id,
            match_type="automatic",
        )
        session.add(match)
        session.commit()
        return match
    raise AssertionError(f"no builder for {table}")


def test_immutable_financial_tables_reject_update_and_delete(db_engine):
    assert set(IMMUTABLE_TABLES) == {
        "transaction",
        "transaction_match",
        "payment_allocation",
        "advance_movement",
        "bill_adjustment",
        "standard_amount_change",
        "utility_bill_payment",
        "audit_log",
    }
    update_targets = {
        "transaction": ("description_raw", "edited description"),
        "transaction_match": ("note", "edited note"),
        "payment_allocation": ("allocation_type", "manual"),
        "advance_movement": ("note", "edited note"),
        "bill_adjustment": ("custom_note", "edited note"),
        "standard_amount_change": ("custom_note", "edited note"),
        "utility_bill_payment": ("customer_reference", "edited reference"),
    }
    for table in update_targets:
        with Session(db_engine) as session:
            row = _build_immutable_row(session, table, tag=table)
            row_id = row.id
            column, new_value = update_targets[table]
            setattr(row, column, new_value)
            with pytest.raises(sa.exc.DBAPIError, match="append-only"):
                session.commit()
            session.rollback()

            session.delete(session.get(type(row), row_id))
            with pytest.raises(sa.exc.DBAPIError, match="append-only"):
                session.commit()
            session.rollback()


def test_only_mutable_tables_carry_updated_at(db_engine):
    inspector = sa.inspect(db_engine)
    mutable = {
        "organization",
        "admin_user",
        "property",
        "room",
        "tenancy",
        "tenant",
        "sender_alias",
        "tenant_access_credential",
        "import_profile",
        "import_channel_category_mapping",
        "import_batch",
        "billing_config",
        "billing_override",
        "monthly_bill",
        "utility_provider",
    }
    append_only = {
        "transaction",
        "payment_allocation",
        "advance_movement",
        "bill_adjustment",
        "standard_amount_change",
        "utility_bill_payment",
    }
    write_once = {"tenant_session", "staged_import_row"}
    for table in mutable:
        assert "updated_at" in {c["name"] for c in inspector.get_columns(table)}, table
    for table in append_only | write_once:
        assert "updated_at" not in {c["name"] for c in inspector.get_columns(table)}, table


def test_no_stored_derived_state_columns(db_engine):
    inspector = sa.inspect(db_engine)
    us4_tables = [
        "billing_config",
        "billing_override",
        "standard_amount_change",
        "transaction",
        "monthly_bill",
        "payment_allocation",
        "advance_movement",
        "bill_adjustment",
        "utility_provider",
        "utility_bill_payment",
    ]
    forbidden = {
        "bill_status",
        "remaining",
        "remaining_due",
        "remaining_minor",
        "outstanding",
        "outstanding_balance",
        "outstanding_minor",
        "advance_balance",
        "net_position",
        "utility_spend",
        "spend_total",
        "total_allocated",
        "amount_due",
        "status",
    }
    for table in us4_tables:
        names = {c["name"] for c in inspector.get_columns(table)}
        assert not (names & forbidden), (table, names & forbidden)
    bill_names = {c["name"] for c in inspector.get_columns("monthly_bill")}
    assert bill_names >= {"standard_amount_minor", "final_amount_minor", "is_adjusted"}


def test_allocation_cap_enforceable_from_columns(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        txn = _make_transaction(session, org, amount_minor=100000)
        bill_jan = _make_bill(session, org, tenancy, JAN)
        bill_feb = _make_bill(session, org, tenancy, FEB)

        first = _make_allocation(session, txn, bill_jan, 40000, "automatic")
        _make_allocation(session, txn, bill_feb, 30000, "manual")
        _make_allocation(session, txn, bill_jan, 15000, "reversal", reverses=first)

        total = _signed_allocation_total(session, txn.id)
        assert total == 40000 + 30000 - 15000
        assert total <= txn.amount_minor


def test_advance_reconciliation_identity_from_records(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        txn = _make_transaction(session, org, amount_minor=100000)
        bill_jan = _make_bill(session, org, tenancy, JAN)
        bill_feb = _make_bill(session, org, tenancy, FEB)

        # Overpayment: 100000 settles a 40000 bill, 60000 becomes advance.
        _make_allocation(session, txn, bill_jan, 40000)
        _make_advance(session, org, tenancy, txn, "created", 60000)
        assert txn.amount_minor - _signed_allocation_total(session, txn.id) == 60000
        assert _logged_advance_total(session, txn.id) == 60000

        # Partial application in one chunk: 20000 of advance settles February.
        feb_alloc = _make_allocation(session, txn, bill_feb, 20000)
        _make_advance(session, org, tenancy, txn, "applied", 20000, bill_feb, feb_alloc)
        assert txn.amount_minor - _signed_allocation_total(session, txn.id) == 40000
        assert _logged_advance_total(session, txn.id) == 40000

        # Second chunk: multi-chunk application of 5000 more.
        feb_alloc_two = _make_allocation(session, txn, bill_feb, 5000)
        _make_advance(session, org, tenancy, txn, "applied", 5000, bill_feb, feb_alloc_two)
        assert txn.amount_minor - _signed_allocation_total(session, txn.id) == 35000
        assert _logged_advance_total(session, txn.id) == 35000

        # Applied-then-reversed: undo 10000 of allocation, restore as new created.
        _make_allocation(session, txn, bill_feb, 10000, "reversal", reverses=feb_alloc)
        _make_advance(session, org, tenancy, txn, "created", 10000)
        assert txn.amount_minor - _signed_allocation_total(session, txn.id) == 45000
        assert _logged_advance_total(session, txn.id) == 45000


def test_bill_amount_change_requires_bill_adjustment_columns(db_engine):
    fk_targets = {
        fk.column.table.name for fk in BillAdjustment.__table__.foreign_keys
    }
    assert "monthly_bill" in fk_targets
    assert "admin_user" in fk_targets

    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        admin = _make_admin(session, org)
        bill = _make_bill(session, org, tenancy, JAN, standard=50000, final=50000)
        assert session.query(BillAdjustment).filter_by(monthly_bill_id=bill.id).count() == 0

        bill.final_amount_minor = 40000
        bill.is_adjusted = True
        session.add(
            BillAdjustment(
                monthly_bill_id=bill.id,
                adjustment_type="rate_change",
                previous_amount_minor=50000,
                new_amount_minor=40000,
                admin_id=admin.id,
            )
        )
        session.commit()

        adjustments = (
            session.query(BillAdjustment).filter_by(monthly_bill_id=bill.id).all()
        )
        assert len(adjustments) == 1
        assert adjustments[0].previous_amount_minor == 50000
        assert adjustments[0].new_amount_minor == bill.final_amount_minor


def test_recommended_indexes_exist(db_engine):
    inspector = sa.inspect(db_engine)

    def _indexed(table: str) -> list[tuple[str, ...]]:
        return [tuple(index["column_names"]) for index in inspector.get_indexes(table)]

    expected = {
        "transaction": [
            ("organization_id", "transaction_date"),
            ("import_batch_id",),
            ("record_category",),
        ],
        "monthly_bill": [("billing_month",), ("organization_id", "billing_month")],
        "payment_allocation": [("transaction_id",), ("monthly_bill_id",)],
        "advance_movement": [("transaction_id",), ("tenancy_id", "occurred_at")],
        "utility_bill_payment": [
            ("provider_id", "spend_month"),
            ("organization_id", "spend_month"),
        ],
        "staged_import_row": [("import_batch_id",)],
        "import_batch": [("statement_fingerprint",)],
        "billing_config": [("organization_id",)],
    }
    for table, indexes in expected.items():
        present = _indexed(table)
        for columns in indexes:
            assert columns in present, (table, columns, present)


def test_org_scoping_columns_present(db_engine):
    inspector = sa.inspect(db_engine)
    not_null_org = {
        "admin_user",
        "property",
        "tenancy",
        "sender_alias",
        "import_batch",
        "billing_config",
        "billing_override",
        "standard_amount_change",
        "transaction",
        "monthly_bill",
        "advance_movement",
        "utility_bill_payment",
    }
    nullable_org = {"import_profile", "utility_provider"}
    for table in not_null_org:
        columns = {c["name"]: c for c in inspector.get_columns(table)}
        assert "organization_id" in columns, table
        assert columns["organization_id"]["nullable"] is False, table
    for table in nullable_org:
        columns = {c["name"]: c for c in inspector.get_columns(table)}
        assert "organization_id" in columns, table
        assert columns["organization_id"]["nullable"] is True, table
    for table in [
        "organization",
        "room",
        "tenant",
        "tenant_access_credential",
        "tenant_session",
        "import_channel_category_mapping",
        "staged_import_row",
        "payment_allocation",
        "bill_adjustment",
    ]:
        assert "organization_id" not in {c["name"] for c in inspector.get_columns(table)}, table


def test_payment_allocation_allocation_type_check_rejects_unknown(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        txn = _make_transaction(session, org)
        bill = _make_bill(session, org, tenancy, JAN)
        session.add(
            PaymentAllocation(
                transaction_id=txn.id,
                monthly_bill_id=bill.id,
                amount_minor=10000,
                allocation_type="bogus",
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_advance_movement_type_check_rejects_unknown(db_engine):
    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        txn = _make_transaction(session, org)
        session.add(
            AdvanceMovement(
                organization_id=org.id,
                tenancy_id=tenancy.id,
                transaction_id=txn.id,
                movement_type="bogus",
                amount_minor=10000,
                occurred_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.commit()
        session.rollback()


def test_timestamps_round_trip_as_utc(db_engine):
    lagos_plus = timezone(timedelta(hours=1))
    occurred = datetime(2026, 3, 10, 14, 30, tzinfo=lagos_plus)
    paid = datetime(2026, 3, 11, 9, 15, tzinfo=timezone.utc)
    uploaded = datetime(2026, 3, 9, 8, 0, tzinfo=timezone.utc)

    with Session(db_engine) as session:
        org, tenancy = _make_chain(session)
        profile = _make_profile(session)
        batch = ImportBatch(
            organization_id=org.id,
            import_profile_id=profile.id,
            status="parsing",
            statement_fingerprint=f"fp-{uuid.uuid4().hex[:12]}",
            uploaded_at=uploaded,
        )
        session.add(batch)
        txn = Transaction(
            organization_id=org.id,
            record_category="tenant_payment",
            source="manual",
            transaction_date=date(2026, 3, 10),
            channel="FUNDING",
            direction="credit",
            description_raw="TRANSFER",
            amount_minor=100000,
            duplicate_key=f"txn-utc-{uuid.uuid4().hex[:8]}",
        )
        session.add(txn)
        session.flush()
        movement = AdvanceMovement(
            organization_id=org.id,
            tenancy_id=tenancy.id,
            transaction_id=txn.id,
            movement_type="created",
            amount_minor=60000,
            occurred_at=occurred,
        )
        session.add(movement)
        provider = UtilityProvider(
            organization_id=None,
            code=f"UTC-{uuid.uuid4().hex[:8]}",
            display_name="UTC Provider",
            channel_signature="BEDC",
        )
        session.add(provider)
        session.flush()
        utility_txn = Transaction(
            organization_id=org.id,
            record_category="utility_bill_payment",
            source="manual",
            transaction_date=date(2026, 3, 11),
            channel="BEDC",
            direction="debit",
            description_raw="BEDC PAYMENT",
            amount_minor=25000,
            duplicate_key=f"txn-utc-u-{uuid.uuid4().hex[:8]}",
        )
        session.add(utility_txn)
        session.flush()
        payment = UtilityBillPayment(
            organization_id=org.id,
            transaction_id=utility_txn.id,
            provider_id=provider.id,
            amount_minor=25000,
            payment_datetime=paid,
            spend_month=date(2026, 3, 1),
        )
        session.add(payment)
        session.commit()

        session.refresh(movement)
        assert movement.occurred_at == occurred.astimezone(timezone.utc)
        assert movement.occurred_at.tzinfo is not None
        session.refresh(payment)
        assert payment.payment_datetime == paid
        assert payment.payment_datetime.tzinfo is not None
        session.refresh(batch)
        assert batch.uploaded_at == uploaded
        assert batch.uploaded_at.tzinfo is not None

        query = sa.text("SELECT occurred_at FROM advance_movement WHERE id = :id").bindparams(
            sa.bindparam("id", value=movement.id, type_=sa.Uuid)
        )
        raw = session.execute(query).scalar()
        assert "2026-03-10 13:30" in str(raw)

        validity = sa.text("SELECT :now > :occurred").bindparams(
            sa.bindparam("now", value=paid, type_=UTCDateTime),
            sa.bindparam("occurred", value=occurred, type_=UTCDateTime),
        )
        assert session.execute(validity).scalar() in (1, True)
