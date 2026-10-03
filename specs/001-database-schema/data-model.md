# Data Model: Full MVP Database Schema

**Feature**: `001-database-schema` | **Date**: 2026-09-21 | **Authoritative source**: `docs/04-database.md` (exhaustive column specs); this document is the ORM-level data model that the implementation must satisfy.

**Engine/type decisions** (from [research.md](research.md), R-1…R-9): UUID PKs app-side `uuid4`; enums as Python `enum.StrEnum` + VARCHAR/CHECK; money as `BIGINT` via a `money()` column helper; `currency CHAR(3)` default `NGN` via `currency()` helper; timezone-aware `DateTime`; `sa.JSON` for JSONB-equivalent columns; partial unique indexes Postgres-native, app-layer on SQLite; immutable tables blocked by Postgres triggers.

**Conventions applied everywhere** (`docs/04` §3): singular `snake_case` tables; `snake_case` columns; FK named `<singular_table>_id`; `created_at` on all tables, `updated_at` on mutable tables only; semantic timestamps supplement, never replace.

**Immutable (append-only, `created_at` only)**: `transaction`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `utility_bill_payment`, `audit_log`.
**Mutable (`updated_at`)**: `organization`, `property`, `room`, `tenancy`, `tenant`, `sender_alias`, `monthly_bill`, `billing_config`, `billing_override`, `portal_setting`, `import_profile`, `import_channel_category_mapping`, `import_batch`, `utility_provider`, `tenant_access_credential`, `admin_user`.
**Write-once operational (no `updated_at`; closed via semantic field or append-only)**: `tenant_session` (`revoked_at`), `staged_import_row` (`committed_transaction_id`), `tenant_login_attempt` (append-only rate-limiting history, prunable).

---

## 1. Identity & Access

### admin_user (mutable)
Represents the administrator login (MVP: one admin per org).
- Fields: `id` (UUID PK), `organization_id` (FK→organization, NOT NULL), `email` (TEXT NOT NULL UNIQUE), `password_hash` (TEXT NOT NULL, never plaintext), `is_active` (BOOL NOT NULL DEFAULT true), `created_at`, `updated_at`.
- Relationships: `organization` (N:1), updated by/creates: `billing_config`, `billing_override`, `standard_amount_change`, `bill_adjustment`.
- Validation: email unique; password hash non-empty.

### tenant_access_credential (mutable)
Hashed shared access code per tenancy.
- Fields: `id`, `tenancy_id` (FK→tenancy NOT NULL UNIQUE), `access_code_hash` (TEXT NOT NULL), `credential_version` (INT NOT NULL DEFAULT 1), `is_active` (BOOL NOT NULL DEFAULT true), `created_at`, `updated_at`, `rotated_at` (semantic).
- State transition (rotation): reset → increment `credential_version`, update hash, set `rotated_at`; prior sessions invalid.
- Notes: `access_code_hash` is NOT globally unique — codes are verified only against the tenancy of the selected room, by tenancy plus code. No unique index spans tenancies.

### tenant_session (write-once operational)
Read-only session token snapshot for the tenant portal.
- Fields: `id`, `credential_id` (FK→tenant_access_credential NOT NULL), `credential_version` (INT NOT NULL snapshot), `token_hash` (TEXT NOT NULL), `device_info` (TEXT), `issued_at`, `expires_at`, `revoked_at`, `created_at`.
- Validity rule (derived): `revoked_at IS NULL AND expires_at > now() AND credential_version = credential.credential_version AND credential.is_active = true`.
- Notes: multiple concurrent sessions allowed; closed via `revoked_at` (no in-place edits). `expires_at` is fixed at issuance and never extended on use. Session lifetime (e.g. 30 days) is application configuration, not schema.

### tenant_login_attempt (write-once operational)
Rate-limiting history for tenant access-code attempts. Operational, prunable; never financial.
- Fields: `id`, `organization_id` (FK→organization NOT NULL, org-scoped), `tenancy_id` (FK→tenancy, nullable — null when the room is unknown), `source_ip` (TEXT), `attempted_at` (timestamptz, UTC), `succeeded` (BOOLEAN NOT NULL), `created_at`.
- Indexes: `(tenancy_id, attempted_at)`, `(source_ip, attempted_at)`.
- Notes: stored in the database so rate limiting survives free-host restarts; thresholds (e.g. 5 failures / 15 min, 15-min lockout) are application configuration, not schema.

---

## 2. Organization & Property

