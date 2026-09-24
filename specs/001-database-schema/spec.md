# Feature Specification: Full MVP Database Schema

**Feature Branch**: `001-database-schema`

**Created**: 2026-09-21

**Status**: Draft

**Input**: User description: "Implement full schema" (source of truth: `docs/03-mvp-architecture.md`, `docs/04-database.md`, and `.specify/memory/constitution.md`)

## User Scenarios & Testing *(mandatory)*

This feature delivers the complete database layer — every entity, relationship, constraint, derived-state computation, and the migration/seed packaging specified in `docs/04-database.md` — as a single coherent, reversible, portable schema. The users of this feature are the administrators who rely on the persisted data, and the developers who must stand up and evolve the schema without corrupting financial history. User stories are ordered as deployable slices following the domain modules in `docs/03` §6.7, so each slice is independently verifiable while still composing into the one integrated schema (`docs/04` §8 cross-table invariants depend on all slices being present).

### User Story 1 - Structural & Identity Foundation (Priority: P1)

A fresh deployment begins by establishing the structural and identity tables on which every financial record depends: organizations, properties, rooms, tenancies, tenants, sender aliases, admin users, tenant access credentials, and tenant sessions. An administrator must be able to set up the org hierarchy and authentication storage as the prerequisite to any financial record.

**Why this priority**: No other module exists without this foundation. The org root (ADR-001) is the isolation boundary for all scoped queries, and every later slice is reachable through it.

**Independent Test**: Can be fully tested by applying the schema and verifying the org/property/room/tenancy tables exist with UUID primary keys and org scoping, the single-active-tenancy-per-room rule holds, and the identity/auth tables (admin, access credential, session) enforce their integrity rules — delivering a usable org hierarchy with no financial records required.

**Acceptance Scenarios**:

1. **Given** the schema is applied to a fresh database, **When** the org-hierarchy and identity tables are inspected, **Then** `organization`, `property`, `room`, `tenancy`, `tenant`, and `sender_alias` all exist with UUID primary keys and `created_at` timestamps.
2. **Given** one active tenancy for a room, **When** an administrator attempts to open a second active tenancy for the same room, **Then** the schema rejects it (partial unique index on active tenancy per room).
3. **Given** a tenancy with a sender alias, **When** a duplicate normalized sender name is added for that tenancy, **Then** it is rejected by the `(tenancy_id, normalized_name)` uniqueness rule.
4. **Given** an active access credential, **When** it is rotated, **Then** the stored version increments and previously issued sessions no longer satisfy the validity rule.

---

### User Story 2 - Billing Configuration (Priority: P1)

Configuration governing how bills are produced must be persisted before any bill can be generated: the org-wide standard monthly amount, per-tenancy/per-month bill-or-skip overrides, and an append-only history of standard-amount changes. An administrator configures the standard amount once; it applies uniformly across all rooms (`docs/03` §10.3).

**Why this priority**: Bills snapshot the standard amount and consult overrides at generation; the billing slice cannot function without this configuration slice.

**Independent Test**: Can be fully tested by verifying the `billing_config` (org-wide default, money column, currency), `billing_override` (per-tenancy/per-month uniqueness, `bill`/`skip` decision only), and `standard_amount_change` (append-only change history with `previous`/`new` amounts).

**Acceptance Scenarios**:

1. **Given** no property scoping, **When** the standard amount is set, **Then** it is stored as the org-wide `billing_config` with an integer minor-unit amount and explicit currency.
2. **Given** an override for a tenancy/month, **When** a second override for the same tenancy/month is attempted, **Then** it is rejected by the `(tenancy_id, billing_month)` uniqueness rule.
3. **Given** a standard-amount change, **When** the change is recorded, **Then** an immutable row capturing previous and new amounts, the admin, and its effective time is appended, never edited.

---

### User Story 3 - Tenant Payment Ledger & Billing (Priority: P1)

The core financial domain (`docs/03` §6.7.6): raw tenant-payment transactions, monthly bills, payment allocations, advance movements, and bill adjustments. This slice is the highest-risk module — money is stored as integer minor units, financial history is append-only, advance credit is derived and reconciled against a movement ledger, and commission rows are impossible to persist.

**Why this priority**: This is the heart of the product and the highest-risk financial code (constitution Principle I). Its correctness is non-negotiable and must be proven by testable invariants.

**Independent Test**: Can be fully tested by persisting a matched tenant payment, allocating it to a generated monthly bill, and verifying: monetary values are integer minor units with currency, the advance reconciliation identity (derived unallocated == logged advance) holds, the allocation cap is not exceeded, and UPDATE/DELETE on any financial table is rejected.

**Acceptance Scenarios**:

1. **Given** a tenant-payment transaction, **When** it persists, **Then** it carries `BIGINT` minor-unit amount, explicit `currency`, `duplicate_key` unique, and a `record_category` restricted to `tenant_payment` or `utility_bill_payment`.
2. **Given** a matched tenant payment allocated to a monthly bill, **When** the signed allocations for the transaction are summed, **Then** they never exceed the transaction amount (allocation cap).
3. **Given** a monthly bill, **When** its final amount is changed, **Then** a corresponding `bill_adjustment` row is recorded (no silent amount rewrite).
4. **Given** an overpaid payment, **When** the advance reconciliation is computed, **Then** the derived unallocated balance equals the logged advance movements for that payment.
5. **Given** a settled bill, **When** a reversal or correction is needed, **Then** it is represented as a new reversal/correction row, never by editing or deleting the original.

---

### User Story 4 - Utility Bill Payment Ledger (Priority: P1)

The second, strictly separate ledger (`docs/03` §3.2, ADR-017): a registry of utility providers and the outgoing utility bill payments made to them, enabling month-bounded spend reporting. These payments never settle tenant bills and never enter tenancy matching.

**Why this priority**: Ledger separation is a foundational invariant; both ledgers must exist together for the integrity constraints that keep them apart to be enforced.

**Independent Test**: Can be fully tested by registering a global utility provider and recording a provider payment, then verifying the payment ties one-to-one to a source transaction, never carries tenancy matching state, and aggregates correctly by provider/calendar month.

**Acceptance Scenarios**:

1. **Given** a global utility provider (e.g. BEDC), **When** a provider payment is recorded, **Then** it is denominated in minor units, has an explicit currency, and its `transaction_id` is unique (one provider-payment per source transaction).
2. **Given** a provider payment, **When** its matching status is inspected, **Then** it is marked `not_applicable` and never participates in tenancy matching.
3. **Given** provider payments across months, **When** utility spend is computed, **Then** it aggregates correctly by provider and payment calendar month without reconciling tenant balances.

---

### User Story 5 - Transaction Ingestion (Priority: P2)

The staged, admin-confirmed intake path (`docs/03` §6.7.4): import profiles, channel/category mappings, import batches, and staged rows. Ingestion is the trust boundary — records are staged and reviewed before commit, duplicates are detected, and commission rows are never staged (`docs/04` §8.4, constitution Principle III).

**Why this priority**: Essential for the product's primary data entry, but it depends on the ledger tables being present to reference; hence P2 after the ledgers.

**Independent Test**: Can be fully tested by defining a global import profile with channel/category mappings, staging rows on an import batch, and verifying a valid staged row commits to a transaction while a commission-mapped channel is never staged and the batch fingerprint uniqueness is enforced.

**Acceptance Scenarios**:

1. **Given** a global import profile, **When** its channel/category mappings are defined, **Then** only `tenant_payment`, `utility_bill_payment`, `ignored`, `excluded`, and `unrecognized` categories are permitted.
2. **Given** an import batch, **When** a row maps to `COMMISSION`, **Then** it is never written to a staged row or transaction (channel `COMMISSION` cannot reach persistence).
3. **Given** a confirmed import batch, **When** the same statement is imported again, **Then** it is rejected by the statement-fingerprint uniqueness rule restricted to confirmed/completed batches.

---

### User Story 6 - Visibility, Settings, and Audit (Priority: P2)

The cross-cutting concern of configurable tenant visibility and append-only auditing (`docs/03` §9 and §6.7.10): `portal_setting` and `audit_log`.

**Why this priority**: Not needed to record money, but required to ship a compliant, auditable product; placed after the financial and ingestion slices.

**Independent Test**: Can be fully tested by persisting a scoped portal setting and writing audit rows, then verifying scope/key uniqueness, the append-only nature of the audit log, and that commission data cannot be recorded.

**Acceptance Scenarios**:

1. **Given** a portal setting, **When** a second setting with the same scope and key is attempted, **Then** it is rejected by the `(scope_type, scope_id, setting_key)` uniqueness rule.
2. **Given** an audit entry, **When** it is inspected, **Then** it records actor, action, entity, structured metadata, and created time with no `updated_at` (append-only).
3. **Given** the audit log, **When** commission data is involved, **Then** no commission value appears in any audit metadata.

---

### User Story 7 - Migration, Portability, and Seed (Priority: P3)

The operational wrapper that makes the schema usable across environments: one reversible migration delivering the whole schema, consistent structural equivalence between the production database engine and the local-development engine, and idempotent seed data for the first organization, admin, global import profile/utility provider, default billing config, and portal settings (`docs/04` §12).

**Why this priority**: Needed to ship and demonstrate, but only meaningful once all schema slices exist.

