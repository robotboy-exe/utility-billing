# Implementation Plan: Full MVP Database Schema

**Branch**: `001-database-schema` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-database-schema/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

Implement the complete database layer for the Utility Billing MVP as SQLAlchemy models plus a single reversible Alembic baseline migration and idempotent seed, satisfying every entity, constraint, index, enum, derived-state computation, and immutability rule in `docs/04-database.md`. PostgreSQL is the production engine (native partial unique indexes and immutable-table triggers live here); SQLite is the local/dev/test engine. Technical decisions are captured in [research.md](research.md); the data model in [data-model.md](data-model.md); the DB contract in [contracts/schema.md](contracts/schema.md); runnable validation in [quickstart.md](quickstart.md).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: SQLAlchemy 2.x (2.0-style declarative), Alembic, psycopg (PostgreSQL), SQLite stdlib (dev), pytest

**Storage**: PostgreSQL (production), SQLite (local development & tests)

**Testing**: pytest; full suite on SQLite locally, PostgreSQL run for smoke + invariant validation (constitution Principle V)

**Target Platform**: Linux free-tier host (deployment) + local dev

**Project Type**: backend data layer (SQLAlchemy models + migrations), part of a FastAPI web-service

**Performance Goals**: Light MVP load (`docs/03` §14.5); no high-throughput targets; correctness prioritized over scale

**Constraints**: Free hosting (no workers/schedulers); money as `BIGINT` minor units + `currency CHAR(3)` (no floats); append-only financial tables; org-scoped queries; PostgreSQL/SQLite parity except two documented divergences (R-4 partial indexes, R-5 immutable triggers)

**Scale/Scope**: Single org MVP; 25 tables + seed

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I — Financial correctness & immutable history**: Conforms. Money = `BIGINT` minor units + explicit `currency` (R-8); financial tables append-only (R-5); no stored mutable advance balance (derived; §7.4/7.5); corrections via reversal/correction rows. **PASS**
- **Principle II — Billing engine independence**: Not materially affected by schema delivery; models do not hardcode source/billing rules. **PASS**
- **Principle III — Ingestion reliability & integrity**: Conforms. Staged/confirmed ingestion; duplicate keys (10.1, §10); commissions never stored (CHECK + category mapping, invariant I-4); category mapping config-driven. **PASS**
- **Principle IV — Two-ledger separation**: Conforms. Structural separation + tests (I-3); utility payments never settle tenant bills nor enter matching. **PASS**
- **Principle V — Test-first financial logic**: Conforms. Allocation cap, advance reconciliation, and ingestion edge cases are in the test plan (quickstart §8; research R-10). **PASS**
- **Database & Schema discipline**: Conforms. UUID PKs (R-2); org scoping mixin (R-9, I-9); every change ships as reversible Alembic migration (R-7); derived state computed not stored; immutability classification honored; audited bill-amount changes (I-7); PostgreSQL prod / SQLite dev. **PASS**

**Gate result**: All gates **PASS**; no requirement is violated that would require a justification. `Complexity Tracking` below is therefore left empty.

### Post-design re-check

Re-evaluated after data-model/contracts/quickstart design (R-1…R-10):
- All money remains integer minor units + currency (R-8); no float introduced.
- All 7 financial tables remain append-only (R-5, §5 contracts).
- The two accepted divergences (partial indexes and immutable triggers app-layer on SQLite) still enforce the same invariants via app-layer + tests; production PostgreSQL retains native integrity — is this a violation? No: the production DB is the source of truth and keeps native enforcement; SQLite is dev-only. Conforms with documents/§8 service-layer stance. **PASS**
- **Locked execution (2026-09-21)**: first implementation pass = **User Story 1 only** (MVP); **SQLite is the only locally-validated engine**, with PostgreSQL-native DDL (partial indexes, immutable triggers, SC-007 equivalence) authored now but validated in CI/deploy rather than locally. This does not change the conforming conclusion above (SQLite app-layer + tests preserve the invariants locally; Postgres proves them natively in CI). **PASS**

## Project Structure

### Documentation (this feature)

```text
specs/001-database-schema/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── schema.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
└── src/
    ├── models/            # SQLAlchemy models, grouped by domain (mirrors docs/04 §6)
    │   ├── base.py        # mixins: IdCreatedAt, OrgScoped, UpdatedAt; money()/currency() helpers
    │   ├── identity.py    # admin_user, tenant_access_credential, tenant_session
    │   ├── org.py         # organization, property, room
    │   ├── tenancy.py     # tenancy, tenant, sender_alias
    │   ├── billing.py     # billing_config, billing_override, standard_amount_change,
    │   │                  #   monthly_bill, payment_allocation, bill_adjustment
    │   ├── ledger.py      # transaction, advance_movement
    │   ├── utility.py     # utility_provider, utility_bill_payment
    │   ├── ingestion.py   # import_profile, import_channel_category_mapping,
    │   │                  #   import_batch, staged_import_row
    │   └── settings.py    # portal_setting, audit_log
    ├── enums.py           # enum.StrEnum definitions (docs/04 §4)
    ├── db.py              # engine/session config (Postgres/SQLite), DATABASE_URL
    ├── seed.py            # idempotent seed (docs/04 §12)
    └── migrations/        # Alembic
        ├── env.py
        └── versions/
            └── 0001_initial_schema.py   # single reversible baseline + triggers/partial indexes

tests/
├── conftest.py            # SQLite per-test DB (and Postgres-capable)
├── test_schema.py         # SC-00x structural/reversibility/equivalence
├── test_seed.py           # SC-006 idempotent seed
├── test_money.py          # Principle I money/currency
├── test_immutable.py      # SC-002 append-only
├── test_separation.py     # I-3 two-ledger
├── test_invariants.py     # I-1 allocation cap, I-2 advance reconciliation
└── test_uniqueness.py     # active tenancy, bill-per-month, duplicate keys
```

**Structure Decision**: **Single `backend/` project** (Option 2 trimmed to the data layer). The constitution locks a Python + FastAPI backend (`03` §6.6); this feature delivers only the database/data-access slice of it (`models/`, `enums.py`, `db.py`, `seed.py`, `migrations/`) plus tests. The frontend (`frontend/`) and API layer are separate features and are intentionally absent here. Models are grouped by domain per `docs/03` §6.7 modules to honor domain isolation and keep each module independently reviewable/testable. `contracts/schema.md` documents the DB-level contract.

## Complexity Tracking

> Filled ONLY if Constitution Check has violations that must be justified

No Constitution Check violations. Section intentionally empty.