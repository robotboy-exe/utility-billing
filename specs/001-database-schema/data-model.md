# Data Model: Full MVP Database Schema

**Feature**: `001-database-schema` | **Date**: 2026-10-10 | **Authoritative source**: `docs/04-database.md` (all 29 tables, columns, constraints, indexes, enums, invariants).

This document is **only** the table-to-module map plus the cross-cutting rules. It deliberately does **not** restate columns, types, or per-table constraints — those live in `docs/04` §6 and are referenced by section here. The ORM models, the baseline migration, and the seed must satisfy `docs/04` exactly; no table, column, constraint, or index may be invented, renamed, or dropped.

**Engine/type decisions** (details in [research.md](research.md)): UUID PKs app-side `uuid4` (R-6); one shared UTC-aware datetime type on every `*_at` column (R-2); money via shared helpers (R-3); enums TEXT + CHECK (R-1); partial unique indexes declared for both `sqlite_where` and `postgresql_where` (R-4); immutable tables blocked by triggers on both engines from one shared DDL (R-5).

## 1. Table → module map (all 29 tables)

Every table below appears in exactly one module and one user story; `docs/04` §6 remains the column contract.

| Table | Module | File | User story | `docs/04` |
|---|---|---|---|---|
| `organization` | identity | `backend/src/models/identity.py` | US1 | §6.2 |
| `admin_user` | identity | `backend/src/models/identity.py` | US1 | §6.1 |
| `property` | tenancy | `backend/src/models/tenancy.py` | US2 | §6.2 |
| `room` | tenancy | `backend/src/models/tenancy.py` | US2 | §6.2 |
| `tenancy` | tenancy | `backend/src/models/tenancy.py` | US2 | §6.3 |
| `tenant` | tenancy | `backend/src/models/tenancy.py` | US2 | §6.3 |
| `sender_alias` | tenancy | `backend/src/models/tenancy.py` | US2 | §6.3 |
| `tenant_access_credential` | tenancy | `backend/src/models/tenancy.py` | US2 | §6.1 |
| `tenant_session` | tenancy | `backend/src/models/tenancy.py` | US2 | §6.1 |
| `import_profile` | ingestion | `backend/src/models/ingestion.py` | US3 | §6.7 |
| `import_channel_category_mapping` | ingestion | `backend/src/models/ingestion.py` | US3 | §6.7 |
| `import_batch` | ingestion | `backend/src/models/ingestion.py` | US3 | §6.7 |
| `staged_import_row` | ingestion | `backend/src/models/ingestion.py` | US3 | §6.7 |
| `billing_config` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.4 |
| `billing_override` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.4 |
| `standard_amount_change` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.4 |
| `transaction` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.5 |
| `transaction_match` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.5 |
| `monthly_bill` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.5 |
| `payment_allocation` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.5 |
| `advance_movement` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.5 |
| `bill_adjustment` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.5 |
| `utility_provider` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.6 |
| `utility_bill_payment` | ledgers & billing | `backend/src/models/ledgers_billing.py` | US4 | §6.6 |
| `portal_setting` | settings | `backend/src/models/settings.py` | US5 | §6.8 |
| `audit_log` | audit | `backend/src/models/audit.py` | US6 | §6.9 |
| `admin_session` | audit | `backend/src/models/audit.py` | US6 | §6.1 |
| `admin_login_attempt` | audit | `backend/src/models/audit.py` | US6 | §6.1 |
| `tenant_login_attempt` | audit | `backend/src/models/audit.py` | US6 | §6.1 |

Count check (spec Assumptions, SC-001): `2 + 7 + 4 + 11 + 1 + 4 = 29` tables, matching `docs/04` §6.1–§6.9.

## 2. Module boundaries

- `backend/src/models/base.py` — **not a domain module**: shared mixins (UUID PK + `created_at`; organization scoping; `updated_at`), the shared UTC-aware datetime type, the `money()`/`currency()` helpers, and the registration that emits the immutable-table trigger DDL (R-2, R-3, R-5, R-8).
- `backend/src/enums.py` — the `docs/04` §4 value sets expressed for Python use, plus the `TEXT` + CHECK column behavior (R-1).
- Domain modules import only from `base.py`, `enums.py`, and earlier dependency modules; they carry no business logic (billing/ingestion/UI logic is out of scope, spec FR-025).
- Cross-module references are foreign keys only (`docs/04` §6). The `ledgers & billing` module is the only one that spans money-bearing tables of both ledgers; strict ledger separation is preserved structurally (see §3).

## 3. Cross-cutting rules (referenced, not restated)

Each rule is enforced by the cited `docs/04` section; columns/constraints are defined there.

