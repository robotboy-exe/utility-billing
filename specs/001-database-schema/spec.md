# Feature Specification: Database Schema Foundation

**Feature Branch**: `001-database-schema`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "Feature: database schema foundation for the Utility Billing MVP. Source of truth: docs/04-database.md (all 28 tables; every table, column, constraint and index is defined there), plus docs/03-mvp-architecture.md, docs/09-security.md and .specify/memory/constitution.md. Do not invent, rename or drop tables or columns. If something is missing or contradictory, list it as an open question instead of deciding."

## Overview

This feature delivers the persistence foundation for the Utility Billing MVP: every table, relationship, constraint, index, derived-state rule, and the migration and seed packaging defined in `docs/04-database.md`. `docs/04` is the single source of truth for the schema; this specification states *what must exist and be enforceable* and cites `docs/04` by section rather than restating column definitions, so the schema is maintained in one place.

The scope is the schema and its seed data **only**. No API, UI, authentication logic, or ingestion/parsing logic is delivered here — those are separate features. The schema must nevertheless be shaped so those features can be built on it, and so the financial invariants in the constitution are enforceable at the storage layer.

User stories below are small, independently testable slices in dependency order: each slice references tables that already exist in earlier slices, so a slice can be applied and verified on its own.

## Clarifications

### Session 2026-10-10

- Q: How are enumerations represented in the schema? → A: TEXT columns with CHECK constraints on both SQLite and PostgreSQL (`docs/04` §4).
- Q: Are the four inline value sets constrained in the schema? → A: Yes — CHECK constraints are defined in `docs/04` §6 for `billing_override.decision`, `bill_adjustment.adjustment_type`, `staged_import_row.parse_status`, and `audit_log.actor_type`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Organization and Admin Identity (Priority: P1)

A fresh deployment establishes the isolation root and the single administrator account: the `organization` to which every scoped record belongs, and the `admin_user` that owns it (MVP: one admin per organization). This is the prerequisite for every other table.

**Why this priority**: Nothing else can exist without the organization root (ADR-001) and the admin actor referenced by many tables. It is the first dependency in the graph.

**Independent Test**: Apply the schema and verify `organization` and `admin_user` exist with UUID primary keys, `admin_user.organization_id` is a NOT NULL foreign key to `organization`, `admin_user.email` is unique, `organization.timezone` defaults to `Africa/Lagos`, and money/currency/timestamp conventions hold.

**Acceptance Scenarios**:

1. **Given** a fresh database, **When** the schema is applied, **Then** `organization` and `admin_user` exist exactly as defined in `docs/04` §6.2 (`organization`) and §6.1 (`admin_user`), with UUID primary keys.
2. **Given** a new organization, **When** it is persisted without a timezone, **Then** `organization.timezone` defaults to `Africa/Lagos` (`docs/04` §6.2, ADR-028), and the database stores the given string.
3. **Given** an existing admin email, **When** a second `admin_user` with the same email is inserted, **Then** it is rejected by the `email` uniqueness constraint (`docs/04` §6.1).
4. **Given** an `admin_user` row, **When** an `organization_id` that does not exist is assigned, **Then** the foreign key rejects it.
5. **Given** an `organization`, **When** `timezone` is set to an invalid IANA name, **Then** the model rejects it before persistence (`docs/04` §6.2; FR-026).

---

### User Story 2 - Property, Room, Tenancy, and Tenant Access (Priority: P2)

The physical and occupancy hierarchy is established: `property` and `room` (a room persists across tenancies), `tenancy` (the occupancy period, with at most one active tenancy per room), `tenant`, `sender_alias` (the namespace used to match tenant payments), and the tenancy-bound access identity (`tenant_access_credential`, `tenant_session`).

**Why this priority**: Tenancy is the privacy and billing boundary; every payment and bill attaches to a tenancy, so this slice must exist before any financial slice.

**Independent Test**: Apply the schema and verify the hierarchy tables exist per `docs/04` §6.2–§6.3, that a second active tenancy for the same room is rejected (partial unique index), that `(tenancy_id, normalized_name)` is unique on `sender_alias`, that `tenant_access_credential.tenancy_id` is unique, and that session validity fields exist.

**Acceptance Scenarios**:

