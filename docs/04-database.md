# Database Design

Document: `docs/04-database.md`
Version: `0.6.0`
Status: Draft — design phase
Last Updated: 2026-10-10
Related documents: `03-mvp-architecture.md`, `05-billing-engine.md`, `06-transaction-ingestion.md`

Changes in this version: Added `admin_session` and `admin_login_attempt` (admin auth storage) and registered them in the ER diagram, index list, and retention/mutability lists.

---

## 1. Purpose

This document defines the database design for the MVP.

It specifies:

- Entities and relationships.
- Tables and columns.
- Constraints and indexes.
- Enumerations.
- Duplicate-detection keys.
- Derived state and reconciliation.
- Immutability and retention rules.
- Migration strategy.

This is a design document. It does not contain application code.

---

## 2. Guiding Principles

The database design follows the architecture's principles:

1. **Single source of truth.** A transaction is stored once and referenced by allocations, not duplicated into bills. Advance *balance* is derived, not stored as an independent mutable value.
2. **Immutable financial history.** Transactions, allocations, adjustments, advance movements, and audit records are append-oriented. Corrections use reversal/correction records, not silent rewrites.
3. **Tamper-evident auditing.** Where a value is derived, an independent append-only log is kept alongside it so the two can be reconciled. If they disagree, tampering or a bug is detected.
4. **Money as integer minor units.** All monetary amounts are stored as `BIGINT` minor units. No floating point.
5. **Organization isolation.** Key financial tables carry `organization_id` to support scoped queries and future multi-tenancy.
6. **Non-guessable identifiers.** Public-facing entities use UUID primary keys. UUIDs reduce enumeration but are not a substitute for server-side authorization.
7. **Commissions are never stored.** No table, column, or log may persist commission data.

---

## 3. Conventions

### 3.1 Primary keys

All entities use UUID primary keys.

```text
id  UUID  PRIMARY KEY  DEFAULT gen_random_uuid()
```

### 3.2 Timestamps

- `created_at` — `timestamptz`, set on insert, present on all tables.
- `updated_at` — `timestamptz`, present on mutable tables only.
- Immutable financial tables have `created_at` only.

Semantic timestamps (rotated_at, issued_at, occurred_at, effective_at, uploaded_at) supplement but never replace created_at/updated_at.

### 3.3 Naming

- Table names: `snake_case`, singular (e.g. `tenancy`, `monthly_bill`).
- Column names: `snake_case`.
- Foreign keys: `<singular_table>_id`.

### 3.4 Money

- Column suffix: `_minor`.
- Type: `BIGINT`.
- Always a non-negative magnitude. Direction is stored separately where relevant.

Example: ₦1,000.00 → `100000`.

### 3.5 Currency

Every persisted table that stores a monetary amount carries a `currency CHAR(3) NOT NULL` column defaulting to the MVP currency, to avoid a future migration. Transient staging tables do not carry currency. The MVP currency is NGN (ISO 4217); monetary examples use ₦.

---

## 4. Enumerations

These may be implemented as database enums or lookup tables. The values are the contract.

### tenancy_status

```text
draft | active | closed
```

### record_category (persisted transactions)

```text
tenant_payment | utility_bill_payment
```

Non-persisted categories exist only in staging and import summaries, never in the `transaction` table:

```text
ignored | excluded | unrecognized
```

### direction

```text
credit | debit
```

### matching_status

```text
unmatched | ambiguous | matched | manually_matched | not_applicable
```

`not_applicable` is used for utility bill payments, which never enter tenancy matching.

### allocation_type

```text
automatic | manual | correction | reversal
```

### advance_movement_type

```text
created | applied | reversed
```

- `created` — advance credit was created from a payment's unallocated remainder.
- `applied` — advance credit was applied to a monthly bill.
- `reversed` — a `created` movement was undone by a correction (advance credit clawed back). It never undoes an `applied` movement; restoring an applied allocation records a new `created` movement.

### import_batch_status

```text
parsing | staged | duplicate_statement | totals_mismatch | confirmed | rejected | completed | failed
```

### totals_status

```text
valid | mismatch | missing
```

### derived bill status (not stored)

```text
unpaid | partial | paid
```

This is computed from allocations, never stored.

---

## 5. Entity-Relationship Overview

```text
AdminUser ─── Organization
                  │
                  ├── Property
                  │      └── Room
                  │             └── Tenancy ──< Tenant
                  │                    │
                  │                    ├──< SenderAlias
                  │                    ├──< MonthlyBill ──< BillAdjustment
                  │                    ├──< TenantAccessCredential ──< TenantSession
                  │                    ├──< TenantLoginAttempt
                  │                    ├──< AdvanceMovement
                  │                    └──< Transaction (tenant_payment, matched)
                  │                              ├──< PaymentAllocation >── MonthlyBill
                  │                              └──< AdvanceMovement
                  │
                  ├──< Transaction (all persisted)
                  │
                  ├── UtilityProvider (global) ──< UtilityBillPayment ── Transaction (utility_bill_payment)
                  │
                  ├── ImportProfile (global) ──< ImportChannelCategoryMapping
                  │        └──< ImportBatch ──< StagedImportRow
                  │
                  ├── BillingConfig
                  ├── BillingOverride
                  ├── StandardAmountChange
                  ├── PortalSetting
                  └── AuditLog

AdminUser
     ├──< AdminSession
     └──< AdminLoginAttempt
```

---

## 6. Table Specifications

Tables are grouped by domain.

---

### 6.1 Identity and Access

#### admin_user

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | MVP: one admin per org |
| email | TEXT | NOT NULL, UNIQUE | Login identifier |
| password_hash | TEXT | NOT NULL | Never plaintext |
| is_active | BOOLEAN | NOT NULL DEFAULT true | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

---

#### tenant_access_credential

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| tenancy_id | UUID | FK → tenancy, NOT NULL, UNIQUE | One credential per tenancy |
| access_code_hash | TEXT | NOT NULL | Hashed, never plaintext |
| credential_version | INTEGER | NOT NULL DEFAULT 1 | Incremented on reset to revoke sessions |
| is_active | BOOLEAN | NOT NULL DEFAULT true | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |
| rotated_at | timestamptz | | Last reset time |

Notes:
- Resetting the code increments `credential_version` and updates `access_code_hash`.
- Sessions issued against an older version become invalid.
- Access codes are generated, hashed, and verified only against the tenancy of the selected room. Codes are not unique across tenancies: there is no uniqueness constraint over the hash, and lookup is by tenancy plus code, never by hash alone across tenancies.

---

#### tenant_session

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| credential_id | UUID | FK → tenant_access_credential, NOT NULL | |
| credential_version | INTEGER | NOT NULL | Snapshot at issuance |
| token_hash | TEXT | NOT NULL | Hashed session token |
| device_info | TEXT | | Optional user-agent/device hint |
| issued_at | timestamptz | NOT NULL | |
| expires_at | timestamptz | NOT NULL | |
| revoked_at | timestamptz | | Set on revocation |
| created_at | timestamptz | NOT NULL | |

Validity rule:

```text
session is valid when:
  revoked_at IS NULL
  AND expires_at > now()
  AND credential_version = credential.credential_version
  AND credential.is_active = true
```

Notes:
- Multiple concurrent sessions per tenancy are allowed (multiple rows).
- Read-only by design; no tenant-initiated mutations.
- `expires_at` is fixed at issuance and never extended on use. The validity rule checks `expires_at > now()`; it never slides the expiry forward.
- Session lifetime and code length (e.g. 30-day sessions, 8-character codes) are application configuration, not schema.

---

#### admin_session

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| admin_user_id | UUID | FK → admin_user, NOT NULL | |
| token_hash | TEXT | NOT NULL | Hashed session token |
| device_info | TEXT | | Optional user-agent/device hint |
| issued_at | timestamptz | NOT NULL | |
| expires_at | timestamptz | NOT NULL | |
| revoked_at | timestamptz | | Set on revocation |
| created_at | timestamptz | NOT NULL | |

Validity rule:

```text
session is valid when:
  revoked_at IS NULL
  AND expires_at > now()
  AND admin_user.is_active = true
```

Notes:
- Multiple concurrent sessions per admin are allowed (multiple rows).
- Interactive session; revoked on logout, password change or reset, and admin deactivation.
- `expires_at` is fixed at issuance and never extended on use. The validity rule checks `expires_at > now()`; it never slides the expiry forward.
- Session lifetime (e.g. 24-hour sessions) is application configuration, not schema.

---

#### tenant_login_attempt

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | Org-scoped for rate limiting |
| tenancy_id | UUID | FK → tenancy | Nullable; an attempt against an unknown room has none |
| source_ip | TEXT | | Client IP |
| attempted_at | timestamptz | NOT NULL | UTC |
| succeeded | BOOLEAN | NOT NULL | |
| created_at | timestamptz | NOT NULL | |

Notes:
- Operational, prunable table backing rate limiting. Rate limiting is stored in the database, not process memory, because free hosts restart (ADR-012).
- Thresholds (e.g. 5 failures per 15 minutes, 15-minute lockout) are application configuration, not schema.
- An attempt against an unknown room is recorded with `tenancy_id` null.
- Not a financial table; never part of the append-only list (see Section 11.6).

---

#### admin_login_attempt

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | Org-scoped for rate limiting |
| admin_user_id | UUID | FK → admin_user | Nullable; an attempt against an unknown admin has none |
| source_ip | TEXT | | Client IP |
| attempted_at | timestamptz | NOT NULL | UTC |
| succeeded | BOOLEAN | NOT NULL | |
| created_at | timestamptz | NOT NULL | |

Notes:
- Operational, prunable table backing admin rate limiting. Rate limiting is stored in the database, not process memory, because free hosts restart (ADR-012).
- Thresholds (e.g. 10 failures per 15 minutes, 15-minute lockout) are application configuration, not schema.
- An attempt against an unknown admin is recorded with `admin_user_id` null.
- Not a financial table; never part of the append-only list (see Section 11.6).

---

### 6.2 Organization and Property