### organization (mutable)
Root isolation boundary (ADR-001); owns all scoped records. `id`, `name` (TEXT NOT NULL), `timezone` (TEXT NOT NULL DEFAULT `Africa/Lagos`, IANA name validated in app code; instants stored UTC, calendar-month boundaries computed in this timezone), `created_at`, `updated_at`.

### property (mutable)
Physical building. `id`, `organization_id` (FK NOT NULL → org for scoping), `name` (TEXT NOT NULL), `created_at`, `updated_at`.

### room (mutable)
Physical space, persists across tenancies. `id`, `property_id` (FK NOT NULL), `label` (TEXT NOT NULL), `is_active` (BOOL DEFAULT true), `created_at`, `updated_at`.
- Org reachable via `room → property → organization`.

---

## 3. Tenancy

### tenancy (mutable)
Occupancy period and tenant-portal privacy boundary.
- Fields: `id`, `organization_id` (FK NOT NULL, denormalized for scoping), `room_id` (FK NOT NULL), `status` (`draft|active|closed`, DEFAULT `draft`), `start_date` (DATE NOT NULL), `end_date` (DATE nullable), `created_at`, `updated_at`.
- Constraint: partial unique index `UNIQUE(room_id) WHERE status='active'` (PG-native; **invariant I-5**).
- State transition: `draft → active → closed` (closed tenancies lose portal access — ADR-026).

### tenant (mutable)
Occupant(s) of a tenancy; no individual logins. `id`, `tenancy_id` (FK NOT NULL), `name` (TEXT NOT NULL), `email`, `phone` (TEXT optional), `created_at`, `updated_at`.

### sender_alias (mutable)
Accepted bank sender name for tenancy matching. `id`, `organization_id` (FK NOT NULL denormalized for matching scope), `tenancy_id` (FK NOT NULL), `display_name` (TEXT NOT NULL as entered), `normalized_name` (TEXT NOT NULL), `created_at`, `updated_at`.
- Constraint: `UNIQUE(tenancy_id, normalized_name)`.

---

## 4. Billing Configuration

### billing_config (mutable)
Org-wide standard amount (property_id null = org-wide; uniform across rooms).
- Fields: `id`, `organization_id` (FK NOT NULL), `property_id` (FK nullable), `standard_amount_minor` (BIGINT NOT NULL CHECK >= 0), `currency` (CHAR(3) NOT NULL default NGN), `created_at`, `updated_at`, `updated_by_admin_id` (FK).
- Behavior: bills snapshot the standard amount at generation; changing it never silently rewrites existing bills (adjustments only via `bill_adjustment`).

### billing_override (mutable)
Per-tenancy, per-month bill/skip decision (move-in opt-in, move-out exemption). `id`, `organization_id` FK, `tenancy_id` FK, `billing_month` (DATE), `decision` (`bill|skip`), `reason`, `created_by_admin_id`, `created_at`, `updated_at`.
- Constraint: `UNIQUE(tenancy_id, billing_month)`.

### standard_amount_change (immutable)
Append-only history of org-wide rate changes. `id`, `organization_id` FK, `previous_amount_minor` (CHECK >=0), `new_amount_minor` (CHECK >=0), `currency` CHAR(3), `auto_note` TEXT, `custom_note`, `admin_id` FK, `effective_at`, `created_at`.

---

## 5. Tenant Payment Ledger

### transaction (immutable) — ledger #1
Normalized source row.
- Fields: `id`, `organization_id` FK NOT NULL, `import_batch_id` FK nullable (manual entry), `record_category` (`tenant_payment|utility_bill_payment`), `source` TEXT, `transaction_date` DATE, `transaction_time` TIME, `channel` TEXT, `direction` (`credit|debit`), `description_raw`, `counterparty_name`, `counterparty_name_normalized`, `counterparty_reference`, `amount_minor` (BIGINT NOT NULL CHECK > 0), `currency` CHAR(3), `tenancy_id` FK nullable (set on match), `matching_status` (`unmatched|ambiguous|matched|manually_matched|not_applicable`), `duplicate_key` TEXT NOT NULL UNIQUE, `created_at`.
- Constraint: `CHECK (record_category IN ('tenant_payment','utility_bill_payment'))` — **guarantees commissions never stored (invariant I-4)**.
- Notes: immutable; corrections via reversals. `tenant_payment` rows get `tenancy_id` after matching; `utility_bill_payment` rows use `matching_status=not_applicable`.

### monthly_bill (mutable, amount changes only via adjustment)
Per-tenancy/month billing state. `id`, `organization_id` FK, `tenancy_id` FK, `billing_month` DATE, `standard_amount_minor` (CHECK >=0, snapshot), `final_amount_minor` (CHECK >=0), `currency` CHAR(3), `is_adjusted` BOOL default false, `created_at`, `updated_at`.
- Constraint: `UNIQUE(tenancy_id, billing_month)` (**invariant I-6**).
- Status (unpaid/partial/paid) is **derived**, never stored (§7.1).