1. **Given** a room with one active tenancy, **When** a second `tenancy` for that room with `status = active` is inserted, **Then** it is rejected by the partial unique index `UNIQUE (room_id) WHERE status = 'active'` (`docs/04` §6.3, §8.5, §13 item 4).
2. **Given** a tenancy, **When** two `sender_alias` rows with the same `normalized_name` are inserted, **Then** the second is rejected by `UNIQUE (tenancy_id, normalized_name)` (`docs/04` §6.3).
3. **Given** a tenancy, **When** a second `tenant_access_credential` for the same `tenancy_id` is inserted, **Then** it is rejected by the unique constraint on `tenancy_id` (`docs/04` §6.1).
4. **Given** an active credential at version *n*, **When** a session issued at version *n* is evaluated after the credential is rotated to *n+1*, **Then** the validity rule in `docs/04` §6.1 no longer holds for that session.
5. **Given** a `sender_alias` whose stored normalization is incorrect, **When** it is updated, **Then** the update succeeds because `sender_alias` is a mutable table carrying `updated_at` (`docs/04` §6.3, §11.2).

---

### User Story 3 - Transaction Ingestion Staging (Priority: P3)

The configuration-driven, staged intake structures are established: `import_profile`, `import_channel_category_mapping`, `import_batch`, and `staged_import_row`. These tables exist so that `transaction.import_batch_id` (User Story 4) can reference a batch; parsing and confirmation logic are out of scope.

**Why this priority**: The persisted `transaction` row references `import_batch`, so the ingestion structures must exist before the ledger slice. It is also the trust boundary for the "commissions are never stored" guarantee.

**Independent Test**: Apply the schema and verify the ingestion tables exist per `docs/04` §6.7, that the category CHECK and mapping uniqueness constraints hold, that a commission-mapped channel cannot be staged, and that the statement-fingerprint partial unique index exists.

**Acceptance Scenarios**:

1. **Given** a global import profile, **When** an `import_channel_category_mapping` is inserted with a `category` outside `tenant_payment`, `utility_bill_payment`, `ignored`, `excluded`, `unrecognized`, **Then** it is rejected by the CHECK constraint (`docs/04` §6.7).
2. **Given** a profile/channel/direction mapping, **When** a duplicate mapping for the same `(import_profile_id, channel, direction)` is inserted, **Then** it is rejected by the uniqueness rule using `COALESCE(direction, 'ANY')` (`docs/04` §6.7).
3. **Given** a confirmed or completed batch with a statement fingerprint, **When** another batch with the same `statement_fingerprint` in `confirmed`/`completed` status is inserted, **Then** it is rejected by the partial unique index; a batch whose prior status is `rejected`/`failed` does not block a new one (`docs/04` §6.7, §8, §13 item 4).
4. **Given** a `staged_import_row`, **When** a `row_category` outside `tenant_payment`/`utility_bill_payment` is inserted, **Then** it is rejected by the CHECK constraint (`docs/04` §6.7).

---

### User Story 4 - Ledgers and Billing Tables (Priority: P4)

The financial core is established: billing configuration (`billing_config`, `billing_override`, `standard_amount_change`), the tenant payment ledger (`transaction`, `monthly_bill`, `payment_allocation`, `advance_movement`, `bill_adjustment`), and the strictly separate utility bill payment ledger (`utility_provider`, `utility_bill_payment`). Money is stored as integer minor units with explicit currency; financial history tables are append-only; commission rows cannot be persisted; and the two ledgers cannot cross-settle.

**Why this priority**: This is the highest-risk domain (constitution Principle I). It depends on User Stories 1–3 (organization, tenancy, import batch references) and is the reason the schema exists.

**Independent Test**: Apply the schema, then verify billing config uniqueness, one-bill-per-tenancy-per-month, `transaction.duplicate_key` uniqueness and the `record_category` CHECK, `utility_bill_payment.transaction_id` uniqueness, and that every table in `docs/04` §11.1 rejects UPDATE and DELETE while all monetary columns are integer minor units with explicit currency.

**Acceptance Scenarios**:

1. **Given** an org-wide `billing_config` with a standard amount, **When** the amount is stored, **Then** `standard_amount_minor` is an integer minor-unit value with an explicit `currency`, and `property_id` may be null for the org-wide default (`docs/04` §6.4).
2. **Given** a `billing_override` for a tenancy and billing month, **When** a second override for the same `(tenancy_id, billing_month)` is inserted, **Then** it is rejected by the unique constraint (`docs/04` §6.4).
3. **Given** a monthly bill for a tenancy and month, **When** a second bill for the same `(tenancy_id, billing_month)` is inserted, **Then** it is rejected (`docs/04` §6.5, §8.6).
4. **Given** a `transaction` row, **When** a `record_category` other than `tenant_payment` or `utility_bill_payment` is inserted, **Then** it is rejected by the CHECK constraint, so no commission row can be persisted (`docs/04` §6.5, §8.4).
5. **Given** a `transaction` with a `duplicate_key`, **When** a second transaction with the same `duplicate_key` is inserted, **Then** it is rejected (`docs/04` §6.5, §10.1).
6. **Given** a `utility_bill_payment`, **When** a second provider payment for the same `transaction_id` is inserted, **Then** it is rejected by the unique constraint (one provider payment per source transaction) (`docs/04` §6.6).
7. **Given** any row in `transaction`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `utility_bill_payment`, or `audit_log`, **When** an UPDATE or DELETE is attempted, **Then** it is rejected (`docs/04` §11.1).
8. **Given** a change to `monthly_bill.final_amount_minor`, **When** the change is applied, **Then** a corresponding `bill_adjustment` row is required to exist (`docs/04` §6.5, §8.7; constitution Database & Schema).
9. **Given** the two ledgers, **When** any attempt is made to record tenancy matching state on a `utility_bill_payment` or to create a `payment_allocation` for a `utility_bill_payment` transaction, **Then** the schema provides no such columns/paths, enforcing ledger separation (`docs/04` §6.5, §6.6, §8.3; ADR-017).
10. **Given** an org-wide `billing_config` (`property_id` null) for an organization, **When** a second org-wide `billing_config` for the same organization is inserted, **Then** it is rejected by the partial unique index `UNIQUE (organization_id) WHERE property_id IS NULL` (`docs/04` §6.4, §8 item 10, §13 item 4).

---

### User Story 5 - Settings and Visibility (Priority: P5)

The configurable visibility policy is established: `portal_setting`, which scopes settings to an organization or property and resolves per `docs/04` §6.8 (property overrides organization; otherwise the application default). This is not needed to record money but is required for the tenant visibility boundary (ADR-008).

**Why this priority**: Cross-cutting configuration; it depends only on `organization`/`property` and is independent of the financial slices.

**Independent Test**: Apply the schema and verify a scoped `portal_setting` persists, that `(scope_type, scope_id, setting_key)` is unique, and that `scope_type` is restricted to `organization`/`property`.

**Acceptance Scenarios**:

1. **Given** a setting for a scope and key, **When** a second setting with the same `(scope_type, scope_id, setting_key)` is inserted, **Then** it is rejected by the unique constraint (`docs/04` §6.8).
2. **Given** a `portal_setting`, **When** a `scope_type` outside `organization`/`property` is inserted, **Then** it is rejected by the CHECK constraint (`docs/04` §6.8).

---

### User Story 6 - Audit and Security Tables (Priority: P6)

The append-only audit trail and the operational security tables are established: `audit_log`, plus `admin_session`, `admin_login_attempt`, and `tenant_login_attempt` (database-backed rate limiting and session storage; ADR-009, ADR-012). Login-attempt tables are operational, prunable data — not financial history.

**Why this priority**: Required for a compliant, auditable, rate-limited product, but it depends on `organization` and `admin_user` and does not block the financial slices.

**Independent Test**: Apply the schema and verify `audit_log` is append-only with no `updated_at` and no commission data path, and that the session/login-attempt tables exist with the scoping, UTC `attempted_at`, and nullable foreign keys defined in `docs/04` §6.1. This story is delivered after the ledgers.

**Acceptance Scenarios**:

1. **Given** an `audit_log` entry, **When** it is written, **Then** it records `actor_type`, `action`, the optional entity reference, JSON metadata, and `created_at`, with no `updated_at`, and an UPDATE/DELETE is rejected (`docs/04` §6.9, §11.1).
2. **Given** a `tenant_login_attempt` for an unknown room, **When** it is recorded, **Then** `tenancy_id` is null while `organization_id`, `source_ip`, UTC `attempted_at`, and `succeeded` are stored (`docs/04` §6.1).
3. **Given** an `admin_login_attempt` for an unknown admin, **When** it is recorded, **Then** `admin_user_id` is null while `organization_id`, `source_ip`, UTC `attempted_at`, and `succeeded` are stored (`docs/04` §6.1).
4. **Given** an `admin_session`, **When** it is persisted, **Then** it carries a hashed token, fixed `issued_at`/`expires_at`, optional `revoked_at`, and is scoped to an `admin_user` (`docs/04` §6.1).
5. **Given** the audit log, **When** commission data is involved, **Then** no commission value can appear in `metadata` (`docs/04` §6.9; constitution Principle III).

---

### User Story 7 - Seed Data (Priority: P7)

Idempotent seed data provisions the system's reference and configuration rows per `docs/04` §12: one default organization, one admin user, the global `PAYVICE_AVANTUS` import profile and its channel/category mappings, the global `BEDC` utility provider, the default org-wide `billing_config`, and the default portal settings.

**Why this priority**: Needed to make the schema usable and demonstrable, but only meaningful once the referenced tables exist.

**Independent Test**: Apply the schema, run the seed, then run it again and confirm the same single set of rows exists with no duplicates and no errors.

**Acceptance Scenarios**:

1. **Given** a fresh database, **When** the seed runs, **Then** exactly the rows listed in `docs/04` §12 exist (one organization, one admin, one global import profile with mappings, one global utility provider, one default billing config, default portal settings).
2. **Given** an already-seeded database, **When** the seed runs again, **Then** it produces no duplicates and no errors (idempotent).
3. **Given** the seeded global import profile and utility provider, **When** they are inspected, **Then** their `organization_id` is null (global/system-wide) and the `billing_config` is org-wide (`property_id` null) (`docs/04` §12).

---

### User Story 8 - Baseline Migration (Priority: P8)

The whole schema is delivered as a single reversible baseline Alembic migration so the full 28-table structure, its constraints, and its indexes can be applied to a fresh database and rolled back cleanly, with structurally equivalent results on the production database engine and the local-development engine.

**Why this priority**: Last by dependency — it packages everything above. It has value only once the schema slices exist.

**Independent Test**: Apply the migration to a fresh database, verify all 28 tables, constraints, and indexes exist, roll it back completely, then re-apply, with no errors and no residue on either supported engine.

**Acceptance Scenarios**:

1. **Given** a fresh database, **When** the baseline migration is applied, **Then** it completes with no errors and creates exactly the 28 tables in `docs/04` §6 with their constraints and indexes (`docs/04` §9, §12).
2. **Given** an applied migration, **When** it is downgraded and re-applied, **Then** the cycle completes cleanly with no errors or leftover objects (`docs/04` §12; constitution Database & Schema).
3. **Given** the migration applied on the production engine and on the local-development engine, **When** the resulting structures are compared, **Then** they are functionally equivalent (same tables, columns, constraints, and index behavior), including the partial unique indexes required by `docs/04` §13 item 4.

---

### Edge Cases

- A partial unique index must allow a new import batch once a previously rejected/failed statement is re-imported (the index is restricted to `confirmed`/`completed`) (`docs/04` §6.7).
- A `reversed` advance movement offsets only a `created` movement; restoring advance after an allocation is reversed is recorded as a new `created` movement, so the reconciliation identity in `docs/04` §7.5 stays sound (schema provides the columns/types; logic is out of scope).
- Money is always a non-negative magnitude with direction stored separately; a negative monetary value must not be stored (`docs/04` §3.4, §6.5).
- `tenant_session`/`admin_session` and login-attempt rows are prunable operational data and must not be treated as immutable financial history (`docs/04` §11.2, §11.4, §11.6).
- A `utility_bill_payment` must never enter tenancy matching (`matching_status = not_applicable`) or reduce a tenant balance (`docs/04` §6.5, §6.6, §8.3).

## Requirements *(mandatory)*

### Functional Requirements

Schema coverage. Each requirement below MUST reproduce the columns, types, nullability, defaults, constraints, and indexes exactly as defined in the cited `docs/04` section. No table, column, constraint, or index may be invented, renamed, or dropped.

