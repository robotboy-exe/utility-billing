# Research: Full MVP Database Schema (Phase 0)

**Feature**: `002`-scoped no — `001-database-schema` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

This document resolves the unknowns listed in Technical Context (plan.md) for implementing the full schema from `docs/04-database.md` as SQLAlchemy models + Alembic migrations, with PostgreSQL for production and SQLite for local development/testing. Every decision is grounded in `docs/04`, the ratified constitution, and the locked ADRs.

**Locked execution decisions (2026-09-21)**:
- **First implementation pass = User Story 1 only** (Structural & Identity Foundation), per tasks.md MVP strategy.
- **SQLite is the only engine validated locally** (no local PostgreSQL on the dev machine). Postgres-native DDL (immutable triggers, `postgresql_where` partial unique indexes) is authored in the code but **validated in CI/deploy**, not locally. All decisions below are therefore phrased so the SQLite path is locally runnable and complete for US1.

---

## R-1: Enum strategy

- **Question**: Native database `ENUM` vs lookup tables vs VARCHAR + CHECK? (`docs/04` §4 says "database enums or lookup tables; the values are the contract.")
- **Decision**: Implement each enum as a Python `enum.StrEnum` and a SQLAlchemy `Enum(EnumClass, native_enum=False, ...)` column — i.e. a `VARCHAR` column backed by a `CHECK` constraint listing the values.
- **Rationale**: SQLite has no native enums; `native_enum=False` yields portable VARCHAR + CHECK on both engines. It also avoids Postgres `ENUM` type-locking concerns on production tables (`docs/04` §12). The values remain a hard contract via both the Python enum and the CHECK.
- **Alternatives considered**: Native PG `ENUM` (locks on alter, no SQLite parity); lookup tables (extra joins, no benefit for closed value sets).

## R-2: UUID primary keys

- **Question**: How are UUID PKs defaulted given Postgres (`gen_random_uuid()`) vs SQLite (none)?
- **Decision**: Use SQLAlchemy `Uuid` (or `postgresql.UUID`-compatible portable type) with an **application-side** `default=uuid.uuid4`. No reliance on a server-side default.
- **Rationale**: Every write path goes through the ORM, so an app-side default is sufficient and identical on both engines. Server-side default would diverge (Postgres has `gen_random_uuid()`, SQLite does not).
- **Alternatives considered**: `server_default=text("gen_random_uuid()")` on Postgres only (breaks parity and dual source of default).

## R-3: JSONB and timestamp parity

- **Question**: `docs/04` uses `JSONB` and `timestamptz` (Postgres-native) but must also run on SQLite.
- **Decision**: Use SQLAlchemy `JSON` for the three config/metadata JSONB columns (`import_profile.detection_config|parse_config|file_limits`, `import_batch.ignored_summary`, `audit_log.metadata`) and `DateTime(timezone=True)` for all `*_at` columns.
- **Rationale**: `sa.JSON` renders as `JSONB` on Postgres and JSON text on SQLite automatically; `DateTime(timezone=True)` renders `TIMESTAMPTZ` on Postgres and timezone-aware datetime on SQLite. Parity with no custom DDL branching.
- **Alternatives considered**: Hand-rolled JSONB branch per engine (unnecessary; SQLAlchemy handles it).

## R-4: Partial unique index portability (active tenancy, statement fingerprint)

- **Question**: `docs/04` §8.5 (`UNIQUE (room_id) WHERE status='active'`) and §10.2 (`UNIQUE (statement_fingerprint) WHERE status IN ('confirmed','completed')`) require **partial** unique indexes, which SQLite does not support (`docs/04` §13 Q4).
- **Decision**: 
  - **Postgres**: real partial unique indexes via `postgresql_where=...` on `UniqueConstraint`/`Index`.
  - **SQLite**: no partial index; enforce the identical invariants in the **application/service layer** and cover them in tests.
- **Rationale**: Postgres gets native integrity (the production DB is the source of truth per constitution); SQLite is dev-only and the invariant is still guaranteed by app-layer checks + tests. This matches `docs/04` §8's stance that row-spanning invariants are enforced in the service layer within transactions.
- **Alternatives considered**: Composite `(room_id, status)` unique index (rejects multiple closed historical tenancies — incorrect); giving up the invariant on SQLite (unacceptable).
- **Divergence note**: Recorded in `contracts/schema.md` and `quickstart.md`; invariants are tested equivalently on both engines. PostgreSQL partial indexes are authored in the code now but exercised in CI/deploy (no local Postgres).