- **Primitives**: UUID primary keys (`docs/04` §3.1); `created_at` on every table and `updated_at` only on mutable tables (`docs/04` §3.2, §11.2); all instants stored UTC (ADR-028) through the shared type (R-2).
- **Money**: integer `BIGINT` minor units, no floating point; `currency CHAR(3)` on money-bearing persisted tables (`docs/04` §3.4–§3.5); transient staging tables carry no currency.
- **Enumerations**: `TEXT` + `CHECK`, including the inline value sets (`docs/04` §4, §6) (R-1).
- **Organization scoping**: `organization_id` on the scoped tables and all scoped queries filter by it (`docs/04` §2.5, §8.9; R-8).
- **Organization timezone**: stored as an IANA `TEXT` string defaulting to `Africa/Lagos`; the model validates it as a valid IANA name before persistence (`docs/04` §6.2; spec FR-026).
- **Immutability**: the eight append-only tables (`docs/04` §11.1) reject `UPDATE`/`DELETE` via triggers on both engines, from one shared DDL (R-5). The mutable set is exactly `docs/04` §11.2; the five write-once operational tables are excluded there (`tenant_session`, `admin_session`, `staged_import_row`, `tenant_login_attempt`, `admin_login_attempt`).
- **Partial unique indexes**: `tenancy` (`UNIQUE (room_id) WHERE status = 'active'`), `import_batch` (`UNIQUE (statement_fingerprint) WHERE status IN ('confirmed','completed')`), `billing_config` (`UNIQUE (organization_id) WHERE property_id IS NULL`, one org-wide default row per organization), and `transaction_match` (`UNIQUE (reverses_match_id) WHERE reverses_match_id IS NOT NULL`) are declared with both `sqlite_where` and `postgresql_where` (`docs/04` §6.3, §6.4, §6.7, §8.5, §10.2, §13 item 4; §6.5 for `transaction_match`; R-4).
- **Ledger separation**: the two ledgers are structurally distinct and cannot cross-settle; `utility_bill_payment` has no tenancy-matching state and ties one-to-one to its source transaction (`docs/04` §6.5–§6.6, §8.3; ADR-017).
- **Commissions never stored**: the `transaction.record_category` and `staged_import_row.row_category` CHECK constraints admit only persistable categories, and `COMMISSION` maps to `excluded` (`docs/04` §6.5, §6.7, §8.4; constitution Principle III).
- **Derived state not stored**: bill status, bill remaining, tenancy outstanding, advance balance, net position, and utility spend are computed from the authoritative tables (`docs/04` §7); no independently mutable copies.
- **Duplicate-detection keys**: only `transaction.duplicate_key` is unique; `staged_import_row.duplicate_key` is not unique so `parse_status = 'duplicate'` rows remain stageable; `import_batch.statement_fingerprint` carries its partial unique index (`docs/04` §6.7, §10.1–§10.2).
- **Indexes**: the recommended non-unique indexes (`docs/04` §9) are applied as documented.
- **Audited bill changes**: any change to `monthly_bill.final_amount_minor` requires a `bill_adjustment` row; the schema supplies the columns/keys and the billing-engine feature enforces it (`docs/04` §6.5, §8.7).

## 4. Invariant → enforcement map

| Invariant (`docs/04` §8) | Enforcement in this feature |
|---|---|
| Allocation cap (I-1) | Columns/FKs enabling the computation; verified by test (engine enforces in the billing feature) |
| Advance reconciliation (I-2) | Append-only `advance_movement` + `transaction`/`payment_allocation` columns; verified by test |
| Ledger separation (I-3) | Schema structure + tests |
| Commissions never stored (I-4) | CHECK constraints + category mapping + tests |
| One active tenancy per room (I-5) | Partial unique index on both engines (R-4) + tests |
| One bill per tenancy per month (I-6) | Unique constraint + tests |
| Bill amount changes audited (I-7) | Keys/columns + test; enforced by the billing feature |
| Advance movement atomic with allocation (I-8) | Shared transaction boundary; enforced by the billing feature |
| Organization scoping (I-9) | Scoping mixin + query discipline + tests |
| One org-wide billing_config per organization (`docs/04` §8 item 10) | Partial unique index `UNIQUE (organization_id) WHERE property_id IS NULL` on both engines (R-4) + tests |

## 5. Packaging

- `backend/src/seed.py` — idempotent seed for exactly the rows in `docs/04` §12 (US7).
- `backend/src/migrations/` — Alembic baseline delivering all tables, constraints, indexes, partial indexes, and triggers (US8), reversible up/down.
- Tests: repository-root `tests/`, one file per user story (see plan.md "Project Structure").