- **FR-001**: System MUST persist `organization` and `admin_user` exactly per `docs/04` §6.2 and §6.1 (User Story 1).
- **FR-002**: System MUST persist `property`, `room`, `tenancy`, `tenant`, `sender_alias`, `tenant_access_credential`, and `tenant_session` exactly per `docs/04` §6.2, §6.3, and §6.1 (User Story 2).
- **FR-003**: System MUST persist `import_profile`, `import_channel_category_mapping`, `import_batch`, and `staged_import_row` exactly per `docs/04` §6.7 (User Story 3).
- **FR-004**: System MUST persist `billing_config`, `billing_override`, and `standard_amount_change` exactly per `docs/04` §6.4 (including the partial unique index `UNIQUE (organization_id) WHERE property_id IS NULL` that allows one org-wide default row per organization); `transaction`, `monthly_bill`, `payment_allocation`, `advance_movement`, and `bill_adjustment` exactly per `docs/04` §6.5; and `utility_provider` and `utility_bill_payment` exactly per `docs/04` §6.6 (User Story 4).
- **FR-005**: System MUST persist `portal_setting` exactly per `docs/04` §6.8 (User Story 5).
- **FR-006**: System MUST persist `audit_log` exactly per `docs/04` §6.9, and `admin_session`, `admin_login_attempt`, and `tenant_login_attempt` exactly per `docs/04` §6.1 (User Story 6).
- **FR-007**: The complete schema MUST consist of exactly the 28 tables enumerated in `docs/04` §6 — no more, no fewer — with the exact table and column names given there.

Cross-cutting conventions.

- **FR-008**: Every table MUST use a UUID primary key (`docs/04` §3.1).
- **FR-009**: Every monetary amount MUST be stored as an integer minor-unit `BIGINT` value with no floating-point storage, per `docs/04` §3.4 and the constitution Principle I.
- **FR-010**: Every persisted table that stores a monetary amount MUST carry an explicit `currency CHAR(3) NOT NULL` column defaulting to the MVP currency; transient staging structures do not carry currency (`docs/04` §3.5, §6).
- **FR-011**: Every table MUST carry `created_at`; `updated_at` MUST be present only on the mutable tables listed in `docs/04` §11.2. Instants MUST be stored in UTC (`docs/04` §3.2; ADR-028).
- **FR-012**: System MUST enforce the persisted value domains in `docs/04` §4 for `tenancy_status`, `record_category`, `direction`, `matching_status`, `allocation_type`, `advance_movement_type`, `import_batch_status`, and `totals_status`, and the inline value sets and CHECK constraints defined in `docs/04` §6 for columns whose allowed values are listed there (e.g. `staged_import_row.row_category`, `import_channel_category_mapping.category`, `portal_setting.scope_type`). `record_category` is a `docs/04` §4 enumeration, not a §6 inline set.
- **FR-013**: Key financial and structural tables MUST carry `organization_id`, and the schema MUST support org-scoped queries as required by `docs/04` §2.5 and §8.9 (constitution Database & Schema).

Integrity and invariants.