#### organization

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| name | TEXT | NOT NULL | |
| timezone | TEXT | NOT NULL DEFAULT 'Africa/Lagos' | IANA business timezone (ADR-028) |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

Notes:
- The IANA name is validated in application code; the database stores whatever string it is given.
- Instants are stored in UTC. Calendar-month boundaries — `billing_month`, "current month", and utility-spend grouping — are computed in the organization's business timezone (ADR-028). The timezone is a single org-wide setting; it is not per-property in the MVP.

---

#### property

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | |
| name | TEXT | NOT NULL | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

---

#### room

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| property_id | UUID | FK → property, NOT NULL | |
| label | TEXT | NOT NULL | Display name, e.g. "Room 4" |
| is_active | BOOLEAN | NOT NULL DEFAULT true | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

Notes:
- A room persists across tenancies.
- Organization is reachable via `room → property → organization`.

---

### 6.3 Tenancy

#### tenancy

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | Denormalized for scoping |
| room_id | UUID | FK → room, NOT NULL | |
| status | tenancy_status | NOT NULL DEFAULT draft | |
| start_date | DATE | NOT NULL | |
| end_date | DATE | | Nullable while active |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

Constraints:

```text
UNIQUE (room_id) WHERE status = 'active'
```

---

#### tenant

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| tenancy_id | UUID | FK → tenancy, NOT NULL | |
| name | TEXT | NOT NULL | |
| email | TEXT | | Optional |
| phone | TEXT | | Optional |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

---

#### sender_alias

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | Denormalized for matching scope |
| tenancy_id | UUID | FK → tenancy, NOT NULL | |
| display_name | TEXT | NOT NULL | As entered |
| normalized_name | TEXT | NOT NULL | Uppercased, punctuation-stripped, collapsed |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

Constraints:

```text
UNIQUE (tenancy_id, normalized_name)
```

---

### 6.4 Billing Configuration

#### billing_config

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | |
| property_id | UUID | FK → property | Nullable; null = org-wide default |
| standard_amount_minor | BIGINT | NOT NULL CHECK (>= 0) | |
| currency | CHAR(3) | NOT NULL | Fixed for MVP |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |
| updated_by_admin_id | UUID | FK → admin_user | |

Notes:
- MVP uses one standard amount (org-wide, `property_id` null).
- The standard amount is organization-wide and uniform across rooms. When describing the standard amount, "global" in the ADRs means org-wide; when describing utility providers and import profiles, "global" means system-wide.
- Bills snapshot the standard amount at generation time. Changing this value does not silently rewrite existing bills; already-generated, unsettled current-month bills are adjusted only via recorded `bill_adjustment` rows, while settled bills and past months are never adjusted.

#### billing_override

**billing_override** — a per-tenancy, per-month decision to force-bill or force-skip.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | |
| tenancy_id | UUID | FK → tenancy, NOT NULL | |
| billing_month | DATE | NOT NULL | First day of month, in the org's business timezone |
| decision | TEXT | NOT NULL | `bill` or `skip` |
| reason | TEXT | | Optional |
| created_by_admin_id | UUID | FK → admin_user | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

Unique constraint: `UNIQUE (tenancy_id, billing_month)`.

Notes: supports the move-in opt-in (`bill`) and the move-out foreknowledge exemption (`skip`). The lazy generator consults this table before creating a bill. This is a bill/skip decision only; it never changes a bill amount. Amount changes are limited to recorded rate-change adjustments and write-offs (see `bill_adjustment`).

#### standard_amount_change

**standard_amount_change** — history of org-wide standard-amount changes.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | |
| previous_amount_minor | BIGINT | NOT NULL CHECK (>= 0) | |
| new_amount_minor | BIGINT | NOT NULL CHECK (>= 0) | |
| currency | CHAR(3) | NOT NULL | Defaults to the MVP currency |
| auto_note | TEXT | NOT NULL | e.g. "Standard amount changed from X to Y" |
| custom_note | TEXT | | Optional |
| admin_id | UUID | FK → admin_user, NOT NULL | |
| effective_at | timestamptz | NOT NULL | |
| created_at | timestamptz | NOT NULL | |

Notes: append-only. One row per rate change. Drives the rate-change bill adjustments.

---

### 6.5 Tenant Payment Ledger

#### transaction

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | |
| import_batch_id | UUID | FK → import_batch | Nullable for manual entry |
| record_category | record_category | NOT NULL | Only persisted categories |
| source | TEXT | NOT NULL | e.g. PAYVICE_AVANTUS, manual |
| transaction_date | DATE | NOT NULL | |
| transaction_time | TIME | | Time of day, normalized |
| channel | TEXT | NOT NULL | e.g. FUNDING, BEDC |
| direction | direction | NOT NULL | credit / debit |
| description_raw | TEXT | NOT NULL | Original description |
| counterparty_name | TEXT | | Extracted sender/counterparty |
| counterparty_name_normalized | TEXT | | For matching |
| counterparty_reference | TEXT | | Account/meter number in parentheses |
| amount_minor | BIGINT | NOT NULL CHECK (> 0) | Positive magnitude |
| currency | CHAR(3) | NOT NULL | |
| tenancy_id | UUID | FK → tenancy | Set when matched (tenant_payment) |
| matching_status | matching_status | NOT NULL DEFAULT unmatched | |
| duplicate_key | TEXT | NOT NULL, UNIQUE | Deterministic hash |
| created_at | timestamptz | NOT NULL | |

