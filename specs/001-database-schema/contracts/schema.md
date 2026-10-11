# Schema Contract: Full MVP Database Schema

**Feature**: `001-database-schema` | **Date**: 2026-10-10

This is the DB-level contract the ORM models, migration, and seed must uphold. It is the interface between the data-access layer and the database engines. `docs/04-database.md` is the only definition of tables and columns; this contract captures types, enumerations, constraints, immutability, and engine parity, without restating the §6 column lists. Table-to-module mapping is in [data-model.md](../data-model.md); type decisions are in [research.md](../research.md).

## Purpose & scope

Types of contract captured here:
- Data types and their per-engine rendering.
- Enumerated values (the value set is the contract — R-1).
- Uniqueness, CHECK, and partial-unique constraints.
- The immutability (append-only) contract.
- Engine parity: what is identical on PostgreSQL (production/CI) and SQLite (local/tests).

## 1. Data type contract

| Logical type | SQLAlchemy | PostgreSQL | SQLite (dev) |
|---|---|---|---|
| Primary key | `Uuid` with `default=uuid.uuid4` | UUID | TEXT/BLOB (UUID) |
| Money | `BigInteger` via `money()` helper (per-column CHECK) | BIGINT | INTEGER |
| Currency | `Char(3)` via `currency()` helper, default `"NGN"` | CHAR(3) | TEXT |
| Timestamp | shared UTC-aware type over `DateTime(timezone=True)` (R-2) | TIMESTAMPTZ | TEXT (ISO), returned tz-aware UTC |
| Date | `Date` | DATE | TEXT (ISO) |
| JSON | `sa.JSON` | JSONB | TEXT (JSON) |
| Enum | `TEXT` + `CHECK` (R-1) | VARCHAR + CHECK | TEXT + CHECK |
| Boolean | `Boolean` | BOOLEAN | INTEGER (0/1) |

Contract rules:
- **No floating-point money anywhere** (constitution Principle I). Money columns always `*_minor` (BIGINT) with an adjacent `currency CHAR(3)` where `docs/04` requires it.
- **One shared timestamp type** is used by every `*_at` column, so a naive datetime can never be compared with an aware one on either engine (R-2).

## 2. Enumeration contract (values are authoritative)

- `tenancy_status`: `draft | active | closed`
- `record_category`: `tenant_payment | utility_bill_payment` (persisted only)
- `direction`: `credit | debit`
- `matching_status`: `unmatched | ambiguous | matched | manually_matched | not_applicable`
- `allocation_type`: `automatic | manual | correction | reversal`
- `advance_movement_type`: `created | applied | reversed`
- `import_batch_status`: `parsing | staged | duplicate_statement | totals_mismatch | confirmed | rejected | completed | failed`
- `totals_status`: `valid | mismatch | missing`
- Derived (not stored): bill status `unpaid | partial | paid`

DB enforcement is `TEXT` + `CHECK` on both engines; the value set is the contract (R-1). Inline value sets in `docs/04` §6 (`billing_override.decision`, `bill_adjustment.adjustment_type`, `staged_import_row.parse_status`, `audit_log.actor_type`) follow the same rule.

## 3. Uniqueness & CHECK constraint contract

Column/constraint definitions live in `docs/04` §6; the contract is that each is enforced exactly as written. Key items:

| Table | Constraint | Contract |
|---|---|---|
| `admin_user` | `email` UNIQUE | One login identity |
| `tenant_access_credential` | `tenancy_id` UNIQUE | One credential per tenancy; the hash is NOT globally unique — verified by tenancy + code |
| `tenant_login_attempt` | indexes `(tenancy_id, attempted_at)`, `(source_ip, attempted_at)` | Operational rate-limiting history; prunable |
| `admin_login_attempt` | indexes `(admin_user_id, attempted_at)`, `(source_ip, attempted_at)` | Operational rate-limiting history; prunable |
| `sender_alias` | `(tenancy_id, normalized_name)` UNIQUE | No duplicate normalized sender |
| `billing_override` | `(tenancy_id, billing_month)` UNIQUE; `CHECK decision IN ('bill','skip')` | One bill/skip decision per tenancy-month |
| `monthly_bill` | `(tenancy_id, billing_month)` UNIQUE | One bill per tenancy per month (I-6) |
| `transaction` | `duplicate_key` UNIQUE; `CHECK record_category IN ('tenant_payment','utility_bill_payment')` | Row de-dup; commissions never stored (I-4) |
| `utility_bill_payment` | `transaction_id` UNIQUE | One provider-payment per source transaction |
| `import_channel_category_mapping` | `UNIQUE (import_profile_id, channel, COALESCE(direction,'ANY'))`; `CHECK category IN (...)` | Mapping is configuration, not code |
| `import_batch` | `totals_status` + partial unique (see §4) | Control totals compared in memory and discarded |
| `staged_import_row` | `CHECK row_category IN (...)`; `CHECK parse_status IN (...)` | Only persistable categories staged; `duplicate_key` is NOT unique so `parse_status = 'duplicate'` rows remain stageable (`docs/04` §6.7, §10.1) |
| `portal_setting` | `(scope_type, scope_id, setting_key)` UNIQUE; `CHECK scope_type IN ('organization','property')` | Scoped config |
| `billing_config` | partial unique `UNIQUE (organization_id) WHERE property_id IS NULL` | One org-wide default row per organization (`docs/04` §6.4) |
| money columns | `CHECK (>= 0)` or `CHECK (> 0)` per `docs/04` §6 | Money magnitude rules (`docs/04` §3.4) |

`organization.timezone` is stored as an IANA `TEXT` string defaulting to `Africa/Lagos`; it is validated as a valid IANA name at the model layer (`docs/04` §6.2; spec FR-026).

## 4. Partial-unique contract (duplicate detection & tenancy)

Both engines enforce the partial unique indexes natively (R-4):
- `UNIQUE (room_id) WHERE status='active'` on `tenancy` (I-5) — declared with `sqlite_where` and `postgresql_where`.
- `UNIQUE (statement_fingerprint) WHERE status IN ('confirmed','completed')` on `import_batch` — declared with `sqlite_where` and `postgresql_where`.
- `UNIQUE (organization_id) WHERE property_id IS NULL` on `billing_config` (one org-wide default per organization; `docs/04` §6.4, §8 item 10) — declared with `sqlite_where` and `postgresql_where`.

SQLite supports partial indexes (since 3.8.0); there is **no** engine divergence for these invariants.

## 5. Immutability (append-only) contract

The following tables are append-only (`docs/04` §11.1): `transaction`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `utility_bill_payment`, `audit_log`.

- **Both engines** reject in-place `UPDATE`/`DELETE` with triggers (R-5): PostgreSQL via a shared `trigger` function + per-table triggers, SQLite via `BEFORE UPDATE`/`BEFORE DELETE` triggers that `RAISE(ABORT, ...)`.
- The trigger DDL is defined **once** and emitted both by `metadata.create_all()` (tests) and by the Alembic baseline (migration), so the two paths cannot differ.
- Corrections use reversal/correction rows (`advance_movement` created/applied/reversed semantics, `docs/04` §7.5), never edits or hard deletes.

## 6. Cross-table invariant contract (`docs/04` §8)

Row-spanning invariants I-1, I-2, I-7, I-8, I-9 are enforced in the service layer inside DB transactions; I-3/I-4 are structural + tested; I-5 is the partial unique index above; I-6 is the unique constraint. Full table in [data-model.md](../data-model.md) §4.

## 7. Migration & seed contract

- **Alembic**, single reversible baseline migration (R-10), then seed.
- Migration ships every schema change; reversible where practical (`docs/04` §12).
- Seed is a **separate idempotent step** (R-9): upsert default org, admin, global `PAYVICE_AVANTUS` profile + mappings, global `BEDC` provider, default org-wide `billing_config`, default portal settings (`docs/04` §12).
- Seed is re-runnable with no duplicates or errors, and never includes commission data.