- **FR-014**: System MUST enforce strict two-ledger separation structurally: `utility_bill_payment` MUST have no tenancy-matching state and MUST tie one-to-one to its source transaction via a unique `transaction_id`; tenant payments and utility bill payments MUST NOT be structurally cross-settleable (`docs/04` §6.5, §6.6, §8.3; ADR-017).
- **FR-015**: System MUST make it impossible to persist commission data: the `transaction.record_category` and `staged_import_row.row_category` CHECK constraints MUST admit only `tenant_payment`/`utility_bill_payment`, and no table, column, constraint, or index may accept a commission-mapped channel (`docs/04` §6.5, §6.7, §8.4; constitution Principle III).
- **FR-016**: System MUST make all financial-history tables append-only — `transaction`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `utility_bill_payment`, and `audit_log` — rejecting in-place UPDATE and DELETE once a row is written (`docs/04` §11.1; constitution Principle I).
- **FR-017**: System MUST store derived state only by computation and MUST NOT store independently mutable copies of bill status, bill remaining, tenancy outstanding, advance balance, net position, or utility spend; the authoritative records required by the computations in `docs/04` §7 MUST exist (`docs/04` §7; constitution Database & Schema).
- **FR-018**: System MUST provide the duplicate-detection keys defined in `docs/04` §10: a unique `duplicate_key` on `transaction` only (`docs/04` §6.5, §10.1); `staged_import_row.duplicate_key` MUST NOT be unique (`docs/04` §6.7) so rows with `parse_status = 'duplicate'` remain stageable; and a `statement_fingerprint` on `import_batch` with a partial unique index restricted to `confirmed`/`completed` status (`docs/04` §6.7, §10.2).
- **FR-019**: System MUST enforce the single-column and composite unique/foreign-key constraints defined across `docs/04` §6, including `admin_user.email`, `tenant_access_credential.tenancy_id`, `UNIQUE (tenancy_id, normalized_name)` on `sender_alias`, `UNIQUE (tenancy_id, billing_month)` on `billing_override`, `UNIQUE (tenancy_id, billing_month)` on `monthly_bill`, `utility_bill_payment.transaction_id`, `utility_provider.code`, `import_profile.code`, `UNIQUE (import_profile_id, channel, COALESCE(direction,'ANY'))`, `UNIQUE (scope_type, scope_id, setting_key)` on `portal_setting`, and all declared foreign keys.
- **FR-020**: System MUST enforce the partial unique indexes required by `docs/04` §13 item 4 — `UNIQUE (room_id) WHERE status = 'active'` on `tenancy`, `UNIQUE (statement_fingerprint) WHERE status IN ('confirmed','completed')` on `import_batch`, and `UNIQUE (organization_id) WHERE property_id IS NULL` on `billing_config` — on both the production database engine (PostgreSQL, `postgresql_where`) and the local-development engine (SQLite, `sqlite_where`).
- **FR-021**: System MUST create the recommended indexes in `docs/04` §9 (beyond primary keys and unique constraints).
- **FR-022**: System MUST enforce that a change to `monthly_bill.final_amount_minor` has a corresponding `bill_adjustment` row; the schema MUST provide the columns, foreign keys, and tests that make this checkable, with enforcement assigned to the billing-engine feature (`docs/04` §6.5, §8.7; constitution Database & Schema). Logic-dependent invariants (allocation cap and advance reconciliation, `docs/04` §7.5, §8.1–8.2) MUST be enforceable from the schema's columns and are verified against those records.

Packaging and scope.

- **FR-023**: System MUST deliver the full schema as a single reversible baseline Alembic migration, with structurally equivalent results on the production and local-development engines; every schema change thereafter ships as a migration (`docs/04` §12; `docs/03` §6.6; constitution Database & Schema).
- **FR-024**: System MUST provide idempotent seed data for exactly the MVP rows in `docs/04` §12 (one organization, one admin user, the global `PAYVICE_AVANTUS` profile and mappings, the global `BEDC` provider, one default `billing_config`, default portal settings).
- **FR-025**: The feature scope MUST be limited to the schema and seed data. System MUST NOT deliver any API, UI, authentication logic, ingestion/parsing logic, billing allocation logic, or reporting/read-model logic (`docs/04` §1, §12).
- **FR-026**: The `organization` model MUST validate `timezone` as a valid IANA time-zone name at the model layer and default it to `Africa/Lagos`; the database stores the given string (`docs/04` §6.2). This adds model-layer validation only — no API or authentication logic (User Story 1).

### Key Entities *(include if feature involves data)*