Constraints:

```text
CHECK (record_category IN ('tenant_payment', 'utility_bill_payment'))
```

This CHECK guarantees commissions and ignored rows are never stored here.

Notes:
- Immutable after commit. Corrections use reversals, not edits.
- `tenant_payment` rows get `tenancy_id` after matching.
- `utility_bill_payment` rows use `matching_status = not_applicable` and spawn a `utility_bill_payment` record.
- `duplicate_key` definition is in Section 10.

---

#### monthly_bill

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | Denormalized for scoping |
| tenancy_id | UUID | FK → tenancy, NOT NULL | |
| billing_month | DATE | NOT NULL | First day of the month, in the org's business timezone |
| standard_amount_minor | BIGINT | NOT NULL CHECK (>= 0) | Snapshot at generation |
| final_amount_minor | BIGINT | NOT NULL CHECK (>= 0) | After any adjustment |
| currency | CHAR(3) | NOT NULL | Defaults to the MVP currency |
| is_adjusted | BOOLEAN | NOT NULL DEFAULT false | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

Constraints:

```text
UNIQUE (tenancy_id, billing_month)
```

Notes:
- One bill per tenancy per month.
- Status (unpaid/partial/paid) is derived, not stored.
- `final_amount_minor` may differ from `standard_amount_minor` only via a recorded adjustment.
- MVP locks `final_amount_minor = standard_amount_minor` except through a recorded adjustment. The separate `final_amount_minor` field intentionally preserves room for future proration without a schema change.

---

#### payment_allocation

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| transaction_id | UUID | FK → transaction, NOT NULL | tenant_payment only |
| monthly_bill_id | UUID | FK → monthly_bill, NOT NULL | |
| amount_minor | BIGINT | NOT NULL CHECK (> 0) | Positive magnitude |
| currency | CHAR(3) | NOT NULL | Defaults to the MVP currency |
| allocation_type | allocation_type | NOT NULL DEFAULT automatic | |
| reverses_allocation_id | UUID | FK → payment_allocation | Set for reversals |
| created_at | timestamptz | NOT NULL | |

Invariant (enforced in the billing engine within a DB transaction):

```text
SUM(amount_minor) per transaction_id  <=  transaction.amount_minor
```

Notes:
- Immutable. Corrections add a `reversal` or `correction` row; they do not edit or delete.

---

#### advance_movement

Append-only ledger of advance credit events. This exists for auditability and fraud detection. The advance *balance* is still derived; this table is an independent, human-readable record that must reconcile with the derived value.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | Denormalized for scoping |
| tenancy_id | UUID | FK → tenancy, NOT NULL | |
| transaction_id | UUID | FK → transaction, NOT NULL | The tenant payment that owns this advance |
| movement_type | advance_movement_type | NOT NULL | created / applied / reversed |
| amount_minor | BIGINT | NOT NULL CHECK (> 0) | Positive magnitude |
| currency | CHAR(3) | NOT NULL | Defaults to the MVP currency |
| monthly_bill_id | UUID | FK → monthly_bill | Set when movement_type = applied |
| allocation_id | UUID | FK → payment_allocation | Set when applied; links to the allocation created |
| note | TEXT | | Optional context |
| occurred_at | timestamptz | NOT NULL | When the movement happened |
| created_at | timestamptz | NOT NULL | |

Notes:
- Append-only. No `updated_at`. No deletion in normal operation.
- Written atomically in the same database transaction as the corresponding allocation or correction, so it cannot drift under normal operation.
- A payment's advance can be applied in multiple chunks; each application is its own `applied` row.
- Corrections are recorded by appending new rows, never by editing prior rows: undoing a `created` movement appends a `reversed` row, while undoing an `applied` movement appends a new `created` movement (advance restored). A `reversed` row therefore always offsets a `created` movement, which keeps the reconciliation invariant sound.

Why this table exists:
- It gives auditors a clear, readable trail of advance credit (created, applied, reversed) without recomputing from raw allocations.
- It is an independent append-only record that is reconciled against the derived advance balance. If the two disagree, tampering or a bug is flagged. A stored mutable advance balance would not provide this, because it could be edited independently of the transactions.

---

#### bill_adjustment

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| monthly_bill_id | UUID | FK → monthly_bill, NOT NULL | |
| adjustment_type | TEXT | NOT NULL | `rate_change` or `write_off` |
| previous_amount_minor | BIGINT | NOT NULL CHECK (>= 0) | |
| new_amount_minor | BIGINT | NOT NULL CHECK (>= 0) | |
| currency | CHAR(3) | NOT NULL | Defaults to the MVP currency |
| public_note | TEXT | | Visible to tenants; holds the auto-generated note |
| custom_note | TEXT | | Optional public custom note added by admin |
| internal_reason | TEXT | | Admin-only |
| admin_id | UUID | FK → admin_user, NOT NULL | |
| created_at | timestamptz | NOT NULL | |

