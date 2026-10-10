# Tasks: Full MVP Database Schema

**Input**: Design documents from `/specs/001-database-schema/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The feature is the financial schema; the constitution requires test-first for financial logic (Principle V), so test tasks ARE included and MUST be written before implementation within each story.

**Locked execution decisions**:
- **Scope (first pass)**: MVP-first — only **User Story 1** (Structural & Identity Foundation) is implemented in the first pass (Setup → Foundational → US1 → stop at checkpoint). Story phases US2–US7 are planned for subsequent passes.
- **Database (first pass)**: **SQLite-only** for local development and validation (no local PostgreSQL on the dev machine). PostgreSQL-native DDL (immutable triggers, `postgresql_where` partial unique indexes) is authored in the code now but **validated only in CI/deploy**, not locally. Any Postgres-dependent validation (e.g. SC-007 equivalence) is deferred to CI.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app (per plan.md)**: `backend/src/`, `tests/`

---


## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project structure per implementation plan: `backend/src/models/`, `backend/src/migrations/versions/`, `backend/src/migrations/alembic.ini`, `tests/`
- [x] T002 [P] Create `backend/pyproject.toml` with dependency pins: SQLAlchemy 2.x (2.0-style), Alembic, psycopg (PostgreSQL), SQLite stdlib (dev), pytest
- [x] T003 [P] Configure pytest skeleton and engine fixtures in `tests/conftest.py` (SQLite default per-test DB; `DATABASE_URL` override for PostgreSQL)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create shared base mixins and money/currency helpers in `backend/src/models/base.py` — mixins `IdCreatedAt` (UUID id, created_at), `OrgScoped` (organization_id FK), `UpdatedAt` (updated_at only on mutable tables); `money()` helper (column suffix `_minor`, type `BIGINT`; default `CHECK (>= 0)`, with a `positive=True` variant emitting `CHECK (> 0)` used ONLY where docs/04 specify `> 0` — e.g. `transaction.amount_minor`), `currency()` helper (`CHAR(3) NOT NULL`, default `NGN`)
- [ ] T033 [P] Money/currency tests in `tests/test_money.py` for the `money()`/`currency()` helpers from `backend/src/models/base.py` (T004): integer minor-unit magnitude, per-table `CHECK (>= 0)` vs `CHECK (> 0)` contract (contracts/schema.md §3.4), `CHAR(3)` currency default `NGN`, no floating-point storage (Principle I). Write FIRST and confirm they fail before/while T004 lands.
- [x] T005 [P] Create all `enum.StrEnum` definitions in `backend/src/enums.py` for docs/04 §4: `tenancy_status` (`draft active closed`), `record_category` (`tenant_payment utility_bill_payment`), `direction` (`credit debit`), `matching_status` (`unmatched ambiguous matched manually_matched not_applicable`), `allocation_type` (`automatic manual correction reversal`), `advance_movement_type` (`created applied reversed`), `import_batch_status` (`parsing staged duplicate_statement totals_mismatch confirmed rejected completed failed`), `totals_status` (`valid mismatch missing`)
- [x] T006 [P] Create `backend/src/db.py` engine/session/config reading `DATABASE_URL` — PostgreSQL for production, SQLite for local development (constitution Database & Schema)
- [x] T007 [P] Initialize Alembic scaffolding: `backend/src/migrations/alembic.ini`, `backend/src/migrations/env.py`, empty `backend/src/migrations/versions/`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Structural & Identity Foundation (Priority: P1) 🎯 MVP

**Goal**: Establish org/property/room/tenancy/tenant/sender_alias and identity/auth tables (admin, access credential, session) as the prerequisite to all financial records.

**Independent Test**: Apply the schema and verify org-hierarchy + identity tables exist with UUID PKs and org scoping; one-active-tenancy-per-room holds; sender-alias normalization unique; credential rotation invalidates old sessions.

### Tests for User Story 1 ⚠️ (write FIRST, ensure they FAIL before implementation)

- [x] T008 [P] [US1] Uniqueness/constraint tests in `tests/test_uniqueness.py` for: active tenancy per room (`UNIQUE (room_id) WHERE status='active'`), sender_alias (`UNIQUE (tenancy_id, normalized_name)`), UUID PK + org scoping presence on org-hierarchy tables
- [x] T009 [P] [US1] Identity validity tests in `tests/test_identity.py` for credential rotation (version increment revokes prior sessions) and tenant_session validity rule (revoked_at IS NULL AND expires_at > now() AND credential_version = credential.credential_version AND credential.is_active = true)
- [ ] T009a [P] [US1] Timezone and login-attempt delta tests in `tests/test_schema_deltas.py` against a fresh in-memory SQLite DB: `organization.timezone` defaults to `Africa/Lagos` and an invalid IANA name is rejected in application code; a `tenant_login_attempt` persists with and without a tenancy; two tenancies can hold credentials with the same hash (no global uniqueness on `access_code_hash`); `tenant_session.expires_at` stays fixed after the session is used
- [ ] T009b [P] [US1] Admin session validity tests in `tests/test_admin_identity.py` for admin_session validity rule (revoked_at IS NULL AND expires_at > now() AND admin_user.is_active = true) and revocation on logout, password change or reset, and admin deactivation
- [ ] T009c [P] [US1] Admin login-attempt tests in `tests/test_admin_identity.py`: an `admin_login_attempt` persists with and without a known admin (nullable `admin_user_id`), with organization scoping, client IP, UTC `attempted_at`, and the success flag

### Implementation for User Story 1

- [x] T010 [P] [US1] Create organization, property, room models in `backend/src/models/org.py` (org scoping: property.organization_id FK NOT NULL; room reachable via room → property → organization; organization.timezone TEXT NOT NULL DEFAULT 'Africa/Lagos' with IANA validation in application code)
- [x] T011 [P] [US1] Create tenancy, tenant, sender_alias models in `backend/src/models/tenancy.py` (tenancy: status default draft, denormalized organization_id, partial unique active-tenancy; sender_alias: normalized_name unique per tenancy)
- [x] T012 [P] [US1] Create admin_user, tenant_access_credential, tenant_session models in `backend/src/models/identity.py` (email UNIQUE; password_hash never plaintext; credential versioned and NOT unique across tenancies; session write-once with semantic revoked_at and fixed expires_at)
- [ ] T012a [P] [US1] Add tenant_login_attempt model in `backend/src/models/identity.py` (UUID PK, organization_id FK NOT NULL, tenancy_id FK nullable, source_ip TEXT, attempted_at timestamptz UTC, succeeded BOOLEAN NOT NULL, created_at; indexes (tenancy_id, attempted_at) and (source_ip, attempted_at))
- [ ] T012b [P] [US1] Create admin_session model in `backend/src/models/identity.py` (admin_user_id FK NOT NULL to admin_user; token_hash never plaintext; write-once with semantic revoked_at and fixed expires_at; valid while admin_user.is_active)
- [ ] T012c [P] [US1] Add admin_login_attempt model in `backend/src/models/identity.py` (UUID PK, organization_id FK NOT NULL, admin_user_id FK nullable, source_ip TEXT, attempted_at timestamptz UTC, succeeded BOOLEAN NOT NULL, created_at; indexes (admin_user_id, attempted_at) and (source_ip, attempted_at))

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Billing Configuration (Priority: P1)

**Goal**: Persist the org-wide standard amount, per-tenancy/month bill-or-skip overrides, and append-only rate-change history before any bill is generated.

**Independent Test**: Verify billing_config (org-wide default, money+currency), billing_override per-tenancy/month uniqueness, and standard_amount_change append-only with previous/new amounts.

### Tests for User Story 2 ⚠️

- [ ] T013 [P] [US2] Constraint tests in `tests/test_billing_config.py` for billing_override `UNIQUE (tenancy_id, billing_month)`, standard_amount_change append-only, billing_config money `CHECK (>= 0)` + currency default

### Implementation for User Story 2

- [ ] T014 [US2] Create billing_config, billing_override, standard_amount_change models in `backend/src/models/billing_config.py` (billing_config: property_id nullable = org-wide; standard_amount_minor `CHECK (>= 0)` + currency; standard_amount_change append-only with previous/new amounts, admin_id, effective_at)

**Checkpoint**: User Story 2 independently functional

---



## Phase 2: Convergence

**Purpose**: Close the gap between what a feature's specification, plan, and tasks call for and what the codebase currently implements.

**Analysis Summary**:
- **Requirements checked**: 8 (FR-001..FR-015)
- **Plan decisions checked**: 10 (architecture, stack, phases, technical constraints)
- **Constitution principles checked**: 6 (I, II, III, IV, V, Database & Schema)
- **Findings by gap type**: missing: 8, partial: 0, contradicts: 0, unrequested: 0
- **Findings by severity**: CRITICAL: 3, HIGH: 5, MEDIUM: 0, LOW: 0

**Key Findings (CRITICAL)**:

1. **F1** - missing (FR-003, Constitution I) - No money() currency() helpers in backend/src/models/base.py; T004 not created
2. **F2** - missing (FR-002, FR-004) - No org scoping mixin or UUID organization_id in base model; shared foundation missing
3. **F3** - missing (FR-005, FR-012) - No enum.StrEnum definitions; T005 not created

**Key Findings (HIGH)**:

4. **F4** - missing (FR-001, FR-004, FR-012, constitution Database & Schema) - No db.py with engine/session config; T006 not created
5. **F5** - missing (FR-014, FR-015, SC-005, SC-006, SC-007) - No Alembic scaffolding; T007 not created
6. **F6** - missing (US1, FR-001, FR-002, FR-004) - No org/property/room/tenancy/tenant/sender_alias models; T010 not created
7. **F7** - missing (US1, FR-001, FR-002, FR-004) - No tenancy, tenant, sender_alias models; T011 not created
8. **F8** - missing (US1, FR-001, FR-002, FR-004) - No admin_user, tenant_access_credential, tenant_session models; T012 not created

**Recommended Next Steps**:

- **Immediate Priority**: Complete Phase 2 Foundational (T004-T007)
  - Implement shared base mixins and money/currency helpers
  - Create enum.StrEnum definitions
  - Set up database engine and Alembic scaffolding

- **Parallel after Foundational**: Begin User Story 1 (T008-T012)
  - Write uniqueness/constraint tests
  - Write identity validity tests
  - Create organization/property/room models
  - Create tenancy/tenant/sender_alias models
  - Create admin_user/tenant_access_credential/tenant_session models

**Status**: Tasks appended - Phase 2 Convergence ready for implementation.

## Phase 5: User Story 3 - Tenant Payment Ledger & Billing (Priority: P1, highest-risk)

**Goal**: The core financial domain: tenant-payment transactions, monthly bills, payment allocations, advance movements, bill adjustments — money as integer minor units, append-only history, derived advance balance reconciled against a movement ledger, commissions impossible.

**Independent Test**: Persist a matched tenant payment, allocate to a bill, and verify integer-minor money + currency, advance reconciliation identity (§7.5) holds, allocation cap not exceeded, and UPDATE/DELETE on any financial table rejected.

### Tests for User Story 3 ⚠️ (write FIRST, ensure they FAIL before implementation)

- [ ] T015 [P] [US3] Allocation cap test (I-1) in `tests/test_invariants.py`: `SUM(amount_minor) per transaction_id <= transaction.amount_minor` (signed as docs/04 §7.1)
- [ ] T016 [P] [US3] Advance reconciliation identity test (I-2, docs/04 §7.5) in `tests/test_invariants.py`: derived unallocated == logged_advance, covering overpayment, partial application, applied-then-reversed, multi-chunk
- [ ] T017 [P] [US3] Immutability tests in `tests/test_immutable.py`: transaction, payment_allocation, advance_movement, bill_adjustment reject UPDATE/DELETE (SC-002)

### Implementation for User Story 3

- [ ] T018 [P] [US3] Create transaction model in `backend/src/models/ledger.py` (constraint verbatim: `CHECK (record_category IN ('tenant_payment', 'utility_bill_payment'))`; amount_minor `CHECK (> 0)`; duplicate_key TEXT NOT NULL UNIQUE; matching_status enum; currency)
- [ ] T019 [P] [US3] Create advance_movement model in `backend/src/models/ledger.py` (append-only, no updated_at; movement_type created/applied/reversed; monthly_bill_id+allocation_id set when applied; reversed only offsets created per docs/04 §7.5)
- [ ] T020 [P] [US3] Create monthly_bill, payment_allocation, bill_adjustment models in `backend/src/models/billing_ledger.py` (monthly_bill `UNIQUE (tenancy_id, billing_month)`; bill status, bill remaining, tenancy outstanding and net position are derived, never stored (FR-009); payment_allocation allocation_type enum + reverses_allocation_id; bill_adjustment adjustment_type rate_change|write_off, previous/new amounts; allocation-cap invariant (I-1) ships via the FKs/columns enabling it and is verified by test T015 — the cap itself is enforced by the billing engine in a later feature (Principle II), since this schema feature has no service layer)

**Checkpoint**: User Story 3 (core financial domain) independently functional and reconciled

---

## Phase 6: User Story 4 - Utility Bill Payment Ledger (Priority: P1)

**Goal**: The strictly separate second ledger: global utility provider registry and outgoing provider payments enabling month-bounded spend.

**Independent Test**: Register a global provider, record a provider payment, verify it ties one-to-one to a source transaction, never has tenancy matching state, and aggregates by provider/calendar month without reconciling tenant balances.

### Tests for User Story 4 ⚠️

- [x] T021 [P] [US4] Two-ledger separation + utility spend tests (I-3) in `tests/test_separation.py`: utility payments never create payment allocations, never carry tenant matching state; spend aggregates by provider_id/spend_month

### Implementation for User Story 4

- [x] T022 [US4] Create utility_provider, utility_bill_payment models in `backend/src/models/utility.py` (utility_provider: global, organization_id nullable = global, code UNIQUE; utility_bill_payment: transaction_id `NOT NULL, UNIQUE` one-to-one, provider_id FK, spend_month DATE for month-bounded spend)

**Checkpoint**: User Stories 1-4 (both ledgers) independently functional

---

## Phase 7: User Story 5 - Transaction Ingestion (Priority: P2)

**Goal**: The staged, admin-confirmed intake path: import profiles, channel/category mappings, import batches, staged rows — duplicates detected, commission rows never staged.

**Independent Test**: Define a global import profile with mappings, stage rows on a batch, verify a valid row commits to a transaction while a commission-mapped channel is never staged and the batch fingerprint uniqueness holds.

### Tests for User Story 5 ⚠️

- [ ] T023 [P] [US5] Commission-never-stored + staging tests (I-4) in `tests/test_ingestion.py`: channel `COMMISSION` cannot reach transaction or staged_import_row; staged row_category restricted to persistable categories

### Implementation for User Story 5

- [ ] T024 [P] [US5] Create import_profile, import_channel_category_mapping models in `backend/src/models/ingestion.py` (import_profile global organization_id nullable; mapping constraints verbatim: `UNIQUE (import_profile_id, channel, COALESCE(direction, 'ANY'))`, `CHECK (category IN ('tenant_payment','utility_bill_payment','ignored','excluded','unrecognized'))`; COMMISSION → excluded; NOTE best name kept as `category` per data-model §6/contracts §2 — this is the channel→route target config, distinct from `record_category` (persisted transaction type, T005) and `row_category` (staged row type, T025), which must stay separate in code)
- [ ] T025 [P] [US5] Create import_batch, staged_import_row models in `backend/src/models/ingestion.py` (import_batch: currency CHAR(3) default NGN, totals_status enum, statement_fingerprint partial unique `WHERE status IN ('confirmed','completed')`, status enum; staged_import_row: `CHECK (row_category IN ('tenant_payment','utility_bill_payment'))`, `duplicate_key` TEXT NOT NULL UNIQUE, parse_status, committed_transaction_id write-once, no updated_at)

**Checkpoint**: User Stories 1-5 independently functional

---

## Phase 8: User Story 6 - Visibility, Settings, and Audit (Priority: P2)

**Goal**: Configurable tenant visibility and append-only auditing: portal_setting and audit_log.

**Independent Test**: Persist a scoped portal setting and write audit rows; verify scope/key uniqueness, audit append-only, and that commission data cannot be recorded.

### Tests for User Story 6 ⚠️

- [ ] T026 [P] [US6] Tests in `tests/test_settings_audit.py` for portal_setting `UNIQUE (scope_type, scope_id, setting_key)` + scope_type CHECK, and audit_log append-only (no updated_at)

### Implementation for User Story 6

- [ ] T027 [P] [US6] Create portal_setting, audit_log models in `backend/src/models/settings.py` (portal_setting: `UNIQUE (scope_type, scope_id, setting_key)`, `CHECK (scope_type IN ('organization','property'))`; audit_log: append-only no updated_at, actor_type enum-like admin/system/tenant_session, metadata JSON)

**Checkpoint**: User Stories 1-6 independently functional

---

## Phase 9: User Story 7 - Migration, Portability, and Seed (Priority: P3)

**Goal**: One reversible migration delivering the whole schema, structural Postgres/SQLite equivalence, and idempotent MVP seed.

**Independent Test**: Apply the migration to a fresh DB, run seed, reverse and re-apply cleanly, and confirm the structure is equivalent on production and local engines.

### Implementation for User Story 7

- [ ] T028 [US7] Create single reversible baseline migration `backend/src/migrations/versions/0001_initial_schema.py` defining ALL tables (all stories) in FK creation order, with Postgres-native partial unique indexes (`postgresql_where=...`) for active-tenancy and statement fingerprint (R-4), and `BEFORE UPDATE`/`BEFORE DELETE` triggers on the 7 immutable tables (R-5: transaction, payment_allocation, advance_movement, bill_adjustment, standard_amount_change, utility_bill_payment, audit_log), reversible up/down. Must include the 0.5.0 schema deltas: `organization.timezone TEXT NOT NULL DEFAULT 'Africa/Lagos'`, the `tenant_login_attempt` table with `(tenancy_id, attempted_at)` and `(source_ip, attempted_at)` indexes, removal of `import_batch.totals_credit_minor`/`totals_debit_minor` in favor of in-memory footer-total comparison plus `source_file_sha256 CHAR(64)`/`source_filename`/`source_page_count`, `import_profile.source_type` restricted to `pdf`, and default portal settings with `allow_other_room_amount_due` = `false`
- [ ] T028a [US7] Extend the baseline migration `backend/src/migrations/versions/0001_initial_schema.py` with the `admin_session` and `admin_login_attempt` tables (and `admin_login_attempt` `(admin_user_id, attempted_at)` / `(source_ip, attempted_at)` indexes), mirroring the tenant counterparts already listed in T028
- [ ] T029 [P] [US7] Implement idempotent seed in `backend/src/seed.py` (upsert: default organization, one admin, global `PAYVICE_AVANTUS` import profile + channel/category mappings, global `BEDC` utility provider, default org-wide `billing_config`, default portal settings) — re-runnable without duplicates/errors, never includes commission data
- [ ] T030 [P] [US7] Schema reversibility + seed-idempotency + engine-equivalence tests in `tests/test_schema.py` and `tests/test_seed.py` (SC-005: upgrade→downgrade→upgrade clean; SC-006: seed twice is no-op; SC-007: Postgres/SQLite structural equivalence)

**Checkpoint**: All user stories independently functional; full schema deliverable complete

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T034 <imperative description> per FR-003 (missing)
   - [ ] T035 <imperative description> per FR-002, FR-004 (missing)
   - [ ] T036 <imperative description> per FR-005, FR-012 (missing)
   - [ ] T037 <imperative description> per FR-001, FR-004, FR-012 (missing)
   - [ ] T038 <imperative description> per plan (FR-014, FR-015, SC-005, SC-006, SC-007) (missing)
   - [ ] T039 <imperative description> per US1 (FR-001, FR-002, FR-004) (missing)
   - [ ] T040 <imperative description> per US1 (FR-001, FR-002, FR-004) (missing)
   - [ ] T041 <imperative description> per US1 (FR-001, FR-002, FR-004) (missing)

**Checkpoint**: Phase 2 Convergence complete — all found gaps addressed.

---

## Implementation Strategy

### MVP First (User Story 1 Only) — THE CURRENT PASS

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently (SQLite)
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently (SQLite) → Deploy/Demo (MVP) — **current pass ends here**
3. Later passes: US2 → US3 → US4 → US5 → US6 → US7, each tested independently on SQLite
4. PostgreSQL-native validation (triggers, partial indexes, SC-007 equivalence) runs in CI/deploy, not locally
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers (future passes; current pass is US1-only):

1. Team completes Setup + Foundational together
2. Once Foundational is done (first pass staffs only US1):
   - Developer A: User Story 1 (current pass)
   - Subsequent passes: Developer B: US2 → US3 (billing chain); Developer C: US4; Developer D: US5 and US6
3. User Story 7 (migration/seed/portability) is a serial integration pass once models exist; its Postgres assertions run in CI/deploy

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Tests for financial invariants MUST fail before implementation (constitution Principle V)
- Immutability of the 7 financial tables validated by tests (SC-002) even though native triggers are Postgres-only (R-5)
- Commit after each task or logical group (only when requested)
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence