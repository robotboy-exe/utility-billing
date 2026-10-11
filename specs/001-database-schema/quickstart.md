# Quickstart / Validation Guide: Full MVP Database Schema

**Feature**: `001-database-schema` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

A runnable validation guide proving the schema works end-to-end. Design details live in [data-model.md](data-model.md), [contracts/schema.md](contracts/schema.md), and [research.md](research.md); implementation code lives in the implementation phase (`tasks.md`), not here.

## Prerequisites

- Python 3.11+ with the project dependency set already in `backend/pyproject.toml` (SQLAlchemy 2.x, Alembic, psycopg, `tzdata`, pytest). No extra libraries are required.
- **Local/dev and tests use in-memory SQLite** (no server). Tests must never open the development database file (AGENTS.md).
- PostgreSQL is only needed for the CI/deploy equivalence pass. Set `TEST_DATABASE_URL=postgresql+psycopg://...` to run the same suite there.

## Setup

```bash
# From the repository root, using the project virtual environment:
.venv/bin/python -m pytest tests -q            # in-memory SQLite, full suite

# Apply the baseline to a SQLite dev database and seed it (manual smoke):
.venv/bin/alembic -c backend/src/migrations/alembic.ini upgrade head
.venv/bin/python -m backend.src.seed           # or the seed entrypoint
.venv/bin/python -m backend.src.seed           # run again: expect a no-op

# PostgreSQL equivalence path (CI/deploy, not local):
DATABASE_URL=postgresql+psycopg://... .venv/bin/alembic -c backend/src/migrations/alembic.ini upgrade head
TEST_DATABASE_URL=postgresql+psycopg://... .venv/bin/python -m pytest tests -q
```

Tests are one file per user story: `tests/test_identity.py` (US1), `test_tenancy.py` (US2), `test_ingestion.py` (US3), `test_ledgers_billing.py` (US4), `test_settings.py` (US5), `test_audit.py` (US6), `test_seed.py` (US7), `test_migration.py` (US8). Run one task's tests at a time, e.g. `.venv/bin/python -m pytest tests/test_tenancy.py::test_one_active_tenancy -q`.

## Validation scenarios

### 1. Fresh schema + reversibility (SC-001, SC-008, SC-010)
- Apply `upgrade head` from empty; all 28 tables, indexes, constraints, partial indexes, and triggers exist (`docs/04` §6, §9).
- `downgrade base` then `upgrade head` again → clean, no leftover objects.
- Structural equivalence: the same suite passes on SQLite and PostgreSQL (PostgreSQL in CI). Table/constraint parity is asserted.

### 2. Seed idempotency (SC-009)
- Run the seed twice → the second run is a no-op (one org, admin, `PAYVICE_AVANTUS` profile + mappings, `BEDC` provider, default `billing_config`, default portal settings; counts unchanged).

### 3. Money & currency (SC-004; Principle I)
- `amount_minor` round-trips as an integer with no float loss; `currency` defaults to `NGN`; a negative magnitude is rejected (CHECK) where `docs/04` requires `>= 0`.

### 4. Immutability of financial tables (SC-003; Principle I)
- Insert a row into each of the seven immutable tables, then attempt `UPDATE` and `DELETE`; both are rejected by **database triggers on SQLite and PostgreSQL** (R-5).

### 5. Commissions never stored (SC-006; Principle III)
- Attempt to stage/insert a row whose channel maps to `COMMISSION` → rejected (CHECK on `transaction`/`staged_import_row`, or `excluded` routing), never persisted or logged.

### 6. Two-ledger separation (SC-007; Principle IV)
- A `utility_bill_payment` cannot carry tenancy-matching state and can never spawn a `payment_allocation`; a `tenant_payment` can never be recorded as a provider payment.

### 7. Uniqueness & partial indexes (SC-002)
- Second `monthly_bill` for (tenancy, month) → rejected.
- Duplicate `transaction.duplicate_key` → rejected.
- Duplicate `sender_alias (tenancy_id, normalized_name)` → rejected.
- Two active tenancies for the same room → rejected by the partial unique index on **both** engines (R-4).
- Re-imported confirmed statement fingerprint → rejected by the partial unique index on `import_batch`.

### 8. Allocation cap & advance reconciliation (I-1, I-2)
- Overpayment/partial/multi-chunk/applied-then-reversed scenarios: assert the sum of signed allocations ≤ the transaction amount, and `derived_unallocated == logged_advance` per `docs/04` §7.5.

### 9. Session & timezone behavior
- `organization.timezone` defaults to `Africa/Lagos`; the `Organization` model carries a model-layer IANA validator (spec FR-026).
- Session validity rules reject after `expires_at`, `revoked_at`, or a credential-version bump; `expires_at` stays fixed after use.

## Expected outcome

All scenarios green on in-memory SQLite locally, including native partial-index and trigger enforcement; the PostgreSQL CI run additionally confirms engine equivalence. This satisfies spec success criteria SC-001..SC-010 and the constitution's test-first financial-logic requirement (Principle V).