**Independent Test**: Can be fully tested by applying the migration to a fresh database, running the seed, then reversing the migration and re-applying it with no errors, and confirming the resulting structure is equivalent on both the production and local database engines.

**Acceptance Scenarios**:

1. **Given** a fresh database, **When** the migration is applied, **Then** it completes with no errors and creates the full set of tables, indexes, and constraints.
2. **Given** a seeded database, **When** seeding is run again, **Then** it is idempotent and produces no duplicates or errors.
3. **Given** a local development database, **When** the migration is applied, **Then** the resulting structure is functionally equivalent to the production database structure.

### Edge Cases

- What happens when an import batch is rejected and then re-imported? (Partial unique index must allow a new batch once the previous failed status is no longer `confirmed`/`completed`.)
- What happens when a financial record needs correction after commitments exist? (New reversal/correction rows, never edits or hard deletes.)
- What happens with advance credit when an applied allocation is reversed? (Restored as a new `created` movement, not a `reversed` one, keeping the reconciliation identity sound.)
- What happens when the org-wide standard amount is changed after bills exist? (Already-generated bills are snapshot; unsettled current-month bills change only via recorded adjustments.)
- What happens on a duplicate transaction row within one statement? (Flagged for admin review, not silently committed.)
- What happens if a tenant payment and a utility bill payment are conflated? (Schema-level ledger separation rejects any cross-settlement.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST persist every entity specified in `docs/04` §6 — `admin_user`, `tenant_access_credential`, `tenant_session`, `organization`, `property`, `room`, `tenancy`, `tenant`, `sender_alias`, `billing_config`, `billing_override`, `standard_amount_change`, `transaction`, `monthly_bill`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `utility_provider`, `utility_bill_payment`, `import_profile`, `import_channel_category_mapping`, `import_batch`, `staged_import_row`, `portal_setting`, and `audit_log` — with the columns, types, and nullability in `docs/04` §6.
- **FR-002**: System MUST use UUID primary keys on every table.
- **FR-003**: System MUST store every monetary amount as an integer minor-unit (`BIGINT`) value with an explicit `currency CHAR(3)` column, with no floating-point storage, across all money-bearing tables (constitution Principle I).
- **FR-004**: System MUST scope financial and structural queries by `organization_id` (and `property_id` / `tenancy_id` where relevant); key financial tables MUST carry `organization_id` (constitution Database & Schema).
- **FR-005**: System MUST enforce all enumerated domains from `docs/04` §4: `tenancy_status`, `record_category`, `direction`, `matching_status`, `allocation_type`, `advance_movement_type`, `import_batch_status`, and `totals_status`.
- **FR-006**: System MUST guarantee strict two-ledger separation: utility bill payments MUST never carry tenancy matching state or trace to billing allocations, and tenant payments MUST never be miscategorized as provider payments (constitution Principle IV).
- **FR-007**: System MUST render it impossible to persist commission data: no table, column, index, or constraint MAY accept a commission-mapped channel, and the `record_category` CHECK MUST restrict persisted rows to `tenant_payment`/`utility_bill_payment` only (constitution Principle III).
- **FR-008**: System MUST make all financial history tables append-only (immutable): `transaction`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `utility_bill_payment`, and `audit_log` MUST reject in-place edits and hard deletes once written (constitution Principle I).
- **FR-009**: System MUST store derived state only by computation from authoritative records: bill status, bill remaining, tenancy outstanding, advance balance, net position, and utility spend MUST be derivable via the computations in `docs/04` §7 and MUST NOT be stored as independently mutable columns.
- **FR-010**: System MUST provision the append-only advance movement ledger and enforce the reconciliation invariant that derived unallocated balance equals the logged advance movements per `docs/04` §7.5.
- **FR-011**: System MUST expose the duplicate-detection keys in `docs/04` §10: a unique `duplicate_key` on transactions and staged rows, and a statement fingerprint with a partial unique index on import batches in `confirmed`/`completed` status.
- **FR-012**: System MUST enforce the cross-table constraints in `docs/04` §8, enforceable within database transactions at the service layer: allocation cap, advance reconciliation, ledger separation, commissions-never-stored, one-active-tenancy-per-room, one-bill-per-tenancy-per-month, audited bill-amount changes, and organization scoping.
- **FR-013**: System MUST create the tables, unique constraints, and per-query performance indexes recommended in `docs/04` §9.
- **FR-014**: System MUST deliver the schema as reversible migrations, such that the schema can be applied and rolled back cleanly, and MUST be structurally consistent between the production database engine and the local-development database engine (constitution Database & Schema; `docs/04` §12).
- **FR-015**: System MUST provide idempotent seed data for the MVP: one organization, one admin user, one global import profile (`PAYVICE_AVANTUS`), channel/category mappings, one global utility provider (`BEDC`), a default org-wide `billing_config`, and default portal settings (`docs/04` §12).

### Key Entities *(include if feature involves data)*

- **organization**: Root isolation boundary; owns users, properties, and all scoped financial records.
- **property / room**: Physical hierarchy; a room persists across tenancies with one active tenancy.
- **tenancy / tenant / sender_alias**: Occupancy period and privacy boundary (tenancy); namespace for matched sender names used in `tenant_payment` matching.
- **admin_user / tenant_access_credential / tenant_session**: Identity and authentication; hashed credentials, versioned for revocation, sessions with validity rules.
- **billing_config / billing_override / standard_amount_change**: Org-wide standard amount, per-tenancy/month bill-or-skip decisions, and append-only rate-change history.
- **transaction**: Normalized source row (tenant_payment or utility_bill_payment), append-only, with duplicate key.
- **monthly_bill**: Per-tenancy/month billing state snapshotting the standard amount.
- **payment_allocation**: Links a tenant payment to a monthly bill; carries reversal/correction semantics.
- **advance_movement**: Append-only advance-credit event ledger (created/applied/reversed) reconciled against the derived balance.
- **bill_adjustment**: Recorded change to a bill's final amount (rate_change or write_off).
- **utility_provider / utility_bill_payment**: Global provider registry and outgoing spend records (separate ledger).
- **import_profile / import_channel_category_mapping / import_batch / staged_import_row**: Configuration-driven, staged, admin-confirmed ingestion.
- **portal_setting**: Configurable visibility and default-view policy.
- **audit_log**: Append-only record of admin/system actions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fresh database can apply the full schema from zero with no errors in under 2 minutes on standard infrastructure.
- **SC-002**: 100% of the append-only financial tables reject in-place updates and hard deletes at the storage layer once a row is written.
- **SC-003**: 0 commission rows can be persisted, staged, or logged across the schema (verified by attempting every commission-mapped channel).
- **SC-004**: The advance reconciliation invariant (derived unallocated balance == logged advance movements) holds for: overpayment, partial application, applied-then-reversed, and multi-chunk application scenarios.
- **SC-005**: Every migration is reversible — a complete up-then-down cycle (and re-apply) leaves the database clean and seed-free without errors.
- **SC-006**: Seeding is idempotent — running seed twice yields the same single set of reference and configuration rows.
- **SC-007**: The schema structure is functionally equivalent on the production database engine and the local-development engine, so locally generated migrations and invariants reproduce in production without divergence.

## Assumptions

- The complete `docs/04-database.md` schema is the source of truth; this feature implements it fully, with no reduction or ratio change. This decision was confirmed by reviewing `docs/03-mvp-architecture.md` §6.7, which shows the schema composing one integrated, cohesive artifact (cross-table invariants in `docs/04` §8 span slices), so a single spec (organized by module) is used rather than multiple sub-feature specs.
- The MVP currency is NGN (ISO 4217); monetary examples use ₦.
- Identifiers, money handling, org scoping, immutability, and ledger separation follow the ratified constitution (`.specify/memory/constitution.md`) and the locked ADRs (ADR-017, ADR-021, ADR-025, ADR-019, ADR-001).
- `docs/04` §13 open questions are intentionally **out of scope** for this schema-creation feature and use their `docs/04`-suggested defaults: reports use plain queries (no materialized read model) per §7.8; staged-row and expired-session pruning are future operational concerns (the tables still carry the columns needed to support them) per §11.3–11.4; partial unique indexes are assumed acceptable per §7 (§8.4, §10.2).
- The schema is delivered as one coherent, reversible baseline migration chain; per-module migration splitting is not required because nothing is yet deployed that would need independent versioning.
- The architectural choice of the data-access layer and migration tooling is already locked by `docs/03` §6.6 and the constitution; this spec captures the deliverable and its invariants, and the isolated tooling references reflect already-decided constraints rather than new implementation detail.
- The production database engine is PostgreSQL with SQLite used only for local development (constitution Database & Schema).
- The first implementation pass targets **User Story 1 only** (Structural & Identity Foundation), per the MVP-first strategy in `tasks.md`; the remaining user stories and polish are planned for subsequent passes.
- Locally, **SQLite is the only validated engine** (no local PostgreSQL on the dev machine). PostgreSQL-native DDL — immutable-table triggers and `postgresql_where` partial unique indexes (spec §3 SC-002) — is authored in the code now but **validated in CI/deploy**, not locally. Consequently SC-005/SC-006/SC-007 and the Postgres-native acceptance scenarios are confirmed in CI/deploy; the SQLite scenarios are confirmed locally.