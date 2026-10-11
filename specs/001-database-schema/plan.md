# Implementation Plan: Full MVP Database Schema

**Branch**: `001-database-schema` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-database-schema/spec.md` and the plan input in this pass.

**Note**: Filled in by `/speckit.plan`; its definition describes the execution workflow.

## Summary

Deliver the complete database layer for the Utility Billing MVP as SQLAlchemy 2.x models plus a single reversible Alembic baseline and an idempotent seed, satisfying every entity, constraint, index, enumeration, derived-state computation, and immutability rule in `docs/04-database.md`. `docs/04` is the **only** definition of tables and columns; this plan and [data-model.md](data-model.md) reference `docs/04` by section and never restate columns. Type/enforcement decisions and their cost of change are in [research.md](research.md); the DB-level contract is in [contracts/schema.md](contracts/schema.md); runnable validation is in [quickstart.md](quickstart.md).

**Scope guard**: this feature is the schema and seed only. It ships **no** API, UI, authentication, ingestion/parsing, billing/allocation, or reporting logic (`docs/04` §1, §12; spec FR-025).

**Delta (against `docs/04` at the current tip)**: enumerations are now `TEXT` + `CHECK` on both engines (`docs/04` §4); the four inline value sets are CHECK-constrained (§6); `docs/04` §13 item 3 is resolved by `09` §14. Carried forward from 04→0.5.0: `organization.timezone` (default `Africa/Lagos`), `tenant_login_attempt`, non-unique access-code hashes, fixed `tenant_session.expires_at`, `import_batch` footer totals not persisted plus `source_file_sha256`/`source_filename`/`source_page_count`, `import_profile.source_type` = `pdf`, and `portal_setting.allow_other_room_amount_due` default `false`.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: SQLAlchemy 2.x (2.0-style declarative), Alembic, psycopg (PostgreSQL), SQLite stdlib (local/tests), pytest, `tzdata`. Nothing else is added (research.md "Libraries").

**Storage**: PostgreSQL (production and CI), SQLite (local development and tests)

**Testing**: pytest; default is a fresh **in-memory SQLite** database per test (never the dev database file, per AGENTS.md); the same suite can run against PostgreSQL in CI. One test file per user story under the repository-root `tests/`.

**Target Platform**: Linux free-tier host (deployment) + local development

**Project Type**: backend data layer (SQLAlchemy models + migrations + seed), the data-access slice of a FastAPI web service (`docs/03` §6.6)

**Performance Goals**: light MVP load (`docs/03` §14.5); correctness prioritized over scale

**Constraints**: free hosting (no workers/schedulers); money as integer minor units + explicit currency (no floats); append-only financial tables; org-scoped queries; PostgreSQL/SQLite parity — **both engines now enforce partial unique indexes and immutable-table triggers natively** (R-4, R-5)

**Scale/Scope**: single org MVP; 28 tables + seed

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I — Financial correctness & immutable history**: Conforms. Money is `BIGINT` minor units + explicit `currency` via shared helpers (R-3); the seven financial tables are append-only and rejected at the database level on both engines by triggers from one shared DDL (R-5); corrections use reversal/correction rows; no mutable stored advance balance (`docs/04` §7.4–7.5). **PASS**
- **Principle II — Billing engine independence**: Conforms. Models express only domain data; no source/billing rules are embedded (spec FR-025). **PASS**
- **Principle III — Ingestion reliability & integrity**: Conforms. Staged/confirmed structures with duplicate keys (`docs/04` §10); commissions never stored (CHECK + category mapping); mapping is configuration data. **PASS**
- **Principle IV — Two-ledger separation**: Conforms. Structural separation with unique `transaction_id` on `utility_bill_payment` and no tenancy-matching state there (`docs/04` §6.5–§6.6, §8.3). **PASS**
- **Principle V — Test-first financial logic**: Conforms. Allocation cap, advance reconciliation, immutability, partial-index, and ingestion edge cases each have a named test in the per-story test files; tests are written before implementation. **PASS**
- **Database & Schema discipline**: Conforms. UUID PKs (R-6); org scoping (R-8); every change ships as a reversible Alembic migration (R-10); derived state computed not stored (`docs/04` §7); immutability classification honored (`docs/04` §11); audited bill changes; PostgreSQL prod / SQLite local. **PASS**

**Gate result**: all gates **PASS**; no unjustified violation, so `Complexity Tracking` is empty.

### Post-design re-check

Re-evaluated after data-model/contracts/quickstart design:
- Money remains integer minor units + currency (R-3); no float path.
- All seven financial tables remain append-only; now enforced by triggers on **both** engines from one DDL source (R-5), so the SQLite tests exercise the same definition the migration applies.
- The three partial unique indexes (tenancy, import_batch, billing_config) are declared for both `sqlite_where` and `postgresql_where` (R-4), so the invariants are enforced and testable locally — the earlier PostgreSQL-only/app-layer divergence is removed.
- Testing uses in-memory SQLite per AGENTS.md; PostgreSQL-native behavior is re-confirmed in CI. **PASS**

## Project Structure

### Documentation (this feature)

```text
specs/001-database-schema/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output — table-to-module map + cross-cutting rules only
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── schema.md        # Phase 1 output — DB-level contract
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml
└── src/
    ├── models/
    │   ├── base.py              # shared mixins, UTC-aware datetime type, money()/currency() helpers,
    │   │                        #   immutable-trigger DDL registration (R-2, R-3, R-5, R-8)
    │   ├── identity.py          # US1: organization, admin_user
    │   ├── tenancy.py           # US2: property, room, tenancy, tenant, sender_alias,
    │   │                        #      tenant_access_credential, tenant_session
    │   ├── ingestion.py         # US3: import_profile, import_channel_category_mapping,
    │   │                        #      import_batch, staged_import_row
    │   ├── ledgers_billing.py   # US4: billing_config, billing_override, standard_amount_change,
    │   │                        #      transaction, monthly_bill, payment_allocation,
    │   │                        #      advance_movement, bill_adjustment,
    │   │                        #      utility_provider, utility_bill_payment
    │   ├── settings.py          # US5: portal_setting
    │   └── audit.py             # US6: audit_log, admin_session, admin_login_attempt,
    │                            #      tenant_login_attempt
    ├── enums.py                 # docs/04 §4 value sets (TEXT + CHECK behavior)
    ├── db.py                    # engine/session config (PostgreSQL prod / SQLite local)
    ├── seed.py                  # idempotent seed (docs/04 §12)  [US7]
    └── migrations/
        ├── alembic.ini                # single Alembic config (D-1)
        ├── env.py
        └── versions/
            └── 0001_initial_schema.py   # single reversible baseline [US8]
tests/
├── conftest.py                  # in-memory SQLite per test (PostgreSQL via DATABASE_URL in CI)
├── test_identity.py             # US1
├── test_tenancy.py              # US2
├── test_ingestion.py            # US3
├── test_ledgers_billing.py      # US4
├── test_settings.py             # US5
├── test_audit.py                # US6
├── test_seed.py                 # US7
└── test_migration.py            # US8
```

**Structure Decision**: single `backend/` project trimmed to the data layer. Models are grouped **one module per area** — `identity`, `tenancy`, `ingestion`, `ledgers_billing`, `settings`, `audit` — matching the spec's user stories (US1–US6), with shared infrastructure in `base.py`/`enums.py`. Tests live in the repository-root `tests/`, **one file per user story**, plus `conftest.py`; shared base-helper behavior (money/currency, UTC-aware type) is asserted inside the story file that first exercises it. The frontend and API layer are separate features and are intentionally absent here.

## Testing Strategy

- Every task names the test it is verified by; tests are written first within each story and must fail before the implementation lands (constitution Principle V).
- Default engine is a fresh **in-memory SQLite** database per test; tests must never open `utility_billing_dev.db` (AGENTS.md).
- Because R-4 and R-5 are now native on SQLite too, partial-index behavior and immutability triggers are validated locally; the same tests run against PostgreSQL in CI for engine equivalence (SC-010).
- Test files map 1:1 to user stories (list above); `tests/test_seed.py` proves idempotency (US7), `tests/test_migration.py` proves apply→downgrade→reapply (US8).

## Complexity Tracking

> Filled ONLY if Constitution Check has violations that must be justified

No Constitution Check violations. Section intentionally empty.

## Open Questions — resolved

1. **`staged_import_row.duplicate_key` is NOT unique** (`docs/04` §6.7, §10.1); only `transaction.duplicate_key` is unique. Rows with `parse_status = 'duplicate'` must remain stageable (spec FR-018).
2. **`organization.timezone` is validated at the model layer** as a valid IANA name and defaults to `Africa/Lagos` (`docs/04` §6.2; spec FR-026); no API or auth logic is added.
3. **`billing_config` enforces one org-wide row per organization** via the partial unique index `UNIQUE (organization_id) WHERE property_id IS NULL` (`docs/04` §6.4, §8 item 10; spec FR-004/FR-020).

## Implementation decisions

Rulings for the decisions `/speckit.analyze` found unspecified; each applies on both engines unless stated.

- **D-1 Alembic config.** One Alembic config lives at `backend/src/migrations/alembic.ini` (matching quickstart.md). If `backend/pyproject.toml`'s `[tool.alembic]` table duplicates it, T002 removes that table so there is a single `script_location`.
- **D-2 Seed values.** Deployment values come from env vars `ORG_NAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH` (pre-hashed; this feature adds no hashing code, FR-025), and `STANDARD_AMOUNT_MINOR`; the seed fails loudly if any is missing, and tests pass fixed values. Idempotency keys: `organization` = skip if any organization exists; `admin_user` = `email`; `import_profile` / `utility_provider` = `code`; `import_channel_category_mapping` = `(profile, channel, direction)`; `billing_config` = the org-wide row; `portal_setting` = `(scope_type, scope_id, setting_key)`. The `PAYVICE_AVANTUS` mappings are the `docs/06` §11.1 channel/direction → category rows (`FUNDING` credit → `tenant_payment`, `BEDC` debit → `utility_bill_payment`, `TRANSFER`/`CHARGE`/`VAT` debit → `ignored`, `COMMISSION` any → `excluded`).
- **D-3 Timezone validation.** `Organization.timezone` is validated by a SQLAlchemy `@validates` hook using `zoneinfo.ZoneInfo`; `tzdata` stays a dependency so IANA names resolve on all platforms (FR-026).
- **D-4 PostgreSQL switch.** The PG path is enabled by `TEST_DATABASE_URL` pointing at a throwaway database; PG variants skip when it is unset. CI wiring is deferred, so T037 runs manually until CI exists. `DATABASE_URL` is never the test switch.
- **D-5 PostgreSQL isolation.** Each PG test resets state with `drop_all` + `create_all` + the trigger DDL, so no residue leaks between tests.
- **D-6 `updated_at` defaults.** Every `docs/04` §11.2 table gets a model-side `default` and `onupdate` from the shared UTC-now helper — no server-side defaults.
- **D-7 Session validity.** The session rule is tested only as a pure predicate over stored columns; no authentication code is delivered (FR-025).
- **D-8 Triggers.** One function returns the per-engine immutable-trigger SQL. `create_all` runs it via an `after_create` listener; the baseline migration calls the same function explicitly with `op.execute`; `downgrade` drops the triggers.

## Notes on artifacts

`specs/001-database-schema/tasks.md` is regenerated by `/speckit.tasks` against this plan, so it references the modules, test files, and both-engine decisions above. The three stale files — `task_structure_plan.txt`, `CONVERGENCE_ANALYSIS.md`, and `convergence_result.json` — described the previous module layout and the PostgreSQL-only stance and have been removed.