Notes:
- Append-oriented. Multiple adjustments produce multiple rows.
- On adjustment, `monthly_bill.final_amount_minor` is updated to the latest `new_amount_minor`.
- The adjustment must be visible to tenants per the architecture.
- In MVP a bill adjustment is created only for a rate change or a write-off; arbitrary per-room overrides are not possible. The public note is auto-generated with an optional custom note, and the admin identity is visible to tenants.

---

### 6.6 Utility Bill Payment Ledger

#### utility_provider

Global / system-wide. Seeded once for the whole application, not per organization.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization | Nullable; null = global. MVP uses global. |
| code | TEXT | NOT NULL, UNIQUE | e.g. BEDC |
| display_name | TEXT | NOT NULL | |
| channel_signature | TEXT | NOT NULL | Statement channel, e.g. BEDC |
| reference_label | TEXT | | e.g. "Meter number" |
| is_active | BOOLEAN | NOT NULL DEFAULT true | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

Notes:
- Registry-driven. BEDC is the first provider.
- Global by default so any future landlord automatically gets BEDC pre-loaded.
- `organization_id` stays nullable to allow future per-org custom providers without a schema change, but MVP seeds only global rows.
- New providers are added as rows, not code changes.

---

#### utility_bill_payment

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | |
| transaction_id | UUID | FK → transaction, NOT NULL, UNIQUE | One-to-one |
| provider_id | UUID | FK → utility_provider, NOT NULL | |
| customer_reference | TEXT | | Meter/customer number |
| amount_minor | BIGINT | NOT NULL CHECK (> 0) | |
| currency | CHAR(3) | NOT NULL | |
| payment_datetime | timestamptz | NOT NULL | |
| spend_month | DATE | NOT NULL | First day of payment calendar month, in the org's business timezone |
| import_batch_id | UUID | FK → import_batch | |
| created_at | timestamptz | NOT NULL | |

Notes:
- Records a payment to a provider. Never settles tenant bills.
- `spend_month` drives the month-bounded utility spend report.
- `transaction_id` UNIQUE ensures one provider-payment record per source transaction.

---

### 6.7 Transaction Ingestion

#### import_profile

Global / system-wide. Seeded once for the whole application.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization | Nullable; null = global. MVP uses global. |
| code | TEXT | NOT NULL, UNIQUE | e.g. PAYVICE_AVANTUS |
| display_name | TEXT | NOT NULL | |
| source_type | TEXT | NOT NULL | pdf — CSV/XLSX are out of MVP scope |
| detection_config | JSONB | | Signatures, structural rules |
| parse_config | JSONB | | Date/time/amount/direction rules |
| file_limits | JSONB | | Max size, max pages |
| is_active | BOOLEAN | NOT NULL DEFAULT true | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

Notes:
- PAYVICE_AVANTUS is the first profile, seeded globally.
- Global by default so any future landlord automatically gets the Payvice Avantus parser pre-loaded.
- `organization_id` stays nullable to allow future per-org custom formats without a schema change.
- Detection and parse rules live here so formats are data-driven.

---

#### import_channel_category_mapping

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| import_profile_id | UUID | FK → import_profile, NOT NULL | |
| channel | TEXT | NOT NULL | e.g. FUNDING, BEDC, COMMISSION |
| direction | direction | | Nullable; null = any direction |
| category | TEXT | NOT NULL | tenant_payment / utility_bill_payment / ignored / excluded / unrecognized |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

Constraints:

```text
UNIQUE (import_profile_id, channel, COALESCE(direction, 'ANY'))
CHECK (category IN ('tenant_payment','utility_bill_payment','ignored','excluded','unrecognized'))
```

Notes:
- Implements category mapping as configuration.
- COMMISSION maps to `excluded`, guaranteeing it is never persisted.

---

#### import_batch

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | |
| import_profile_id | UUID | FK → import_profile, NOT NULL | |
| status | import_batch_status | NOT NULL DEFAULT parsing | |
| statement_account_holder | TEXT | | |
| statement_account_number | TEXT | | |
| statement_start_date | DATE | | |
| statement_end_date | DATE | | |
| source_file_sha256 | CHAR(64) | | SHA-256 of the presented file |
| source_filename | TEXT | | Original file name |
| source_page_count | INTEGER | | Pages in the presented file |
| currency | CHAR(3) | NOT NULL | Statement currency; MVP is NGN |
| totals_status | totals_status | | valid / mismatch / missing |
| statement_fingerprint | TEXT | | Content-based duplicate-detection hash |
| ignored_summary | JSONB | | Counts/amounts for ignored categories |
| tenant_payment_row_count | INTEGER | | Persistable tenant-payment rows staged |
| tenant_payment_total_minor | BIGINT | | Staged tenant-payment amount total |
| utility_payment_row_count | INTEGER | | Persistable utility-payment rows staged |
| utility_payment_total_minor | BIGINT | | Staged utility-payment amount total |
| duplicate_row_count | INTEGER | | Rows skipped as duplicates |
| invalid_row_count | INTEGER | | Rows marked invalid |
| unrecognized_row_count | INTEGER | | Rows marked unrecognized |
| uploaded_at | timestamptz | NOT NULL | |
| confirmed_at | timestamptz | | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | | |

Constraints:

```text
UNIQUE (statement_fingerprint) WHERE status IN ('confirmed','completed')
```

Notes:
- The statement-footer credit and debit totals are **not persisted**. Footer totals include commission amounts (ADR-019), so they are compared against the parsed rows in memory and discarded; only `totals_status` is persisted.
- `ignored_summary` may include TRANSFER/CHARGE/VAT counts and totals.
- `ignored_summary` must never include commission data.
- `source_file_sha256` is a hash of the presented file, so the admin can tell that a re-presented file is the same one imported. It is separate from the content-based `statement_fingerprint`, which stays.
- The PDF is not retained (ADR-012, ADR-019); `source_filename` and `source_page_count` are display metadata only.
- Any monetary amounts inside `ignored_summary` and the `*_total_minor` staged-row totals are expressed in the batch `currency`.
- The staged-row counters and their `*_total_minor` amount totals are populated at parse time and are expressed in the batch `currency`.
- The partial unique index prevents committing the same statement twice while still allowing re-import after rejection.

---

#### staged_import_row

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| import_batch_id | UUID | FK → import_batch, NOT NULL | |
| row_category | TEXT | NOT NULL | tenant_payment / utility_bill_payment |
| transaction_date | DATE | NOT NULL | |
| transaction_time | TIME | | |
| channel | TEXT | NOT NULL | |
| direction | direction | NOT NULL | |
| description_raw | TEXT | NOT NULL | |
| counterparty_name | TEXT | | |
| counterparty_reference | TEXT | | |
| amount_minor | BIGINT | NOT NULL CHECK (> 0) | |
| duplicate_key | TEXT | NOT NULL | |
| parse_status | TEXT | NOT NULL | valid / duplicate / invalid / unrecognized |
| parse_error | TEXT | | Reason if not valid |
| committed_transaction_id | UUID | FK → transaction | Set after commit |
| created_at | timestamptz | NOT NULL | |

Constraints:

```text
CHECK (row_category IN ('tenant_payment','utility_bill_payment'))
```

Notes:
- Only persistable categories are staged. Ignored rows are summarized on the batch; commission rows are never staged.
- Survives cold starts/restarts between parse and confirm.
- After commit, rows may be pruned per retention policy (Section 11).

---

### 6.8 Settings and Visibility

#### portal_setting

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| scope_type | TEXT | NOT NULL | organization / property |
| scope_id | UUID | NOT NULL | ID of the org or property |
| setting_key | TEXT | NOT NULL | e.g. default_view |
| setting_value | TEXT | NOT NULL | e.g. property / room / true / false |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |

Constraints:

```text
UNIQUE (scope_type, scope_id, setting_key)
CHECK (scope_type IN ('organization','property'))
```

Notes:
- Implements the configurable visibility policy and default tenant view.
- Resolution order: property-level overrides organization-level; otherwise use application default.
- Example keys:
  - `default_view` → `property` | `room`
  - `allow_other_room_amount_due` → `false` (default). Other rooms see property aggregates by default; per-room amount and status are opt-in by the admin, per organization or property. Tenants cannot opt in or out.
  - `allow_property_utility_spend` → `true`
  - `allow_other_room_tenant_names` → `false`

---

### 6.9 Audit

#### audit_log

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | |
| organization_id | UUID | FK → organization, NOT NULL | |
| actor_type | TEXT | NOT NULL | admin / system / tenant_session |
| actor_id | UUID | | Nullable for system |
| action | TEXT | NOT NULL | e.g. bill.adjust, tenancy.close |
| entity_type | TEXT | | e.g. monthly_bill |
| entity_id | UUID | | |
| metadata | JSONB | | Structured context |
| created_at | timestamptz | NOT NULL | |

Notes:
- Append-oriented. No `updated_at`. No deletion in normal operation.
- Commission data must never appear in `metadata`.
- Tenants do not see the audit log in MVP.

---

## 7. Derived State and Reconciliation

The following values are computed, not stored. They are produced by the billing engine or reporting queries from the authoritative tables.

### 7.1 Monthly bill status

```text
net_allocated = SUM(signed payment_allocation.amount_minor) for the bill

A signed allocation is:
  + amount_minor  for allocation_type in (automatic, manual, correction)
  - amount_minor  for allocation_type = reversal

if net_allocated = 0                → unpaid
if 0 < net_allocated < final_amount → partial
if net_allocated >= final_amount    → paid
```

### 7.2 Bill remaining due

```text
remaining = final_amount_minor - net_allocated
```

### 7.3 Tenancy outstanding balance

```text
outstanding = SUM(remaining) across the tenancy's bills where remaining > 0
```

### 7.4 Advance credit (derived balance + movement log)

