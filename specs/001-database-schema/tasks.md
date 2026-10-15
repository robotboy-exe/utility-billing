---

description: "Task list for the Full MVP Database Schema feature"
---

# Tasks: Full MVP Database Schema

**Input**: Design documents from `/specs/001-database-schema/`

**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required for user stories), [research.md](research.md), [data-model.md](data-model.md), [contracts/schema.md](contracts/schema.md), [quickstart.md](quickstart.md)

**Tests**: REQUIRED. This feature is financial schema; the constitution (Principle V) and plan.md "Testing Strategy" require test-first. Every task below names the test file/function that proves it; within each story the test task is written and made to FAIL before the implementation tasks land.

## Execution constraints (from the request)

- **One test file per user story (8 stories), in dependency order** — `tests/test_identity.py` (US1), `tests/test_tenancy.py` (US2), `tests/test_ingestion.py` (US3), `tests/test_ledgers_billing.py` (US4), `tests/test_settings.py` (US5), `tests/test_audit.py` (US6), `tests/test_seed.py` (US7), `tests/test_migration.py` (US8), plus shared `tests/conftest.py`.
- **Both engines for constraint enforcement**: in-memory **SQLite always**, **PostgreSQL when a PG URL is configured** (skip locally if none, run in CI). Constraint/immutability/index tests consume a parametrized `db_engine` fixture. PostgreSQL-native DDL is authored now and exercised where a PG URL exists (SC-003, SC-010).
- **Test run command** (AGENTS.md): `.venv/bin/python -m pytest tests -q`. Run only the current task's tests while working, e.g. `.venv/bin/python -m pytest tests/test_tenancy.py::test_one_active_tenancy_per_room_partial_unique_index -q`.
- **Scope**: tasks cover only what `spec.md` FR-001..FR-026 require. No API, UI, authentication logic, ingestion/parsing logic, billing/allocation logic, or reporting/read-model logic (spec FR-025, plan.md "Scope guard").
- **Every task is unticked `[ ]`.**
- **Do not edit** spec.md, plan.md, research.md, quickstart.md, or `docs/`. Unspecified decisions are listed under **Gaps** at the end, not decided here.
- **Do not commit.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1..US8); setup, foundational, and polish tasks carry no story label
- Every task names the exact test file/function that proves it

## Path Conventions

- **Backend data layer (plan.md "Project Structure")**: `backend/src/models/`, `backend/src/enums.py`, `backend/src/db.py`, `backend/src/seed.py`, `backend/src/migrations/`
- **Tests**: repository-root `tests/`, one file per user story plus `conftest.py`

## Test-file → story map

| Test file | Story | Priority | Requirements covered |
|---|---|---|---|
| `tests/conftest.py` | shared | — | both-engine fixture for FR-020/SC-002/SC-010 |
| `tests/test_identity.py` | US1 | P1 | FR-001, FR-008, FR-011, FR-026 |
| `tests/test_tenancy.py` | US2 | P2 | FR-002, FR-008, FR-011, FR-012, FR-019, FR-020 |
| `tests/test_ingestion.py` | US3 | P3 | FR-003, FR-010, FR-012, FR-015, FR-018, FR-019, FR-020 |
| `tests/test_ledgers_billing.py` | US4 | P4 | FR-004, FR-009, FR-010, FR-011, FR-013, FR-014, FR-015, FR-016, FR-017, FR-019, FR-020, FR-021, FR-022 |
| `tests/test_transaction_match.py` | US4 | P4 | FR-012, FR-016, FR-019, FR-020, FR-021, FR-027 |
| `tests/test_settings.py` | US5 | P5 | FR-005, FR-012, FR-019 |
| `tests/test_audit.py` | US6 | P6 | FR-006, FR-011, FR-012, FR-016 |
| `tests/test_seed.py` | US7 | P7 | FR-024 |
| `tests/test_migration.py` | US8 | P8 | FR-007, FR-020, FR-021, FR-023, FR-025 |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and test harness

- [ ] T001 Create the package skeleton: `backend/src/__init__.py`, `backend/src/models/__init__.py`, `backend/src/migrations/__init__.py`, `backend/src/migrations/versions/__init__.py`, `tests/__init__.py`. Proved by: `tests/conftest.py` (T003) importing cleanly and `.venv/bin/python -m pytest tests -q` collecting the 8 story files.
- [ ] T002 [P] Verify/extend `backend/pyproject.toml` so the locked dependency set and pytest config are present: `SQLAlchemy>=2.0,<3.0`, `Alembic`, `psycopg[binary]`, `tzdata`, `pytest`, `pytest-sqlalchemy` (research.md "Libraries"). The **single import root is the repository root**: tests import `backend.src.*` (per the removed US1 tests at `cbe8b93^` and quickstart's `python -m backend.src.seed`), so `[tool.pytest.ini_options]` uses `testpaths=["tests"]`, `python_files=["test_*.py"]`, and puts the repository root on `sys.path` — not an `src`-prefixed root. Per D-1, remove `backend/pyproject.toml`'s `[tool.alembic]` table if it duplicates `backend/src/migrations/alembic.ini`. Proved by: `.venv/bin/python -m pytest tests -q` resolving `backend.src` (the sole import root) imports from `tests/test_identity.py`.
- [ ] T003 [P] Create `tests/conftest.py` providing `sqlite_engine` (fresh in-memory SQLite per test, never the dev DB file — AGENTS.md/R-11), `pg_engine` (creates a PostgreSQL engine only when `TEST_DATABASE_URL` is set to a `postgresql+psycopg://` URL — it never reads `DATABASE_URL` (D-4); otherwise `pytest.skip("no PostgreSQL URL configured")`), a parametrized `db_engine` fixture that yields SQLite always and PostgreSQL only when configured, and a `create_schema` helper that resets state per test with `drop_all` + `Base.metadata.create_all()` + the shared immutable-trigger DDL (D-5). Proved by: every `db_engine`-parametrized test, e.g. `tests/test_identity.py::test_organization_and_admin_user_exist_with_uuid_pk`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 [P] Create `backend/src/enums.py` with the `docs/04` §4 value sets (TEXT + CHECK behavior, R-1): `tenancy_status` (`draft | active | closed`), `record_category` (`tenant_payment | utility_bill_payment`), `direction` (`credit | debit`), `matching_status` (`unmatched | ambiguous | matched | manually_matched | not_applicable`), `allocation_type` (`automatic | manual | correction | reversal`), `advance_movement_type` (`created | applied | reversed`), `import_batch_status` (`parsing | staged | duplicate_statement | totals_mismatch | confirmed | rejected | completed | failed`), `totals_status` (`valid | mismatch | missing`). Proved by: `tests/test_tenancy.py::test_tenancy_status_check_rejects_unknown_value` and `tests/test_ledgers_billing.py::test_transaction_record_category_check_rejects_commission`.
- [ ] T005 [P] Create `backend/src/models/base.py` with shared infrastructure (R-2, R-3, R-5, R-6, R-8): `IdCreatedAt` mixin (UUID PK `default=uuid.uuid4`, `created_at`), optional `OrgScoped` mixin (`organization_id` FK), `UpdatedAt` mixin (applied only to the mutable tables of `docs/04` §11.2), the single shared UTC-aware `TypeDecorator` over `DateTime(timezone=True)` used by every `*_at` column, the `money()` helper (column suffix `_minor`, `BigInteger`, default `CHECK (>= 0)` with a `positive=True` variant emitting `CHECK (> 0)`) and `currency()` helper (`CHAR(3) NOT NULL` default `NGN`), and the immutable-table trigger DDL registration — one function returning the per-engine trigger SQL, run by `create_all` via an `after_create` listener (D-8). Proved by: `tests/test_identity.py::test_identity_tables_created_at_and_updated_at_conventions`, `tests/test_ledgers_billing.py::test_money_columns_are_integer_minor_with_currency`, `tests/test_ledgers_billing.py::test_immutable_financial_tables_reject_update_and_delete`, `tests/test_ledgers_billing.py::test_timestamps_round_trip_as_utc`.
- [ ] T006 [P] Create `backend/src/db.py` with engine/session/config resolution from `DATABASE_URL` (PostgreSQL production/CI, SQLite local) per constitution "Database & Schema". Proved by: `tests/test_migration.py::test_engine_equivalence_partial_indexes_and_triggers`.
- [ ] T007 [P] Create the single Alembic config `backend/src/migrations/alembic.ini` (D-1) and the scaffolding `backend/src/migrations/env.py`, wired so `upgrade`/`downgrade` use `Base.metadata` and the same per-engine trigger-SQL function that `create_all` runs (D-8; R-5, R-10). Proved by: `tests/test_migration.py::test_baseline_upgrade_then_downgrade_then_reapply`.

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Organization and Admin Identity (Priority: P1) 🎯 MVP

**Goal**: Establish the isolation root (`organization`) and the single administrator account (`admin_user`), exactly per `docs/04` §6.2 and §6.1.

**Independent Test**: Apply the schema and verify `organization`/`admin_user` exist with UUID PKs, `admin_user.organization_id` is NOT NULL FK → `organization`, `admin_user.email` is unique, `organization.timezone` defaults to `Africa/Lagos` and is rejected when invalid at the model layer, and created_at/updated_at conventions hold.

**Requirements**: FR-001, FR-008, FR-011, FR-026.

### Tests for User Story 1 (write FIRST, ensure they FAIL) ⚠️

- [ ] T008 [P] [US1] Write `tests/test_identity.py` (all functions below; constraint tests parametrize over `db_engine` so they run on in-memory SQLite always and on PostgreSQL when a PG URL is configured): `test_organization_and_admin_user_exist_with_uuid_pk`, `test_admin_user_email_unique_rejects_duplicate` (both engines), `test_admin_user_organization_id_fk_not_null_rejects_orphan` (both engines), `test_organization_timezone_defaults_to_africa_lagos`, `test_organization_timezone_rejects_invalid_iana_at_model_layer` (FR-026), `test_identity_tables_created_at_and_updated_at_conventions` (`organization` and `admin_user` are in `docs/04` §11.2 and carry both timestamps; `created_at` on every row). Proved by: the functions themselves.

### Implementation for User Story 1

- [ ] T009 [US1] Create the `organization` model in `backend/src/models/identity.py` verbatim per `docs/04` §6.2: UUID PK, `name TEXT NOT NULL`, `timezone TEXT NOT NULL DEFAULT 'Africa/Lagos'`, `created_at` NOT NULL, `updated_at`. Add the model-layer IANA validator required by FR-026 (reject an invalid IANA name before persistence; the DB stores the given string). Proved by: `tests/test_identity.py::test_organization_timezone_defaults_to_africa_lagos` and `tests/test_identity.py::test_organization_timezone_rejects_invalid_iana_at_model_layer`.
- [ ] T010 [US1] Create the `admin_user` model in `backend/src/models/identity.py` verbatim per `docs/04` §6.1: UUID PK, `organization_id UUID FK → organization NOT NULL`, `email TEXT NOT NULL UNIQUE`, `password_hash TEXT NOT NULL` (never plaintext), `is_active BOOLEAN NOT NULL DEFAULT true`, `created_at` NOT NULL, `updated_at`. Proved by: `tests/test_identity.py::test_admin_user_email_unique_rejects_duplicate` and `tests/test_identity.py::test_admin_user_organization_id_fk_not_null_rejects_orphan`.
- [ ] T011 [US1] Register the US1 models in `backend/src/models/__init__.py` so `Base.metadata.create_all()` includes `organization` and `admin_user`. Proved by: `tests/test_identity.py::test_organization_and_admin_user_exist_with_uuid_pk`.

**Checkpoint**: US1 fully functional and testable independently

---

## Phase 4: User Story 2 - Property, Room, Tenancy, and Tenant Access (Priority: P2)

**Goal**: Establish the physical/occupancy hierarchy and tenancy-bound access identity: `property`, `room`, `tenancy`, `tenant`, `sender_alias`, `tenant_access_credential`, `tenant_session` per `docs/04` §6.2, §6.3, §6.1.

**Independent Test**: A second active tenancy for the same room is rejected (partial unique index); `(tenancy_id, normalized_name)` is unique on `sender_alias`; `tenant_access_credential.tenancy_id` is unique while `access_code_hash` is NOT globally unique; the session-validity predicate is expressible over stored columns.

**Requirements**: FR-002, FR-008, FR-011, FR-012, FR-019, FR-020.

### Tests for User Story 2 (write FIRST, ensure they FAIL) ⚠️

- [ ] T012 [P] [US2] Write `tests/test_tenancy.py` (`db_engine` for constraint tests): `test_property_room_tenancy_tenant_sender_alias_access_tables_exist` (both engines), `test_one_active_tenancy_per_room_partial_unique_index` (`UNIQUE (room_id) WHERE status='active'`, both engines), `test_closed_tenancy_does_not_block_new_active_tenancy` (both engines), `test_sender_alias_unique_per_tenancy_normalized_name` (`UNIQUE (tenancy_id, normalized_name)`, both engines), `test_tenant_access_credential_tenancy_id_unique` (both engines), `test_access_code_hash_not_globally_unique_across_tenancies` (both engines), `test_tenant_session_validity_predicate_from_columns` (`revoked_at IS NULL AND expires_at > :now AND credential_version = credential.credential_version AND credential.is_active = true`, where `:now` is a bound UTC parameter supplied by the test — not SQL `now()`; `expires_at` fixed across use), `test_tenancy_status_check_rejects_unknown_value` (both engines). Proved by: the functions themselves.

### Implementation for User Story 2

- [ ] T013 [US2] Create `property` and `room` models in `backend/src/models/tenancy.py` verbatim per `docs/04` §6.2: `property` (UUID PK, `organization_id FK NOT NULL`, `name NOT NULL`, `created_at`, `updated_at`), `room` (UUID PK, `property_id FK NOT NULL`, `label NOT NULL`, `is_active BOOLEAN NOT NULL DEFAULT true`, `created_at`, `updated_at`; org reachable `room → property → organization`). Proved by: `tests/test_tenancy.py::test_property_room_tenancy_tenant_sender_alias_access_tables_exist`.
- [ ] T014 [US2] Create `tenancy`, `tenant`, and `sender_alias` models in `backend/src/models/tenancy.py` verbatim per `docs/04` §6.3: `tenancy` (UUID PK, `organization_id FK NOT NULL`, `room_id FK NOT NULL`, `status tenancy_status NOT NULL DEFAULT draft`, `start_date DATE NOT NULL`, `end_date DATE`, `created_at`, `updated_at`) with the partial unique index `UNIQUE (room_id) WHERE status='active'` declared for both `sqlite_where` and `postgresql_where` (R-4); `tenant` (UUID PK, `tenancy_id FK NOT NULL`, `name NOT NULL`, `email`, `phone`, `created_at`, `updated_at`); `sender_alias` (UUID PK, `organization_id FK NOT NULL`, `tenancy_id FK NOT NULL`, `display_name NOT NULL`, `normalized_name NOT NULL`, `created_at`, `updated_at`, `UNIQUE (tenancy_id, normalized_name)`). Proved by: `tests/test_tenancy.py::test_one_active_tenancy_per_room_partial_unique_index`, `tests/test_tenancy.py::test_closed_tenancy_does_not_block_new_active_tenancy`, `tests/test_tenancy.py::test_sender_alias_unique_per_tenancy_normalized_name`.
- [ ] T015 [US2] Create `tenant_access_credential` and `tenant_session` models in `backend/src/models/tenancy.py` verbatim per `docs/04` §6.1: `tenant_access_credential` (UUID PK, `tenancy_id FK NOT NULL UNIQUE`, `access_code_hash NOT NULL`, `credential_version INTEGER NOT NULL DEFAULT 1`, `is_active BOOLEAN NOT NULL DEFAULT true`, `created_at`, `updated_at`, `rotated_at`; NO uniqueness over `access_code_hash` — lookup is by tenancy + code); `tenant_session` (UUID PK, `credential_id FK NOT NULL`, `credential_version INTEGER NOT NULL`, `token_hash NOT NULL`, `device_info`, `issued_at NOT NULL`, `expires_at NOT NULL`, `revoked_at`, `created_at`; write-once, no `updated_at`). Proved by: `tests/test_tenancy.py::test_tenant_access_credential_tenancy_id_unique`, `tests/test_tenancy.py::test_access_code_hash_not_globally_unique_across_tenancies`, `tests/test_tenancy.py::test_tenant_session_validity_predicate_from_columns`.
- [ ] T016 [US2] Register the US2 models in `backend/src/models/__init__.py`. Proved by: `tests/test_tenancy.py::test_property_room_tenancy_tenant_sender_alias_access_tables_exist`.

**Checkpoint**: US1 and US2 independently functional

---

## Phase 5: User Story 3 - Transaction Ingestion Staging (Priority: P3)

**Goal**: Establish the configuration-driven staging structures: `import_profile`, `import_channel_category_mapping`, `import_batch`, `staged_import_row` per `docs/04` §6.7. Parsing/confirmation logic is out of scope.

**Independent Test**: Category CHECK and mapping uniqueness hold; a confirmed/completed statement fingerprint is unique while a rejected/failed batch does not block re-import; only persistable row categories stage; a commission-mapped channel is never staged.

**Requirements**: FR-003, FR-010, FR-012, FR-015, FR-018, FR-019, FR-020.

### Tests for User Story 3 (write FIRST, ensure they FAIL) ⚠️

- [ ] T017 [P] [US3] Write `tests/test_ingestion.py` (`db_engine` for constraint tests): `test_ingestion_tables_exist` (both engines), `test_channel_category_mapping_category_check_rejects_unknown` (`CHECK (category IN ('tenant_payment','utility_bill_payment','ignored','excluded','unrecognized'))`, both engines; FR-015), `test_channel_category_mapping_unique_profile_channel_direction` (`UNIQUE (import_profile_id, channel, COALESCE(direction,'ANY'))`, both engines), `test_import_batch_fingerprint_partial_unique_confirmed_completed` (`UNIQUE (statement_fingerprint) WHERE status IN ('confirmed','completed')`, both engines), `test_rejected_batch_allows_reimport_same_fingerprint` (both engines; edge case), `test_staged_row_category_check_rejects_nonpersistable` (`CHECK (row_category IN ('tenant_payment','utility_bill_payment'))`, both engines), `test_staged_row_parse_status_check` (`CHECK (parse_status IN ('valid','duplicate','invalid','unrecognized'))`, both engines), `test_staged_row_duplicate_key_not_unique` (FR-018; `parse_status='duplicate'` rows remain stageable, both engines), `test_commission_channel_never_staged_or_persisted` (a channel mapped to `excluded`/`COMMISSION` cannot produce a persistable staged row or transaction; SC-006), `test_staged_row_direction_check_rejects_unknown` (`CHECK (direction IN ('credit','debit'))`; both engines), `test_import_batch_status_check_rejects_unknown` (`CHECK (status IN (...))` per `docs/04` §4 `import_batch_status`; both engines), `test_import_batch_totals_status_check_rejects_unknown` (`CHECK (totals_status IN ('valid','mismatch','missing'))`; both engines), `test_import_profile_code_unique` (`import_profile.code` UNIQUE; both engines). Proved by: the functions themselves.

### Implementation for User Story 3

- [ ] T018 [US3] Create `import_profile` and `import_channel_category_mapping` models in `backend/src/models/ingestion.py` verbatim per `docs/04` §6.7: `import_profile` (UUID PK, `organization_id FK` nullable = global, `code TEXT NOT NULL UNIQUE`, `display_name NOT NULL`, `source_type TEXT NOT NULL` = `pdf`, `detection_config JSONB`, `parse_config JSONB`, `file_limits JSONB`, `is_active BOOLEAN NOT NULL DEFAULT true`, `created_at`, `updated_at`); `import_channel_category_mapping` (UUID PK, `import_profile_id FK NOT NULL`, `channel NOT NULL`, `direction direction` nullable, `category TEXT NOT NULL`, `created_at`, `updated_at`, `UNIQUE (import_profile_id, channel, COALESCE(direction,'ANY'))`, `CHECK (category IN ('tenant_payment','utility_bill_payment','ignored','excluded','unrecognized'))`). Proved by: `tests/test_ingestion.py::test_channel_category_mapping_category_check_rejects_unknown` and `tests/test_ingestion.py::test_channel_category_mapping_unique_profile_channel_direction`, `tests/test_ingestion.py::test_import_profile_code_unique`.
- [ ] T019 [US3] Create `import_batch` and `staged_import_row` models in `backend/src/models/ingestion.py` verbatim per `docs/04` §6.7: `import_batch` (UUID PK, `organization_id FK NOT NULL`, `import_profile_id FK NOT NULL`, `status import_batch_status NOT NULL DEFAULT parsing`, statement metadata columns, `source_file_sha256 CHAR(64)`, `source_filename`, `source_page_count`, `currency CHAR(3) NOT NULL`, `totals_status totals_status`, `statement_fingerprint TEXT`, `ignored_summary JSONB`, the staged-row counters and `*_total_minor` totals, `uploaded_at NOT NULL`, `confirmed_at`, `created_at`, `updated_at`; NO persisted footer credit/debit totals; partial unique `UNIQUE (statement_fingerprint) WHERE status IN ('confirmed','completed')` declared for both `sqlite_where` and `postgresql_where`); `staged_import_row` (UUID PK, `import_batch_id FK NOT NULL`, `row_category NOT NULL`, `transaction_date DATE NOT NULL`, `transaction_time TIME`, `channel NOT NULL`, `direction direction NOT NULL`, `description_raw NOT NULL`, `counterparty_name`, `counterparty_reference`, `amount_minor BIGINT NOT NULL CHECK (> 0)` with NO currency, `duplicate_key TEXT NOT NULL` (NOT unique), `parse_status TEXT NOT NULL`, `parse_error`, `created_at`; write-once, no `updated_at`; `CHECK (row_category IN ('tenant_payment','utility_bill_payment'))`, `CHECK (parse_status IN ('valid','duplicate','invalid','unrecognized'))`). Proved by: `tests/test_ingestion.py::test_import_batch_fingerprint_partial_unique_confirmed_completed`, `tests/test_ingestion.py::test_rejected_batch_allows_reimport_same_fingerprint`, `tests/test_ingestion.py::test_staged_row_category_check_rejects_nonpersistable`, `tests/test_ingestion.py::test_staged_row_parse_status_check`, `tests/test_ingestion.py::test_staged_row_duplicate_key_not_unique`, `tests/test_ingestion.py::test_import_batch_status_check_rejects_unknown`, `tests/test_ingestion.py::test_import_batch_totals_status_check_rejects_unknown`, `tests/test_ingestion.py::test_staged_row_direction_check_rejects_unknown`.
- [ ] T020 [US3] Register the US3 models in `backend/src/models/__init__.py`. Proved by: `tests/test_ingestion.py::test_ingestion_tables_exist`.

**Checkpoint**: US1–US3 independently functional

---

## Phase 6: User Story 4 - Ledgers and Billing Tables (Priority: P4)

> Design B (docs/04 0.9.0): T038 to T041 amend T004, T021, T023 and T025: the `transaction` columns `tenancy_id` and `matching_status` and its `(tenancy_id)` index are removed, `matching_status` becomes the derived status (not stored) with `match_type` added to the stored enums, the `transaction_match` table is added, and the immutable-trigger registration covers 8 tables.

**Goal**: The financial core per `docs/04` §6.4–§6.6: billing configuration (`billing_config`, `billing_override`, `standard_amount_change`), the tenant payment ledger (`transaction`, `monthly_bill`, `payment_allocation`, `advance_movement`, `bill_adjustment`), and the strictly separate utility bill ledger (`utility_provider`, `utility_bill_payment`).

**Independent Test**: billing-config uniqueness, one-bill-per-tenancy-per-month, `transaction.duplicate_key` uniqueness and `record_category` CHECK, `utility_bill_payment.transaction_id` uniqueness, money stored as integer minor units + explicit currency, every §11.1 table rejects UPDATE/DELETE, derived state never stored, and no cross-ledger settlement path.

**Requirements**: FR-004, FR-009, FR-010, FR-011, FR-013, FR-014, FR-016, FR-017, FR-019, FR-020, FR-021, FR-022.

### Tests for User Story 4 (write FIRST, ensure they FAIL) ⚠️

- [ ] T021 [P] [US4] Write `tests/test_ledgers_billing.py` (`db_engine` for constraint/enforcement tests, so they run on in-memory SQLite always and on PostgreSQL when a PG URL is configured): `test_billing_config_tables_exist_with_money_and_currency` (both engines), `test_billing_config_one_org_wide_row_per_organization` (`UNIQUE (organization_id) WHERE property_id IS NULL`, both engines; FR-020), `test_billing_override_unique_tenancy_month_and_decision_check` (`UNIQUE (tenancy_id, billing_month)`, `CHECK (decision IN ('bill','skip'))`, both engines), `test_standard_amount_change_append_only` (both engines), `test_monthly_bill_unique_tenancy_month` (`UNIQUE (tenancy_id, billing_month)`, both engines), `test_transaction_record_category_check_rejects_commission` (`CHECK (record_category IN ('tenant_payment','utility_bill_payment'))`, both engines; FR-015), `test_transaction_duplicate_key_unique` (both engines; FR-018), `test_utility_bill_payment_transaction_id_unique` (both engines), `test_utility_provider_code_unique` (both engines), `test_two_ledger_separation_has_no_cross_settle_paths` (no tenancy-matching column on `utility_bill_payment` and no allocation path from a utility transaction; SC-007/FR-014), `test_money_columns_are_integer_minor_with_currency` (every money-bearing persisted table is `BIGINT` `_minor` with `currency CHAR(3) NOT NULL`, no float; staged row carries none; SC-004/FR-009/FR-010), `test_immutable_financial_tables_reject_update_and_delete` (all 7 of `docs/04` §11.1 reject in-place UPDATE and DELETE via triggers on both engines; SC-003/FR-016), `test_only_mutable_tables_carry_updated_at` (`updated_at` present exactly on `docs/04` §11.2 tables; absent on the append-only set; FR-011), `test_no_stored_derived_state_columns` (no stored bill status/remaining/outstanding/advance-balance/net-position/utility-spend columns; FR-017), `test_allocation_cap_enforceable_from_columns` (signed `SUM(payment_allocation.amount_minor) <= transaction.amount_minor` is computable from stored columns; I-1/FR-022), `test_advance_reconciliation_identity_from_records` (`derived_unallocated == logged_advance` per `docs/04` §7.5, covering overpayment/partial/applied-then-reversed/multi-chunk; I-2/FR-022), `test_bill_amount_change_requires_bill_adjustment_columns` (`monthly_bill.final_amount_minor` change has a checkable `bill_adjustment` path; FR-022), `test_recommended_indexes_exist` (`docs/04` §9 indexes beyond PK/unique; FR-021), `test_org_scoping_columns_present` (every table `docs/04` gives `organization_id` carries it with the documented nullability; FR-013), `test_transaction_matching_status_check_rejects_unknown` (`CHECK (matching_status IN (...))`; both engines), `test_payment_allocation_allocation_type_check_rejects_unknown` (`CHECK (allocation_type IN (...))`; both engines), `test_advance_movement_type_check_rejects_unknown` (`CHECK (movement_type IN ('created','applied','reversed'))`; both engines), `test_timestamps_round_trip_as_utc` (UTC instants round-trip without drift; SC-005/FR-011). Proved by: the functions themselves.

### Implementation for User Story 4

- [ ] T022 [US4] Create `billing_config`, `billing_override`, and `standard_amount_change` models in `backend/src/models/ledgers_billing.py` verbatim per `docs/04` §6.4: `billing_config` (UUID PK, `organization_id FK NOT NULL`, `property_id FK` nullable = org-wide, `standard_amount_minor BIGINT NOT NULL CHECK (>= 0)`, `currency CHAR(3) NOT NULL`, `created_at`, `updated_at NOT NULL`, `updated_by_admin_id FK → admin_user`, partial unique `UNIQUE (organization_id) WHERE property_id IS NULL` with both `sqlite_where` and `postgresql_where`); `billing_override` (UUID PK, `organization_id FK NOT NULL`, `tenancy_id FK NOT NULL`, `billing_month DATE NOT NULL`, `decision TEXT NOT NULL`, `reason`, `created_by_admin_id FK → admin_user`, `created_at`, `updated_at`, `UNIQUE (tenancy_id, billing_month)`, `CHECK (decision IN ('bill','skip'))`); `standard_amount_change` (UUID PK, `organization_id FK NOT NULL`, `previous_amount_minor BIGINT NOT NULL CHECK (>= 0)`, `new_amount_minor BIGINT NOT NULL CHECK (>= 0)`, `currency CHAR(3) NOT NULL`, `auto_note TEXT NOT NULL`, `custom_note`, `admin_id FK → admin_user NOT NULL`, `effective_at NOT NULL`, `created_at`; append-only, no `updated_at`). For the mutable tables created here (`billing_config`, `billing_override`), `updated_at` gets a model-side `default` and `onupdate` from the shared UTC-now helper — no server-side defaults (D-6). Proved by: `tests/test_ledgers_billing.py::test_billing_config_one_org_wide_row_per_organization`, `tests/test_ledgers_billing.py::test_billing_override_unique_tenancy_month_and_decision_check`, `tests/test_ledgers_billing.py::test_standard_amount_change_append_only`.
- [ ] T023 [US4] Create `transaction`, `monthly_bill`, `payment_allocation`, `advance_movement`, and `bill_adjustment` models in `backend/src/models/ledgers_billing.py` verbatim per `docs/04` §6.5: `transaction` (UUID PK, `organization_id FK NOT NULL`, `import_batch_id FK` nullable, `record_category NOT NULL`, `source NOT NULL`, `transaction_date DATE NOT NULL`, `transaction_time TIME`, `channel NOT NULL`, `direction NOT NULL`, `description_raw NOT NULL`, `counterparty_name`, `counterparty_name_normalized`, `counterparty_reference`, `amount_minor BIGINT NOT NULL CHECK (> 0)`, `currency CHAR(3) NOT NULL`, `tenancy_id FK` nullable, `matching_status NOT NULL DEFAULT unmatched`, `duplicate_key TEXT NOT NULL UNIQUE`, `created_at`; append-only; `CHECK (record_category IN ('tenant_payment','utility_bill_payment'))`); `monthly_bill` (UUID PK, `organization_id FK NOT NULL`, `tenancy_id FK NOT NULL`, `billing_month DATE NOT NULL`, `standard_amount_minor BIGINT NOT NULL CHECK (>= 0)`, `final_amount_minor BIGINT NOT NULL CHECK (>= 0)`, `currency CHAR(3) NOT NULL`, `is_adjusted BOOLEAN NOT NULL DEFAULT false`, `created_at`, `updated_at`, `UNIQUE (tenancy_id, billing_month)`); `payment_allocation` (UUID PK, `transaction_id FK NOT NULL`, `monthly_bill_id FK NOT NULL`, `amount_minor BIGINT NOT NULL CHECK (> 0)`, `currency CHAR(3) NOT NULL`, `allocation_type NOT NULL DEFAULT automatic`, `reverses_allocation_id FK → payment_allocation`, `created_at`; append-only); `advance_movement` (UUID PK, `organization_id FK NOT NULL`, `tenancy_id FK NOT NULL`, `transaction_id FK NOT NULL`, `movement_type NOT NULL`, `amount_minor BIGINT NOT NULL CHECK (> 0)`, `currency CHAR(3) NOT NULL`, `monthly_bill_id FK`, `allocation_id FK → payment_allocation`, `note`, `occurred_at NOT NULL`, `created_at`; append-only, no `updated_at`); `bill_adjustment` (UUID PK, `monthly_bill_id FK NOT NULL`, `adjustment_type TEXT NOT NULL`, `previous_amount_minor BIGINT NOT NULL CHECK (>= 0)`, `new_amount_minor BIGINT NOT NULL CHECK (>= 0)`, `currency CHAR(3) NOT NULL`, `public_note`, `custom_note`, `internal_reason`, `admin_id FK → admin_user NOT NULL`, `created_at`; append-only; `CHECK (adjustment_type IN ('rate_change','write_off'))`). Also add the `committed_transaction_id UUID FK → transaction` column to the `staged_import_row` model in `backend/src/models/ingestion.py` in this task, because its FK target `transaction` does not exist until US4 (the `staged_import_row` table itself is created in T019). Proved by: `tests/test_ledgers_billing.py::test_monthly_bill_unique_tenancy_month`, `tests/test_ledgers_billing.py::test_transaction_record_category_check_rejects_commission`, `tests/test_ledgers_billing.py::test_transaction_duplicate_key_unique`, `tests/test_ledgers_billing.py::test_allocation_cap_enforceable_from_columns`, `tests/test_ledgers_billing.py::test_advance_reconciliation_identity_from_records`, `tests/test_ledgers_billing.py::test_bill_amount_change_requires_bill_adjustment_columns`, `tests/test_ledgers_billing.py::test_transaction_matching_status_check_rejects_unknown`, `tests/test_ledgers_billing.py::test_payment_allocation_allocation_type_check_rejects_unknown`, `tests/test_ledgers_billing.py::test_advance_movement_type_check_rejects_unknown`.
- [ ] T024 [US4] Create `utility_provider` and `utility_bill_payment` models in `backend/src/models/ledgers_billing.py` verbatim per `docs/04` §6.6: `utility_provider` (UUID PK, `organization_id FK` nullable = global, `code TEXT NOT NULL UNIQUE`, `display_name NOT NULL`, `channel_signature NOT NULL`, `reference_label`, `is_active BOOLEAN NOT NULL DEFAULT true`, `created_at`, `updated_at`); `utility_bill_payment` (UUID PK, `organization_id FK NOT NULL`, `transaction_id FK NOT NULL UNIQUE`, `provider_id FK NOT NULL`, `customer_reference`, `amount_minor BIGINT NOT NULL CHECK (> 0)`, `currency CHAR(3) NOT NULL`, `payment_datetime NOT NULL`, `spend_month DATE NOT NULL`, `import_batch_id FK → import_batch`, `created_at`; append-only; NO tenancy-matching column). Proved by: `tests/test_ledgers_billing.py::test_utility_bill_payment_transaction_id_unique`, `tests/test_ledgers_billing.py::test_utility_provider_code_unique`, `tests/test_ledgers_billing.py::test_two_ledger_separation_has_no_cross_settle_paths`.
- [ ] T025 [US4] Register the US4 models in `backend/src/models/__init__.py` and ensure `metadata.create_all()` emits the shared immutable-trigger DDL for all 7 append-only tables (`transaction`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `utility_bill_payment`, `audit_log` — the last lands in US6) plus both-engine partial unique indexes (R-4, R-5). Proved by: `tests/test_ledgers_billing.py::test_immutable_financial_tables_reject_update_and_delete`, `tests/test_ledgers_billing.py::test_money_columns_are_integer_minor_with_currency`, `tests/test_ledgers_billing.py::test_no_stored_derived_state_columns`, `tests/test_ledgers_billing.py::test_recommended_indexes_exist`, `tests/test_ledgers_billing.py::test_org_scoping_columns_present`.

**Checkpoint**: US1–US4 (both ledgers) independently functional

---

## Phase 7: User Story 5 - Settings and Visibility (Priority: P5)

**Goal**: Establish the scoped visibility policy table `portal_setting` per `docs/04` §6.8.

**Independent Test**: A scoped `portal_setting` persists; `(scope_type, scope_id, setting_key)` is unique; `scope_type` is restricted to `organization`/`property`.

**Requirements**: FR-005, FR-012, FR-019.

### Tests for User Story 5 (write FIRST, ensure they FAIL) ⚠️

- [ ] T026 [P] [US5] Write `tests/test_settings.py` (`db_engine`, both engines): `test_portal_setting_scope_unique` (`UNIQUE (scope_type, scope_id, setting_key)`), `test_portal_setting_scope_type_check` (`CHECK (scope_type IN ('organization','property'))`). Proved by: the functions themselves.

### Implementation for User Story 5

- [ ] T027 [US5] Create the `portal_setting` model in `backend/src/models/settings.py` verbatim per `docs/04` §6.8 (UUID PK, `scope_type TEXT NOT NULL`, `scope_id UUID NOT NULL`, `setting_key TEXT NOT NULL`, `setting_value TEXT NOT NULL`, `created_at`, `updated_at NOT NULL`, `UNIQUE (scope_type, scope_id, setting_key)`, `CHECK (scope_type IN ('organization','property'))`) and register it in `backend/src/models/__init__.py`; `updated_at` gets a model-side `default` and `onupdate` from the shared UTC-now helper — no server-side default (D-6). Proved by: `tests/test_settings.py::test_portal_setting_scope_unique` and `tests/test_settings.py::test_portal_setting_scope_type_check`.

**Checkpoint**: US1–US5 independently functional

---

## Phase 8: User Story 6 - Audit and Security Tables (Priority: P6)

**Goal**: Establish the append-only `audit_log` and the operational tables `admin_session`, `admin_login_attempt`, `tenant_login_attempt` per `docs/04` §6.9 and §6.1.

**Independent Test**: `audit_log` is append-only, has no `updated_at`, and rejects UPDATE/DELETE; session/login-attempt tables exist with the documented scoping, UTC `attempted_at`, and nullable foreign keys.

**Requirements**: FR-006, FR-011, FR-012, FR-016.

### Tests for User Story 6 (write FIRST, ensure they FAIL) ⚠️

- [ ] T028 [P] [US6] Write `tests/test_audit.py` (`db_engine` for enforcement tests): `test_audit_log_append_only_no_updated_at` (records `actor_type`, `action`, optional entity reference, JSON metadata, `created_at`; UPDATE/DELETE rejected on both engines; FR-016), `test_audit_log_actor_type_check` (`CHECK (actor_type IN ('admin','system','tenant_session'))`, both engines), `test_admin_session_validity_predicate_and_scoping` (`revoked_at IS NULL AND expires_at > :now AND admin_user.is_active = true`, where `:now` is a bound UTC parameter supplied by the test — not SQL `now()`; hashed token; fixed `expires_at`), `test_admin_login_attempt_nullable_admin_user_id` (`admin_user_id` null with `organization_id`, `source_ip`, UTC `attempted_at`, `succeeded` stored), `test_tenant_login_attempt_nullable_tenancy_id_and_utc` (`tenancy_id` null while `organization_id`, `source_ip`, UTC `attempted_at`, `succeeded` stored), `test_login_attempt_tables_are_prunable_not_append_only` (UPDATE/DELETE are NOT blocked; `updated_at` absent; `docs/04` §11.2/§11.6). Proved by: the functions themselves.

### Implementation for User Story 6

- [ ] T029 [US6] Create the `audit_log` model in `backend/src/models/audit.py` verbatim per `docs/04` §6.9 (UUID PK, `organization_id FK NOT NULL`, `actor_type TEXT NOT NULL`, `actor_id UUID`, `action TEXT NOT NULL`, `entity_type TEXT`, `entity_id UUID`, `metadata JSONB`, `created_at`; append-only, no `updated_at`; `CHECK (actor_type IN ('admin','system','tenant_session'))`). Proved by: `tests/test_audit.py::test_audit_log_append_only_no_updated_at` and `tests/test_audit.py::test_audit_log_actor_type_check`.
- [ ] T030 [US6] Create `admin_session`, `admin_login_attempt`, and `tenant_login_attempt` models in `backend/src/models/audit.py` verbatim per `docs/04` §6.1: `admin_session` (UUID PK, `admin_user_id FK NOT NULL`, `token_hash NOT NULL`, `device_info`, `issued_at NOT NULL`, `expires_at NOT NULL`, `revoked_at`, `created_at`; write-once, no `updated_at`); `admin_login_attempt` (UUID PK, `organization_id FK NOT NULL`, `admin_user_id FK` nullable, `source_ip`, `attempted_at NOT NULL`, `succeeded BOOLEAN NOT NULL`, `created_at`; indexes `(admin_user_id, attempted_at)` and `(source_ip, attempted_at)`); `tenant_login_attempt` (UUID PK, `organization_id FK NOT NULL`, `tenancy_id FK` nullable, `source_ip`, `attempted_at NOT NULL`, `succeeded BOOLEAN NOT NULL`, `created_at`; indexes `(tenancy_id, attempted_at)` and `(source_ip, attempted_at)`). Proved by: `tests/test_audit.py::test_admin_session_validity_predicate_and_scoping`, `tests/test_audit.py::test_admin_login_attempt_nullable_admin_user_id`, `tests/test_audit.py::test_tenant_login_attempt_nullable_tenancy_id_and_utc`, `tests/test_audit.py::test_login_attempt_tables_are_prunable_not_append_only`.
- [ ] T031 [US6] Register the US6 models in `backend/src/models/__init__.py` (this completes the full 29-table `Base.metadata`) and ensure `audit_log` receives the shared immutable-trigger DDL. Proved by: `tests/test_audit.py::test_audit_log_append_only_no_updated_at`.

**Checkpoint**: US1–US6 independently functional

---

## Phase 9: User Story 7 - Seed Data (Priority: P7)

**Goal**: Idempotent seed data for exactly the MVP rows in `docs/04` §12: one default organization, one admin user, the global `PAYVICE_AVANTUS` import profile and its channel/category mappings, the global `BEDC` utility provider, one default org-wide `billing_config`, and the default portal settings.

**Independent Test**: Run the seed, then run it again; the same single set of rows exists with no duplicates and no errors.

**Requirements**: FR-024.

### Tests for User Story 7 (write FIRST, ensure they FAIL) ⚠️

- [ ] T032 [P] [US7] Write `tests/test_seed.py`: `test_seed_creates_exactly_docs04_reference_rows` (one organization, one admin, one global `PAYVICE_AVANTUS` profile + its mappings, one global `BEDC` provider, one default `billing_config`, the default portal settings), `test_seed_is_idempotent` (run twice: no duplicates, no errors; SC-009), `test_seeded_global_rows_have_null_organization_id` (profile and provider are global; `docs/04` §12), `test_default_billing_config_is_org_wide` (`property_id` null). Proved by: the functions themselves.

### Implementation for User Story 7

- [ ] T033 [US7] Create `backend/src/seed.py` — an idempotent seed (D-2) delivering exactly the `docs/04` §12 rows and never any commission data. Deployment values come from env vars `ORG_NAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH` (already hashed; this feature adds no hashing code, FR-025), and `STANDARD_AMOUNT_MINOR`, and the seed fails loudly if any is missing; tests pass fixed values. Idempotency keys (R-9): `organization` = skip if any organization exists; `admin_user` = `email`; `import_profile`/`utility_provider` = `code`; `import_channel_category_mapping` = `(profile, channel, direction)`; `billing_config` = the org-wide row; `portal_setting` = `(scope_type, scope_id, setting_key)`. Seed the `PAYVICE_AVANTUS` mappings from the `docs/06` §11.1 channel/direction → category table. Proved by: `tests/test_seed.py::test_seed_creates_exactly_docs04_reference_rows`, `tests/test_seed.py::test_seed_is_idempotent`, `tests/test_seed.py::test_seeded_global_rows_have_null_organization_id`, `tests/test_seed.py::test_default_billing_config_is_org_wide`.

**Checkpoint**: US1–US7 independently functional

---

## Phase 10: User Story 8 - Baseline Migration (Priority: P8)

**Goal**: Deliver the whole schema as one reversible baseline Alembic migration creating all 29 tables, constraints, indexes, both-engine partial unique indexes, and triggers, with equivalent results on PostgreSQL and SQLite.

**Independent Test**: Apply the migration to a fresh database, verify all 29 tables/constraints/indexes exist, roll it back completely, re-apply with no errors or residue, on either supported engine.

**Requirements**: FR-007, FR-020, FR-023, FR-025.

### Tests for User Story 8 (write FIRST, ensure they FAIL) ⚠️

- [ ] T034 [P] [US8] Write `tests/test_migration.py`: `test_baseline_upgrade_then_downgrade_then_reapply` (SC-008/FR-023), `test_schema_has_exactly_29_tables` (0 missing, 0 extra vs `docs/04` §6; FR-007/SC-001), `test_engine_equivalence_partial_indexes_and_triggers` (same tables/columns/constraints and native partial-index/trigger enforcement on SQLite always and PostgreSQL when a PG URL is configured; SC-010/FR-020), `test_all_recommended_indexes_created` (`docs/04` §9; FR-021), `test_all_tables_have_uuid_pk_and_created_at` (all 29 tables carry a UUID PK and `created_at`; FR-008/FR-011), `test_scope_guard_no_forbidden_modules` (the package exposes only the schema/seed/migration modules — no API, UI, auth, ingestion/parsing, billing/allocation, or reporting modules; FR-025). Proved by: the functions themselves.

### Implementation for User Story 8

- [ ] T035 [US8] Create `backend/src/migrations/versions/0001_initial_schema.py` — a single reversible baseline creating all 29 tables in FK creation order, all §6 constraints and §9 indexes, the three §13-item-4 partial unique indexes and the `transaction_match (reverses_match_id)` partial unique index, each declared with both `sqlite_where` and `postgresql_where` (R-4), and the 8 §11.1 immutable triggers by calling the same per-engine trigger-SQL function `create_all` uses, explicitly with `op.execute`, with `downgrade` dropping the triggers (D-8; R-5); plus a clean `downgrade`. Proved by: `tests/test_migration.py::test_baseline_upgrade_then_downgrade_then_reapply`, `tests/test_migration.py::test_schema_has_exactly_29_tables`, `tests/test_migration.py::test_engine_equivalence_partial_indexes_and_triggers`, `tests/test_migration.py::test_all_recommended_indexes_created`, `tests/test_migration.py::test_all_tables_have_uuid_pk_and_created_at`.

**Checkpoint**: Full schema deliverable complete; all user stories independently functional

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Full-suite verification across the 8 story files and both engines

- [ ] T036 Run the full suite on in-memory SQLite from the repository root: `.venv/bin/python -m pytest tests -q` (AGENTS.md). Must be green across all 8 story files before the feature is considered done. Proved by: the full-suite run itself.
- [ ] T037 [P] Run the same full suite against PostgreSQL when a PG URL is configured (CI/deploy): `DATABASE_URL=postgresql+psycopg://... .venv/bin/python -m pytest tests -q` (quickstart.md; SC-010). Locally, with no PG URL, the PostgreSQL variants skip (they do not fail). Proved by: the full-suite run against `db_engine`'s PostgreSQL parameter.

---

## Phase 12: Design B amendments (docs/04 0.9.0)

**Goal**: Amend the built US4 schema to Design B (`docs/04` 0.9.0): `transaction` drops `tenancy_id`, `matching_status` and the `(tenancy_id)` index, the stored enum set swaps `matching_status` for `match_type`, and the append-only `transaction_match` table is added, bringing the append-only set to 8 tables.

**Independent Test**: Run `tests/test_transaction_match.py` and the amended `tests/test_ledgers_billing.py`; the `transaction_match` columns, CHECKs, partial unique index, indexes and append-only trigger hold on both engines, and `transaction` carries no tenancy or matching-status columns.

**Requirements**: FR-012, FR-016, FR-019, FR-020, FR-021, FR-027.

### Tests for Design B (write FIRST, ensure they FAIL) ⚠️

- [ ] T038 [P] [US4] Write `tests/test_transaction_match.py` (`db_engine`, both engines): `test_transaction_match_table_exists_with_columns` (columns and nullability per `docs/04` §6.5; no `updated_at`), `test_match_type_check_rejects_unknown`, `test_reversal_requires_reverses_match_id`, `test_non_reversal_rejects_reverses_match_id`, `test_reverses_match_id_unique_partial_index` (a second reversal of the same match is rejected; several NULLs allowed; partial predicate present on both engines), `test_transaction_match_foreign_keys`, `test_transaction_match_indexes_exist`, `test_transaction_match_append_only` (UPDATE and DELETE rejected by the trigger, asserting the trigger's own message, not a foreign-key error), `test_transaction_has_no_tenancy_id_or_matching_status_columns`.
- [ ] T039 [US4] Amend `tests/test_ledgers_billing.py` (the T021 tests): remove assertions and tests for `transaction.tenancy_id`, `transaction.matching_status` (including its default) and the `transaction` `(tenancy_id)` index; make the immutability tests cover the 8 append-only tables.

### Implementation for Design B

- [ ] T040 [US4] Amend the `transaction` model in `backend/src/models/ledgers_billing.py` (T023): delete the `tenancy_id` and `matching_status` columns and the `(tenancy_id)` index; change nothing else.
- [ ] T041 [US4] Add the `transaction_match` model in `backend/src/models/ledgers_billing.py` verbatim per `docs/04` §6.5 (columns, the two CHECKs, the partial unique index on `reverses_match_id` with both `sqlite_where` and `postgresql_where`, indexes `(transaction_id, created_at)` and `(tenancy_id)`); in `backend/src/enums.py` (T004) remove `matching_status` and add `match_type` (`automatic | manual | reversal`, TEXT + CHECK); register `transaction_match` with the shared immutable-trigger DDL (T025) so it covers all 8 append-only tables; export it from `backend/src/models/__init__.py`.

**Checkpoint**: US4 amended to Design B; both ledgers and the match history are independently testable

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Stories (Phases 3–10)**: All depend on Foundational. They are in dependency order (US1 → US2 → US3 → US4 → US5 → US6 → US7 → US8); each story depends on the tables it references already existing.
  - US4 depends on US1 (`organization`, `admin_user`), US2 (`tenancy`), US3 (`import_batch`).
  - US6 depends on US1 (`organization`, `admin_user`).
  - US7 depends on US1–US6 (it seeds rows across them).
  - US8 packages US1–US7.
- **Polish (Phase 11)**: Depends on all desired stories being complete.
- **Design B amendments (Phase 12)**: Depend on T023 to T025; T038 and T039 come before T040 and T041; the baseline migration (T035) must include `transaction_match`.

### Within Each User Story

- The test task is written and made to FAIL before the implementation tasks land (constitution Principle V).
- Implementation tasks that edit the same module file are sequential (not `[P]`); models precede registration; registration precedes the migration.
- Story complete and independently testable before moving to the next priority.

### Parallel Opportunities

- Phase 1: T002 and T003 are different files (`[P]`).
- Phase 2: T004, T005, T006, T007 are different files (`[P]`).
- Phases 3–10: each story's **single test file** task is a different file and can run in parallel with other stories' test files (`[P]`). Model implementation tasks within a story share one module file and therefore run sequentially.

---

## Parallel Example: Test files across stories

```bash
# Once Foundational (Phase 2) is complete, the 8 story test files are independent:
Task: "Write tests/test_identity.py"       # US1
Task: "Write tests/test_tenancy.py"        # US2
Task: "Write tests/test_ingestion.py"      # US3
Task: "Write tests/test_ledgers_billing.py"# US4
Task: "Write tests/test_settings.py"       # US5
Task: "Write tests/test_audit.py"          # US6
Task: "Write tests/test_seed.py"           # US7
Task: "Write tests/test_migration.py"      # US8
```

Within a story, the module file is single, so model tasks are sequential, e.g. US4:

```bash
Task: "Create billing_config/billing_override/standard_amount_change in ledgers_billing.py"  # T022
Task: "Create transaction/monthly_bill/payment_allocation/advance_movement/bill_adjustment" # T023 (same file, after T022)
Task: "Create utility_provider/utility_bill_payment"                                          # T024 (same file, after T023)
Task: "Register US4 models in models/__init__.py"                                             # T025
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US1
4. **STOP and VALIDATE**: `.venv/bin/python -m pytest tests/test_identity.py -q` (in-memory SQLite; PostgreSQL when configured).

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → test independently → the isolation root and admin exist.
3. US2 → US3 → US4 → US5 → US6, each tested independently.
4. US7 (seed) and US8 (baseline migration) once the models exist.
5. Each story adds value without breaking previous stories.

### Engine strategy

- Constraint/enforcement/immutability tests run on in-memory SQLite on every run and on PostgreSQL when a PG URL is configured; with no PG URL those variants skip locally and run in CI (SC-003, SC-010).
- The PostgreSQL-native DDL (`postgresql_where` partial indexes, trigger function) is authored from the same shared DDL that SQLite uses, so the two paths cannot drift (R-4, R-5).

---

## Notes

- `[P]` = different files, no dependency on an incomplete task. Within a story the module file is single, so model tasks are not `[P]`.
- `[Story]` labels map each task to its user story for traceability.
- Tests for financial invariants MUST fail before implementation (constitution Principle V).
- Never point tests at `utility_billing_dev.db`; use the in-memory SQLite fixture (AGENTS.md).
- Run only the current task's tests while working; run the full suite at a story checkpoint.
- Do not commit (per the request).

---

## Gaps

Resolved — see plan.md Implementation decisions D-1..D-8.