## R-5: Immutable (append-only) table write enforcement

- **Question**: How do the 7 immutable financial tables (`transaction`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `utility_bill_payment`, `audit_log`) reject in-place UPDATE/DELETE (spec SC-002)?
- **Decision**: **Postgres** `BEFORE UPDATE` / `BEFORE DELETE` triggers (raise exception) on the immutable tables; **SQLite** relies on application-layer guards plus tests asserting no ORM UPDATE/DELETE path exists. Postgres triggers are authored now but validated in CI/deploy (not locally).
- **Rationale**: Satisfies SC-002's "reject at the storage layer" literally on production Postgres while keeping SQLite simple. Append-only is a policy enforced by schema; corrections go through reversal/correction rows (`docs/04` §11.1, constitution Principle I).
- **Alternatives considered**: App-layer only (fails SC-002 "storage layer" wording); SQLite triggers too (optional — kept app-layer for simplicity; documented).

## R-6: Seed data mechanism

- **Question**: How to deliver MVP seed (`docs/04` §12): default org, admin, global `PAYVICE_AVANTUS` profile + channel/category mappings, global `BEDC` provider, default org-wide `billing_config`, default portal settings?
- **Decision**: A **separate idempotent seed step** (upsert keyed on natural identifiers), run after migrations, not baked into the Alembic migration.
- **Rationale**: Keeps migrations pure, reversible DDL; seeding is idempotent (spec SC-006) and safe to re-run on existing DBs. The org-wide standard amount is admin-configurable and required before first lazy bill generation (`docs/04` §12).
- **Alternatives considered**: Alembic data migration (mixes data with DDL, ties reversibility to data state); hybrid split (extra moving parts, no benefit for MVP).

## R-7: Alembic migration packaging

- **Question**: One vs multiple migrations for a from-scratch schema.
- **Decision**: **Single reversible baseline migration** creating all tables + indexes + triggers, respecting FK creation order, followed by the idempotent seed.
- **Rationale**: Nothing is deployed yet; per-module migration splitting buys versioning ability only for an existing live schema (`docs/04` §12 ships every change as a migration going forward). One baseline keeps up/down deterministic (spec SC-005).
- **Alternatives considered**: One-migration-per-domain (over-engineering pre-deployment; fragmentation for no benefit).

## R-8: Money and currency pattern

- **Question**: How to prevent float money and enforce the `_minor` + `currency CHAR(3)` convention (`docs/04` §3.4–§3.5)?
- **Decision**: Provide shared column/value helpers — a `money` column factory (`sa.BigInteger` with `CHECK (x >= 0)` where doc says `>= 0`, or `> 0`) and a `currency` column factory (`sa.Char(3) NOT NULL`, default `"NGN"`) — applied to every money-bearing table so the convention is structural, not ad hoc.
- **Rationale**: Converts a prose rule into a reusable, reviewable pattern (constitution Principle I). No floats anywhere.
- **Alternatives considered**: Reproducing BIGINT by hand per column (drift risk); a full custom money type (over-abstraction for MVP).

## R-9: Shared foundation & organization scoping

- **Question**: How to enforce common columns (UUID PK, `organization_id` scoping, `created_at`/`updated_at`) consistently (`docs/04` §2, §3, §8.9)?
- **Decision**: Define shared **mixin classes** — an `IdCreatedAtMixin` (id, created_at), an optional `OrgScopedMixin` (organization_id FK), and an `UpdatedAtMixin` (updated_at, applied only to mutable tables) — reused across models.
- **Rationale**: Makes the §3 conventions and §8.9 (organization scoping on all scoped queries) structural and non-duplicative; matches the module boundaries in `docs/03` §6.7.
- **Alternatives considered**: Hand-authoring columns per model (inconsistency/risk).

## R-10: Testing & DB isolation

- **Question**: How to validate constraints per constitution Principle V (test-first financial logic)?
- **Decision**: pytest suite with a fresh SQLite database per test (in-memory or tmp file); the same test suite can run against Postgres for a smoke/CI pass.
- **Rationale**: SQLite runs the full suite locally/dev without a server; Postgres is validated in the deployment/CI path where the partial indexes and immutable triggers are real. All financial invariants (advance reconciliation, allocation cap, ledger separation) are covered by tests on both engines.
- **Alternatives considered**: Postgres-only testing (not dev-friendly); manual verification (violates test-first).

---
**Result**: All Technical Context unknowns in plan.md are now resolved. No `NEEDS CLARIFICATION` remain.