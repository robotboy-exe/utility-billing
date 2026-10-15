# Research: Full MVP Database Schema (Phase 0)

**Feature**: `001-database-schema` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

This document resolves the Technical Context unknowns for implementing the schema defined in `docs/04-database.md` as SQLAlchemy 2.x models plus a single reversible Alembic baseline, targeting **PostgreSQL (production/CI)** and **SQLite (local/tests)**. `docs/04` is the only definition of tables and columns; this document records *how* the schema is expressed, not *what* the schema is.

**Scope guard**: no API, UI, or auth logic ships in this feature (`docs/04` §1, §12; spec FR-025). Every decision below is about the persistence layer only.

## Required decisions

Each item below was called out in the plan input and records a one-line rationale plus the cost of changing the decision later.

### R-1 — Enumerations are TEXT + CHECK

- **Decision**: Every enumeration is a `TEXT` column with a `CHECK` constraint listing the allowed values, on both SQLite and PostgreSQL, including the four inline value sets in `docs/04` §6 (`billing_override.decision`, `bill_adjustment.adjustment_type`, `staged_import_row.parse_status`, `audit_log.actor_type`).
- **Rationale**: identical behavior on both engines, no lookup tables, no native-enum type lock-in; the values are the contract (`docs/04` §4).
- **Cost of changing later**: every enum-bearing table and its CHECK must migrate on both engines, and any already-stored value must be remapped; adding one value is one constraint-replacement migration per enum.
- **Alternatives considered**: native PostgreSQL `ENUM` (engine-locked, no SQLite parity, `ALTER TYPE` locking); lookup tables (extra joins for closed sets).

### R-2 — One shared UTC-aware datetime column type

- **Decision**: a single shared `TypeDecorator` over `DateTime(timezone=True)` is used by **every** `*_at` timestamp column; on bind it coerces to timezone-aware UTC, and on result it returns a timezone-aware UTC datetime.
- **Rationale**: SQLite round-trips timestamps naively, so a stray naive value would raise on comparison with an aware one; one shared type makes that impossible and keeps all instants UTC (`docs/04` §3.2, ADR-028).
- **Cost of changing later**: touches every timestamp column and every persisted instant; needs a migration rewriting the column type/values on both engines and re-validation of the month-boundary computations.
- **Alternatives considered**: raw `DateTime(timezone=True)` per column (SQLite returns naive → comparison bugs); naive-UTC columns with ad-hoc handling at call sites (leaks across the codebase).

### R-3 — Money as integer minor units via shared helpers

- **Decision**: every monetary value is an integer `BIGINT` minor unit built through a shared `money()` column helper (per-column CHECK `>= 0` or `> 0` exactly as `docs/04` states) with an adjacent shared `currency()` helper (`CHAR(3) NOT NULL`, default the MVP currency).
- **Rationale**: turns `docs/04` §3.4–§3.5 and constitution Principle I into one reusable pattern, so no float can enter any money column.
- **Cost of changing later**: every money-bearing table, its CHECK, and its currency column migrate together; a change to the magnitude/rounding semantics also requires a data conversion.
- **Alternatives considered**: hand-authored `BIGINT` per column (drift and omission risk); a custom Money type (over-abstraction for the MVP).

### R-4 — Partial unique indexes declared for both engines

- **Decision**: partial unique indexes are declared with **both** `sqlite_where` and `postgresql_where` — `tenancy` (`UNIQUE (room_id) WHERE status = 'active'`; `docs/04` §6.3, §8.5), `import_batch` (`UNIQUE (statement_fingerprint) WHERE status IN ('confirmed','completed')`; `docs/04` §6.7, §10.2), `billing_config` (`UNIQUE (organization_id) WHERE property_id IS NULL`; `docs/04` §6.4), and `transaction_match` (`UNIQUE (reverses_match_id) WHERE reverses_match_id IS NOT NULL`; `docs/04` §6.5, §8.11). The first three are registered in `docs/04` §9 and §13 item 4, which specify `sqlite_where` locally and `postgresql_where` in production; the fourth is defined in `docs/04` §6.5 and uses the same pair.
- **Rationale**: SQLite has supported partial indexes since 3.8.0, so both engines enforce the invariants natively and they are verifiable locally, replacing the earlier PostgreSQL-only/app-layer divergence.
- **Cost of changing later**: drop and recreate the indexes on both engines and re-verify; any stopgap app-layer guard must be removed.
- **Alternatives considered**: PostgreSQL-only partial index plus a SQLite application-layer guard (weaker, service-layer tested only — the previous approach); a composite `(room_id, status)` index (wrongly blocks historical closed tenancies).

### R-5 — Immutable tables blocked by triggers on both engines from one shared DDL