The advance **balance** is derived. It is not stored as a mutable number.

```text
advance_balance = SUM(derived_unallocated)
                  across matched tenant_payment transactions
                  where unallocated remainder > 0
```

Every change to advance credit is also written to the append-only `advance_movement` table (created / applied / reversed). The balance stays derived for correctness; the movement log exists for auditability and tamper detection.

Advance is always linked to its original payment because it is derived from that payment's unallocated remainder, and every movement row references that payment.

Applying advance to a newly generated bill creates a `payment_allocation` from the original payment and a corresponding `applied` advance movement. No separate stored advance balance is needed.

### 7.5 Advance reconciliation invariant (fraud detection)

For every `tenant_payment` transaction, two independent values must agree:

```text
derived_unallocated =
    transaction.amount_minor
    - SUM(signed payment_allocation.amount_minor for that transaction)

(signed as defined in Section 7.1: plus for automatic/manual/correction, minus for reversal)

logged_advance =
    SUM(advance_movement.amount_minor where movement_type = 'created')
    - SUM(advance_movement.amount_minor where movement_type = 'applied')
    - SUM(advance_movement.amount_minor where movement_type = 'reversed')
    (all for that transaction)

REQUIRED: derived_unallocated == logged_advance
```

If these disagree, the system flags a reconciliation error. Because the movement log is append-only and independent of the derived computation, tampering with allocations (or with the log) breaks the equality and is detected. This is the mechanism that makes advance credit auditable and fraud-resistant.

This identity assumes `reversed` only ever offsets a `created` movement. Restoring advance after an allocation is reversed is recorded as a new `created` movement, not as `reversed`; recording it as `reversed` would double-subtract and break the equality.

### 7.6 Net tenant position

```text
net_position = outstanding - advance_balance
```

### 7.7 Utility spend by month

```text
spend = SUM(utility_bill_payment.amount_minor)
        grouped by provider_id and spend_month
```

Notes:
- Month-bounded by the payment's calendar month, computed in the org's business timezone.
- Does not reconcile tenant balances.

### 7.8 Optional read model

For reporting performance, a database view or read model may later expose:

- Tenant billing summary.
- Property billing summary.
- Utility spend by month.
- Advance movement history.

For MVP, these can be plain queries. A materialized read model is a future optimization, not a requirement.

---

## 8. Cross-Table Constraints and Invariants

Some invariants span rows and are enforced in the service layer inside database transactions, not by single-column constraints.

1. **Allocation cap.** The sum of signed allocations for a transaction (as defined in Section 7.1) must not exceed the transaction amount.
2. **Advance reconciliation.** The derived advance balance must equal the logged advance per Section 7.5. Violations are flagged.
3. **Ledger separation.** Utility bill payments must never create payment allocations. Tenant payments must never create utility bill payments.
4. **Commissions never stored.** No row with channel `COMMISSION` may reach `transaction` or `staged_import_row`.
5. **One active tenancy per room.** Enforced by partial unique index.
6. **One bill per tenancy per month.** Enforced by unique constraint.
7. **Bill amount changes are audited.** Any change to `monthly_bill.final_amount_minor` must have a corresponding `bill_adjustment` row.
8. **Advance movements are atomic with allocations.** An `applied` advance movement and its allocation are written in the same transaction.
9. **Organization scoping.** All scoped queries must filter by `organization_id`.

---

## 9. Indexes

Recommended indexes beyond primary keys and unique constraints.

| Table | Index | Purpose |
|---|---|---|
| transaction | (organization_id, transaction_date) | Date-scoped ledger queries |
| transaction | (tenancy_id) | Tenant payment lookups |
| transaction | (import_batch_id) | Batch tracing |
| transaction | (record_category) | Ledger filtering |
| monthly_bill | (billing_month) | Month reports |
| monthly_bill | (organization_id, billing_month) | Scoped month reports |
| payment_allocation | (transaction_id) | Allocation lookups |
| payment_allocation | (monthly_bill_id) | Bill allocated totals |
| advance_movement | (transaction_id) | Per-payment advance trail |
| advance_movement | (tenancy_id, occurred_at) | Tenancy advance history |
| utility_bill_payment | (provider_id, spend_month) | Utility spend report |
| utility_bill_payment | (organization_id, spend_month) | Scoped spend report |
| sender_alias | (organization_id, normalized_name) | Matching |
| staged_import_row | (import_batch_id) | Staging review |
| audit_log | (organization_id, created_at) | Audit queries |
| audit_log | (entity_type, entity_id) | Entity history |
| import_batch | (statement_fingerprint) | Duplicate statement detection |
| tenant_login_attempt | (tenancy_id, attempted_at) | Tenancy-scoped login-attempt history |
| tenant_login_attempt | (source_ip, attempted_at) | IP-scoped rate limiting |
| admin_login_attempt | (admin_user_id, attempted_at) | Admin-scoped login-attempt history |
| admin_login_attempt | (source_ip, attempted_at) | IP-scoped admin rate limiting |

---

## 10. Duplicate-Detection Keys

### 10.1 Transaction duplicate key

For persistable rows, the duplicate key is a deterministic hash of:

