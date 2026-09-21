# Quickstart / Validation Guide: Full MVP Database Schema

**Feature**: `001-database-schema` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

This is a runnable validation guide proving the schema works end-to-end. Design details live in [data-model.md](data-model.md) and [contracts/schema.md](contracts/schema.md); implementation code lives in the implementation phase (tasks.md), not here.

## Prerequisites

- Python 3.11+ environment with the project dependency set (SQLAlchemy 2.x, Alembic, pytest; psycopg for the Postgres path).
- Optionally, access to a PostgreSQL instance for the production-engine validation (SQLite covers local/dev).
- `DATABASE_URL` configurable (default: SQLite for dev).

## Setup

```bash
# 1. Create the feature database and apply the schema (SQLite dev)
alembic -c alembic.ini upgrade head

# 2. Apply idempotent seed data
./scripts/seed.py            # or `python -m app.seed`

# 3. Confirm seed is idempotent (run again, expect no-op)
./scripts/seed.py
```

For PostgreSQL, set `DATABASE_URL=postgresql+psycopg://...` and run the same `upgrade head` then seed.

## Validation scenarios

Run the test suite (pytest) which executes every scenario below against SQLite by default and can run against PostgreSQL via CI/env switch:

```bash
pytest                              # local/dev: SQLite
DATABASE_URL=postgresql+psycopg://... pytest   # production engine smoke + invariants
```

### 1. Fresh schema + reversibility (SC-005, SC-007)
- Apply `upgrade head` from empty → no errors; all 25 tables, indexes, and constraints exist (list in [data-model.md](data-model.md)).
- `alembic downgrade base` then `upgrade head` again → clean, seed-free, no errors.
- Structural equivalence: parse the applied structure and assert the table/column/constraint set matches on SQLite and PostgreSQL ([contracts/schema.md](contracts/schema.md) §1).

### 2. Seed idempotency (SC-006)
- Run seed twice → second run is a no-op (no duplicate org/admin/profile/provider/config; counts unchanged).

### 3. Money & currency (constitution Principle I)
- Insert a tenant payment with `amount_minor` (varchar/float rejected); assert the value round-trips as an integer; assert `currency` defaults to `NGN`; assert a negative `amount_minor` is rejected.

### 4. Immutability of financial tables (SC-002)
- Insert a row into each of the 7 immutable tables, then attempt `UPDATE` and `DELETE` on it.
- PostgreSQL: the operation is rejected by trigger.
- SQLite: the application layer rejects it; tests assert no update/delete path.

### 5. Commissions never stored (SC-003)
- Attempt to stage/insert a row whose `channel` maps to `COMMISSION` → rejected at CHECK (transaction/staged) or category routing (`excluded`), never persisted or logged.

### 6. Two-ledger separation (I-3)
- Insert a `utility_bill_payment` row and assert it cannot be linked to a tenancy matching state and can never spawn a `payment_allocation`; a `tenant_payment` can never be recorded as a provider payment.

### 7. Uniqueness constraints
- Second `monthly_bill` for (tenancy, month) → rejected.
- Duplicate `transaction.duplicate_key` → rejected.
- Duplicate `sender_alias (tenancy_id, normalized_name)` → rejected.
- Two active tenancies for same room → rejected (PG: partial unique; SQLite: app-layer).

### 8. Allocation cap & advance reconciliation (I-1, I-2; SC-004)
- Overpayment/partial/multi-chunk/applied-then-reversed scenarios: assert sum of signed allocations ≤ transaction amount, and `derived_unallocated == logged_advance` per `docs/04` §7.5.

### 9. Session & duplicate-statement behavior
- Session validity rule rejects after `expires_at`, `revoked_at`, or credential version bump.
- Re-importing a confirmed statement → caught by fingerprint.

## Expected outcome

All scenarios green against SQLite locally; the Postgres run additionally validates native partial indexes and immutable triggers. This satisfies spec success criteria SC-001..SC-007 and the constitution's test-first financial-logic requirement (Principle V).