- **Decision**: the eight immutable tables (`docs/04` §11.1 — `transaction`, `transaction_match`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `utility_bill_payment`, `audit_log`) are protected against in-place `UPDATE`/`DELETE` by database triggers on **both** engines, and the trigger DDL is defined **once** in a shared helper that is emitted both by SQLAlchemy events during `metadata.create_all()` and by the Alembic baseline migration, so tests and migrations cannot differ.
- **Feasibility**: **feasible.** SQLite uses `CREATE TRIGGER ... BEFORE UPDATE/DELETE ... BEGIN SELECT RAISE(ABORT, '...'); END;`. PostgreSQL uses one shared `CREATE OR REPLACE FUNCTION` returning `trigger` plus per-table `CREATE TRIGGER ... EXECUTE FUNCTION`. Both forms are produced by the same Python helper, branched by dialect.
- **Rationale**: a single DDL source means the SQLite triggers exercised by tests and the PostgreSQL triggers applied by the migration are literally the same definition (`docs/04` §11.1; constitution Principle I; spec FR-016, SC-003).
- **Cost of changing later**: triggers must be dropped/recreated in a migration; editing the guard means editing the shared DDL and re-running both paths; a future per-table mutable exception requires parameterizing the helper.
- **Alternatives considered (kept on record; not needed because the approach is feasible)**: (1) PostgreSQL-only triggers + SQLite application-layer guards — would let tests pass without database enforcement locally; (2) ORM `before_update`/`before_delete` event guards only — bypassable by raw SQL, weaker than "database level"; (3) a trigger script run outside both paths — creates exactly the tests-vs-migrations drift the input forbids.

## Supporting decisions

### R-6 — UUID primary keys

- **Decision**: portable UUID PK type with an application-side `default=uuid.uuid4`; no server-side default.
- **Rationale**: every write goes through the ORM, so one app-side default is identical on both engines; PostgreSQL has `gen_random_uuid()` but SQLite does not (`docs/04` §3.1).
- **Alternatives considered**: server-side defaults per engine (dual source of truth, parity break).

### R-7 — JSON columns

- **Decision**: `sa.JSON().with_variant(postgresql.JSONB(), "postgresql")` (the `jsonb()` helper in `backend/src/models/base.py`) for the JSONB columns (`import_profile.detection_config|parse_config|file_limits`, `import_batch.ignored_summary`, `audit_log.metadata`).
- **Rationale**: the variant renders `JSONB` on PostgreSQL and `JSON` text on SQLite with no custom DDL (plain `sa.JSON` would render `JSON` on PostgreSQL) (`docs/04` §6.7, §6.9).
- **Alternatives considered**: hand-rolled per-engine DDL (unnecessary).

### R-8 — Shared foundation and organization scoping

- **Decision**: shared mixins — UUID PK + `created_at`; an optional `organization_id` FK mixin; and an `updated_at` mixin applied only to the mutable tables of `docs/04` §11.2. The shared UTC-aware type (R-2), `money()`/`currency()` (R-3), and the immutability-DDL registration (R-5) live in the same base module.
- **Rationale**: makes `docs/04` §2/§3/§8.9 conventions structural and non-duplicative.
- **Alternatives considered**: per-model hand-authoring (inconsistency).

### R-9 — Seed data mechanism

- **Decision**: an idempotent seed step (upsert keyed on natural identifiers), separate from the migration, delivering exactly the rows in `docs/04` §12.
- **Rationale**: keeps migrations pure/reversible DDL; re-runnable without duplicates (spec SC-009).
- **Alternatives considered**: data inside the baseline migration (ties reversibility to data state).

### R-10 — Migration packaging

- **Decision**: one reversible baseline migration creating all 29 tables, constraints, indexes, partial unique indexes (R-4), and triggers (R-5), in FK creation order.
- **Rationale**: nothing is deployed yet, so per-module splitting buys no benefit; one baseline keeps up/down deterministic (`docs/04` §12; `docs/03` §6.6).
- **Alternatives considered**: one migration per domain (pre-deployment over-engineering).

### R-11 — Testing and database isolation

- **Decision**: `pytest` with a **fresh in-memory SQLite database per test** by default; the same suite can run against PostgreSQL in CI. Tests never point at the development database file (AGENTS.md).
- **Rationale**: runs the full suite locally with no server; PostgreSQL is exercised in CI where the native triggers and partial indexes are applied by the migration.
- **Alternatives considered**: PostgreSQL-only testing (not dev-friendly); manual verification (violates Principle V).

## Libraries

No library is required beyond those already in `backend/pyproject.toml`: SQLAlchemy 2.x, Alembic, psycopg (PostgreSQL), `tzdata`, pytest, pytest-sqlalchemy (dev: ruff, mypy, pre-commit). SQLite is stdlib. The SQLite and PostgreSQL trigger DDL (R-5) needs no additional dependency.

## Open questions

Anything still genuinely open lives in `docs/04` §13; this feature adds none.