```text
statement_account_number
+ normalized transaction date/time
+ channel
+ normalized description
+ direction
+ amount_minor
```

Stored on `transaction.duplicate_key` (unique) and `staged_import_row.duplicate_key`.

### 10.2 Statement fingerprint

The import batch fingerprint is a hash of:

```text
statement_account_number
+ statement period
+ ordered persistable row duplicate keys
```

Used to detect re-importing the same statement.

### 10.3 Behavior

| Situation | Behavior |
|---|---|
| Same statement imported again | Flagged/rejected as duplicate statement |
| Same row already committed | Skipped as duplicate |
| Two identical rows in one statement | Flagged for admin review |
| Duplicate found after commit | Handled via reversal, not deletion |

---

## 11. Immutability and Retention

### 11.1 Immutable tables

These are append-oriented and must not be silently edited or deleted:

- transaction
- payment_allocation
- advance_movement
- bill_adjustment
- standard_amount_change
- utility_bill_payment
- audit_log

Corrections use reversal/correction records.

### 11.2 Mutable tables

These may be updated normally:

- organization, property, room
- tenancy, tenant, sender_alias
- monthly_bill (amount changes only via adjustment)
- billing_config, billing_override, portal_setting
- import_profile, import_channel_category_mapping, import_batch
- utility_provider
- tenant_access_credential (rotation)
- admin_user

This list equals exactly the tables carrying `updated_at`. Five write-once operational tables are excluded: `tenant_session`, `admin_session`, `staged_import_row`, `tenant_login_attempt`, and `admin_login_attempt`. `tenant_session`, `admin_session` and `staged_import_row` are opened once and closed via semantic fields (`revoked_at`, `committed_transaction_id`) rather than in-place edits; `tenant_login_attempt` and `admin_login_attempt` are write-once, prunable operational data for rate limiting. All five are governed by Sections 11.3, 11.4 and 11.6. `tenant_login_attempt` and `admin_login_attempt` are operational, prunable data; they are not financial tables and are not part of immutable financial history.

### 11.3 Staged row retention

After an import batch is committed, `staged_import_row` entries may be pruned after a retention window, because the committed `transaction` rows are the source of truth. Pruning policy is an open question. `staged_import_row` is staging-only operational data and is not part of immutable financial history.

### 11.4 Session retention

Expired or revoked `tenant_session` and `admin_session` rows may be pruned periodically. They are operational/ephemeral data, not financial history.

### 11.5 Commission data

Commission data is never stored anywhere and therefore has no retention concern. It must also be excluded from logs and error output.

### 11.6 Login-attempt retention

`tenant_login_attempt` and `admin_login_attempt` rows may be pruned periodically. Login attempts are operational/ephemeral rate-limiting data, not financial history.

This classification covers every table specified in Section 6.

---

## 12. Migration Strategy

- Use Alembic for schema migrations.
- Every schema change ships with a migration.
- Migrations must be reversible where practical.
- Enum changes should be handled carefully to avoid locking issues on production tables.
- Seed data for MVP:
  - One default organization.
  - One admin user.
  - One global import profile: `PAYVICE_AVANTUS` (organization_id null).
  - Channel/category mappings for the Payvice Avantus profile.
  - One global utility provider: `BEDC` (organization_id null).
  - One default `billing_config` row for the organization with the deployment's standard monthly amount (admin-configurable and required before the first lazy bill generation).
  - Default portal settings: `default_view` = `property`, `allow_other_room_amount_due` = `false` (per-room amount/status is admin opt-in), `allow_property_utility_spend` = `true`, `allow_other_room_tenant_names` = `false`.

---

## 13. Open Database Questions

1. Should reports use plain queries or a dedicated read model/view in MVP?
2. What is the retention window for `staged_import_row` after commit?
3. Should expired/revoked `tenant_session` rows be pruned automatically, and how often?
4. Is a partial unique index acceptable on the target free Postgres host for the statement fingerprint and active-tenancy rules?
   Decision: Acceptable. The hosting provider must support partial unique indexes (03 §6.4); SQLite local development uses sqlite_where, PostgreSQL uses postgresql_where.
5. Should `sender_alias.normalized_name` normalization rules be enforced in the database or only in the application layer?
6. How often should the advance reconciliation invariant be checked (on every allocation, on demand, or as a periodic audit report)?

Resolved:

- Advance credit uses a derived balance plus an append-only movement ledger for auditability. No stored mutable advance balance.
- `utility_provider` and `import_profile` are global / system-wide, seeded once, with nullable `organization_id` reserved for future per-org overrides.

---

## 14. Summary

This design gives you:

- A clean two-ledger structure at the data level.
- Strong integrity constraints for financial records.
- Derived state computed from authoritative tables.
- An append-only advance movement ledger with a reconciliation invariant for fraud detection.
- Global, registry-driven providers and import profiles.
- Configuration-driven ingestion and visibility.
- A hard guarantee (via CHECK constraints) that commissions are never persisted.
- UUID identifiers plus server-side authorization for tenant isolation.
- A migration path via Alembic.