### payment_allocation (immutable)
Links a tenant payment to a monthly bill. `id`, `transaction_id` FK NOT NULL, `monthly_bill_id` FK NOT NULL, `amount_minor` (CHECK >0), `currency` CHAR(3), `allocation_type` (`automatic|manual|correction|reversal`), `reverses_allocation_id` FK nullable, `created_at`.
- Invariant (**I-1 allocation cap**): `SUM(amount_minor) per transaction_id <= transaction.amount_minor` (enforced in billing engine within a DB transaction).

### advance_movement (immutable) — advance ledger
Append-only advance-credit event log for auditability/fraud detection; **balance is derived** (§7.4).
- Fields: `id`, `organization_id` FK, `tenancy_id` FK, `transaction_id` FK NOT NULL (originating payment), `movement_type` (`created|applied|reversed`), `amount_minor` (CHECK >0), `currency` CHAR(3), `monthly_bill_id` FK (set when `applied`), `allocation_id` FK (set when `applied`), `note`, `occurred_at`, `created_at`.
- Semantics: `reversed` only ever offsets a `created`; restoring an applied allocation appends a new `created` (§7.5). `applied` movement is atomic with its allocation (**invariant I-8**).

### bill_adjustment (immutable)
Recorded change to a bill's final amount. `id`, `monthly_bill_id` FK NOT NULL, `adjustment_type` (`rate_change|write_off`), `previous_amount_minor` (CHECK >=0), `new_amount_minor` (CHECK >=0), `currency` CHAR(3), `public_note`, `custom_note`, `internal_reason`, `admin_id` FK NOT NULL, `created_at`.
- Invariant (**I-7 audited amount change**): any change to `monthly_bill.final_amount_minor` has a matching `bill_adjustment`.

---

## 6. Utility Bill Payment Ledger

### utility_provider (mutable, global registry)
Global/system-wide; `organization_id` nullable (null = global, MVP seeds global). `id`, `organization_id` FK null, `code` (TEXT UNIQUE e.g. BEDC), `display_name`, `channel_signature`, `reference_label`, `is_active`, `created_at`, `updated_at`.

### utility_bill_payment (immutable) — ledger #2
Outgoing provider payment; never settles tenant bills. `id`, `organization_id` FK, `transaction_id` FK NOT NULL UNIQUE, `provider_id` FK NOT NULL, `customer_reference`, `amount_minor` (CHECK >0), `currency` CHAR(3), `payment_datetime`, `spend_month` DATE, `import_batch_id` FK, `created_at`.
- Constraint `transaction_id UNIQUE`: one provider-payment per source transaction.

---

## 7. Transaction Ingestion

### import_profile (mutable, global registry)
Global/system-wide parser config; `organization_id` nullable. `id`, `organization_id` FK null, `code` (TEXT UNIQUE e.g. PAYVICE_AVANTUS), `display_name`, `source_type` (`pdf` only — CSV/XLSX are out of MVP scope), `detection_config` (JSON), `parse_config` (JSON), `file_limits` (JSON), `is_active`, `created_at`, `updated_at`.

### import_channel_category_mapping (mutable)
Channel→category routing config. `id`, `import_profile_id` FK, `channel` TEXT, `direction` (`credit|debit|null`), `category` (`tenant_payment|utility_bill_payment|ignored|excluded|unrecognized`), `created_at`, `updated_at`.
- Constraints: `UNIQUE(import_profile_id, channel, COALESCE(direction,'ANY'))`, `CHECK (category IN (...))`.
- `COMMISSION` maps to `excluded` → never persisted (**invariant I-4**).

### import_batch (mutable)
Staged/confirmed import operation metadata.
- Fields: `id`, `organization_id` FK, `import_profile_id` FK, `status` (`parsing|staged|duplicate_statement|totals_mismatch|confirmed|rejected|completed|failed`), statement header fields, `source_file_sha256` (CHAR(64)), `source_filename`, `source_page_count`, `currency` CHAR(3) default NGN, `totals_status` (`valid|mismatch|missing`), `statement_fingerprint` TEXT, `ignored_summary` JSON, staged row counters/totals, `uploaded_at`, `confirmed_at`, `created_at`, `updated_at`.
- Constraint: partial unique `UNIQUE(statement_fingerprint) WHERE status IN ('confirmed','completed')` (PG-native; **invariant** — duplicate-statement detection; allows re-import after rejection).
- State transition: `parsing → staged → confirmed → completed`; failure/skip branches `totals_mismatch`, `duplicate_statement`, `rejected`, `failed`.
- Notes: statement-footer credit/debit totals are NOT persisted — they include commissions (ADR-019) and are compared in memory then discarded; only `totals_status` is stored. `source_file_sha256` detects a re-presented file and is distinct from the content-based `statement_fingerprint`; the PDF is not retained (ADR-012, ADR-019).

