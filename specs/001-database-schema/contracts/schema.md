# Schema Contract: Full MVP Database Schema

**Feature**: `001-database-schema` | **Date**: 2026-09-21

This is the DB-level contract the ORM models, migration, and seed must uphold. It is the interface between the data-access layer and the database engines. For full entity/column detail see [data-model.md](../data-model.md) and the authoritative `docs/04-database.md`.

## Purpose & scope

Types of contract captured here:
- Data types and their per-engine rendering.
- Enumerated values (the value set is the contract — see R-1).
- Uniqueness, CHECK, and partial-unique constraints ("the values are the contract").
- The immutability (append-only) contract.
- Engine parity: what is identical on PostgreSQL and SQLite, and the two documented divergences.

## 1. Data type contract

| Logical type | SQLAlchemy | PostgreSQL | SQLite (dev) |
|---|---|---|---|
| Primary key | `Uuid` / `postgresql.UUID`, `default=uuid.uuid4` | UUID | TEXT/BLOB (UUID) |
| Money | `BigInteger` via `money()` helper (CHECK per column) | BIGINT | INTEGER |
| Currency | `Char(3)` via `currency()` helper, default `"NGN"` | CHAR(3) | TEXT |
| Timestamp | `DateTime(timezone=True)` | TIMESTAMPTZ | TEXT (ISO) |
| Date | `Date` | DATE | TEXT (ISO) |
| JSON | `sa.JSON` | JSONB | TEXT (JSON) |
| Enum | `Enum(StrEnum, native_enum=False)` | VARCHAR + CHECK | VARCHAR + CHECK |
| Boolean | `Boolean` | BOOLEAN | INTEGER (0/1) |

Contract rule: **no floating-point money anywhere** (constitution Principle I). Money columns always `*_minor` (BIGINT) with an adjacent `currency CHAR(3)`.

## 2. Enumeration contract (values are authoritative)

- `tenancy_status`: `draft | active | closed`
- `record_category`: `tenant_payment | utility_bill_payment` (persisted only)
- `direction`: `credit | debit`
- `matching_status`: `unmatched | ambiguous | matched | manually_matched | not_applicable`
- `allocation_type`: `automatic | manual | correction | reversal`
- `advance_movement_type`: `created | applied | reversed`
- `import_batch_status`: `parsing | staged | duplicate_statement | totals_mismatch | confirmed | rejected | completed | failed`
- `totals_status`: `valid | mismatch | missing`
- Deriived (not stored): bill status `unpaid | partial | paid`

Each implemented as a Python `enum.StrEnum`; DB enforcement via `CHECK` (R-1).

## 3. Uniqueness & CHECK constraint contract

| Table | Constraint | Contract |
|---|---|---|
| admin_user | `email` UNIQUE | One login identity |
| tenant_access_credential | `tenancy_id` UNIQUE | One credential per tenancy; the hash itself is NOT unique — codes are verified by tenancy + code, never globally |
| tenant_login_attempt | indexes `(tenancy_id, attempted_at)`, `(source_ip, attempted_at)` | Operational rate-limiting history; prunable, never financial |
| sender_alias | `(tenancy_id, normalized_name)` UNIQUE | No duplicate normalized sender |
| billing_override | `(tenancy_id, billing_month)` UNIQUE | One bill/skip decision per tenancy-month |
| monthly_bill | `(tenancy_id, billing_month)` UNIQUE | One bill per tenancy per month (I-6) |
| transaction | `duplicate_key` UNIQUE | Row de-dup (10.1) |
| transaction | `CHECK record_category IN (...)` | Commissions never stored (I-4) |
| utility_bill_payment | `transaction_id` UNIQUE | One provider-payment per source tx |
| import_channel_category_mapping | `UNIQUE (import_profile_id, channel, COALESCE(direction,'ANY'))`; `CHECK category IN (...)` | Mapping is a config, not code |
| import_batch | `CHECK`/app-layer `totals_status` | Control-total validation: footer totals (incl. commissions) compared in memory and discarded; only `totals_status` persisted; `source_file_sha256` detects re-presented files |
| staged_import_row | `CHECK row_category IN ('tenant_payment','utility_bill_payment')` | Only persistable categories staged |
| portal_setting | `(scope_type, scope_id, setting_key)` UNIQUE; `CHECK scope_type IN (...)` | Scoped config |
| billing_config | `standard_amount_minor CHECK >= 0` (+ all money where doc says `>= 0`); `amount_minor CHECK > 0` where doc says `> 0` | Money magnitude rules (3.4) |

## 4. Partial-unique contract (duplicate detection & tenancy)

PostgreSQL (native):
- `UNIQUE (room_id) WHERE status='active'` on `tenancy` (I-5).
- `UNIQUE (statement_fingerprint) WHERE status IN ('confirmed','completed')` on `import_batch`.

SQLite (divergence documented — R-4): SQLite has no partial indexes. Same invariants are enforced by the **application/service layer** and covered by tests. This is the **only** accepted engine divergence for invariants. PostgreSQL partial indexes are authored in the code now but exercised in CI/deploy (no local Postgres).

## 5. Immutability (append-only) contract

The following tables are append-only: `transaction`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `utility_bill_payment`, `audit_log` (R-5, spec SC-002).

PostgreSQL: `BEFORE UPDATE` / `BEFORE DELETE` triggers raise an exception on these tables (**authored now, validated in CI/deploy — no local Postgres**).
SQLite (divergence): application-layer guards; no UPDATE/DELETE write path; tests assert immutability.

Corrections must use reversal/correction rows (`advance_movement` created/applied/reversed semantics in §7.5), never edits or hard deletes.

## 6. Cross-table invariant contract (`docs/04` §8)

These span rows; enforced in the service layer inside DB transactions (I-1, I-2, I-7, I-8, I-9) and structurally + by tests for I-3, I-4. Full table in [data-model.md](../data-model.md) "Cross-Table Invariants".

## 7. Migration & seed contract

- **Alembic**, single reversible baseline migration (R-7), then seed.
- Migration ships every schema change; reversible where practical (`docs/04` §12).
- Seed is a **separate idempotent step** (R-6, spec SC-006): upsert default org, admin, global `PAYVICE_AVANTUS` profile + channel/category mappings, global `BEDC` provider, default org-wide `billing_config`, default portal settings.
- Seed must be re-runnable without duplicates or errors, and never include commission data.