- **organization / admin_user**: Isolation root and the single MVP administrator (identity boundary) — `docs/04` §6.2, §6.1.
- **property / room**: Physical hierarchy; a room persists across tenancies — `docs/04` §6.2.
- **tenancy / tenant / sender_alias / tenant_access_credential / tenant_session**: Occupancy, privacy boundary, match namespace, and tenancy-scoped access — `docs/04` §6.3, §6.1.
- **import_profile / import_channel_category_mapping / import_batch / staged_import_row**: Configuration-driven staging; trust boundary for commissions — `docs/04` §6.7.
- **billing_config / billing_override / standard_amount_change**: Standard amount, per-tenancy/month bill-or-skip, append-only rate-change history — `docs/04` §6.4.
- **transaction / monthly_bill / payment_allocation / advance_movement / bill_adjustment**: Tenant payment ledger and billing state (append-only financial history) — `docs/04` §6.5.
- **utility_provider / utility_bill_payment**: Global provider registry and outgoing spend records (separate ledger) — `docs/04` §6.6.
- **portal_setting**: Scoped visibility and default-view policy — `docs/04` §6.8.
- **audit_log / admin_session / admin_login_attempt / tenant_login_attempt**: Append-only audit and operational session/rate-limit data — `docs/04` §6.9, §6.1.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A freshly migrated database contains exactly 28 tables, matching the set in `docs/04` §6 by name (0 missing, 0 extra).
- **SC-002**: Every constraint defined in `docs/04` §6, §8, §9, §10 is enforced: inserting or updating data that violates a unique, CHECK, foreign-key, or not-null rule is rejected. This explicitly includes the partial unique indexes in `docs/04` §13 item 4, verified on both SQLite and PostgreSQL.
- **SC-003**: 100% of the append-only tables listed in `docs/04` §11.1 reject UPDATE and DELETE on a written row (7 of 7) via database-level rejection on both SQLite and PostgreSQL (native triggers, `docs/04` §11.1).
- **SC-004**: 100% of monetary columns are integer minor units stored with an explicit `currency`; a stored value round-trips exactly with no floating-point loss (verified across all money-bearing tables).
- **SC-005**: 100% of timestamp columns store UTC instants; `updated_at` appears only on the mutable tables in `docs/04` §11.2 and on no append-only table.
- **SC-006**: 0 commission rows can be persisted, staged, or logged: every commission-mapped channel is rejected by the schema's CHECK constraints.
- **SC-007**: 0 cross-settlement paths exist between the two ledgers: no structure allows a utility bill payment to carry tenancy matching state or produce a payment allocation.
- **SC-008**: The baseline migration completes a clean apply-then-rollback-then-reapply cycle with no errors or leftover objects (`docs/04` §12).
- **SC-009**: Seeding is idempotent: running the seed twice yields exactly one set of the `docs/04` §12 reference and configuration rows.
- **SC-010**: The schema's structure and constraint behavior are functionally equivalent on the production and local-development engines (same tables, columns, constraints, and index enforcement), so locally validated invariants reproduce in production.

## Assumptions

- `docs/04-database.md` is the source of truth; this feature implements it fully. `docs/03`, `docs/09`, and the constitution constrain how, but the table/column contract lives only in `docs/04`.
- The table count is 28, confirmed by enumerating `docs/04` §6.1–§6.9 (6 + 3 + 3 + 3 + 5 + 2 + 4 + 1 + 1).
- User-story grouping is a presentation choice, not a schema change: `tenant_session` is placed with the tenancy slice (User Story 2) because it is bound to `tenant_access_credential`, while `admin_session`, `admin_login_attempt`, `tenant_login_attempt`, and `audit_log` form the audit/security slice (User Story 6). Every table appears in exactly one slice, and all 28 are covered.
- The MVP currency is NGN (ISO 4217); monetary examples use ₦ (`docs/04` §3.5).
- Production is PostgreSQL and local development is SQLite; idempotent identifiers, integer money, immutability, and ledger separation follow the ratified constitution and locked ADRs (ADR-001, ADR-017, ADR-019, ADR-021, ADR-025, ADR-028).
- Timestamps are stored in UTC. Calendar-month boundaries (`billing_month`, "current month", utility-spend grouping) are computed in application code from the organization's `timezone`, not by the database engine (`docs/04` §6.2; ADR-028).
- Enumerations are TEXT columns with CHECK constraints on both engines (`docs/04` §4).
- The schema is delivered as one coherent baseline migration chain; per-module splitting is unnecessary because nothing is yet deployed that needs independent versioning.
- SQLAlchemy and Alembic are already locked by `docs/03` §6.6 and the constitution; references to migration tooling reflect a decided constraint, not new implementation detail.
- Locally, SQLite is the only validated engine (no local PostgreSQL). PostgreSQL-native DDL (immutable-table guards and `postgresql_where` partial unique indexes) is authored now and validated in CI/deploy, per SC-003 and SC-010.

## Open Questions

Questions 1 and 2 are resolved and retained only as pointers to their source of truth; question 3 remains open. None blocks the schema-coverage requirements above.

1. **Enumeration representation**: Resolved — see `docs/04` §4 (enumerations are TEXT columns with CHECK constraints on both SQLite and PostgreSQL).
2. **Inline value sets**: Resolved — see `docs/04` §6 (the four inline value sets are constrained by CHECK).
3. **Remaining `docs/04` §13 open questions** (items 1, 2, 5, 6): read model vs. plain queries for reports, `staged_import_row` retention window, `sender_alias.normalized_name` enforcement location, and advance-reconciliation check cadence are operational/reporting concerns. The tables carry the columns needed to support them; the decisions are deferred.