### staged_import_row (write-once operational)
Staged row surviving between parse and confirm. `id`, `import_batch_id` FK, `row_category` (`tenant_payment|utility_bill_payment`), date/time, `channel`, `direction`, `description_raw`, `counterparty_name`, `counterparty_reference`, `amount_minor` (CHECK >0), `duplicate_key`, `parse_status` (`valid|duplicate|invalid|unrecognized`), `parse_error`, `committed_transaction_id` FK null, `created_at`.
- Constraint: `CHECK (row_category IN ('tenant_payment','utility_bill_payment'))`; closed via `committed_transaction_id`. Commission never staged.

---

## 8. Settings & Visibility

### portal_setting (mutable)
Configurable visibility/default view. `id`, `scope_type` (`organization|property`), `scope_id` (UUID), `setting_key`, `setting_value`, `created_at`, `updated_at`.
- Constraints: `UNIQUE(scope_type, scope_id, setting_key)`, `CHECK (scope_type IN ('organization','property'))`.
- Example keys: `default_view`, `allow_other_room_amount_due` (default `false` — other rooms see property aggregates; per-room amount/status is admin opt-in, tenants cannot opt in/out), `allow_property_utility_spend`, `allow_other_room_tenant_names`.

---

## 9. Audit

### audit_log (immutable)
Append-only admin/system action record. `id`, `organization_id` FK, `actor_type` (`admin|system|tenant_session`), `actor_id` (null for system), `action` TEXT, `entity_type`, `entity_id`, `metadata` (JSON), `created_at`.
- Never contains commission data; tenants never see it.

---

## Cross-Table Invariants (`docs/04` §8)

| # | Invariant | Enforcement |
|---|---|---|
| I-1 | Allocation cap (sum signed allocations ≤ transaction amount) | Billing engine in DB transaction + test |
| I-2 | Advance reconciliation (derived balance == logged movements, §7.5) | Service check + test |
| I-3 | Ledger separation (utility ≠ tenant settlement) | Schema structure + tests |
| I-4 | Commissions never stored in `transaction`/`staged_import_row` | CHECK + category mapping |
| I-5 | One active tenancy per room | Partial unique index (PG); app-layer (SQLite) |
| I-6 | One bill per tenancy per month | `UNIQUE(tenancy_id, billing_month)` |
| I-7 | Every bill amount change has a `bill_adjustment` | Service invariant + test |
| I-8 | `applied` advance movement atomic with its allocation | Same DB transaction |
| I-9 | All scoped queries filter by `organization_id` | Mixin + query discipline + test |

## Derived State (`docs/04` §7) — computed, never stored

- §7.1 bill status, §7.2 bill remaining, §7.3 tenancy outstanding, §7.4 advance balance (derived + movement log), §7.5 reconciliation identity, §7.6 net position, §7.7 utility spend by month. (Plain queries for MVP — §7.8; see spec Assumptions.)

## Duplicate-Detection Keys (`docs/04` §10)

- `transaction.duplicate_key` / `staged_import_row.duplicate_key`: deterministic hash of `statement_account_number + normalized date/time + channel + normalized description + direction + amount_minor`.
- `import_batch.statement_fingerprint`: hash of `statement_account_number + statement period + ordered persistable row duplicate keys`.

## Indexes (`docs/04` §9)

Applied as documented: transaction `(organization_id, transaction_date)`, `(tenancy_id)`, `(import_batch_id)`, `(record_category)`; monthly_bill `(billing_month)`, `(organization_id, billing_month)`; payment_allocation `(transaction_id)`, `(monthly_bill_id)`; advance_movement `(transaction_id)`, `(tenancy_id, occurred_at)`; utility_bill_payment `(provider_id, spend_month)`, `(organization_id, spend_month)`; sender_alias `(organization_id, normalized_name)`; staged_import_row `(import_batch_id)`; audit_log `(organization_id, created_at)`, `(entity_type, entity_id)`; import_batch `(statement_fingerprint)`; tenant_login_attempt `(tenancy_id, attempted_at)`, `(source_ip, attempted_at)`.