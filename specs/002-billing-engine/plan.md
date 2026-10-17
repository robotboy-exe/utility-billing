# Implementation Plan: Tenant Billing Engine

**Branch**: `002-billing-engine` | **Date**: 2026-10-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-billing-engine/spec.md` and the plan input in this pass.

**Note**: Filled in by `/speckit.plan`; its definition describes the execution workflow.

## Summary

Deliver the tenant billing engine defined by `docs/05-billing-engine.md` on top of the existing 29-table schema (`docs/04-database.md`): lazy rolling bill generation, deterministic chronological payment allocation, the append-only advance movement ledger with its reconciliation invariant, derived bill and tenancy status, audited bill adjustments (rate change, write-off), controlled corrections and reversals (wrong-match correction, complete reversal), and the read-only billing summaries. The engine is a **pure domain module** (no SQLAlchemy imports) with byte-for-byte testable algorithms, wrapped by a single persistence adapter that owns the database transaction and the `docs/05` §6.9 lock order. `docs/05` is the source of intent and `docs/04` the table contract; this plan and [data-model.md](data-model.md) reference them by section and never restate columns. Type/enforcement decisions are in [research.md](research.md); the engine's callable contract is in [contracts/engine.md](contracts/engine.md); runnable validation is in [quickstart.md](quickstart.md).

**Schema guard**: this feature adds **no schema change**. It reads and writes the existing tables (`tenancy`, `monthly_bill`, `transaction`, `transaction_match`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `billing_config`, `billing_override`, `organization`) and introduces at most new non-persisted domain types. If implementation appears to need a column or table, that is escalated and stopped, not made.

**Scope guard**: no utility-provider spend logic, no PDF/statement parsing, no tenant-portal visibility rules, no authentication/authorization, and no frontend or API implementation (`docs/05` §1–§2; spec Out of Scope).

**Delta**: this is a new feature, not an amendment. It builds on spec `001-database-schema` (already implemented) and adds the billing behaviour the schema was shaped for (`docs/04` §7 derived state; `docs/05` §16 test scenarios; `docs/05` §17 locked rules).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: none added. Standard-library `zoneinfo` for the business timezone; the existing set (SQLAlchemy 2.x, Alembic, psycopg, `tzdata`, pytest) is reused only by the persistence adapter and tests (`research.md` "Libraries").

**Storage**: PostgreSQL (production and CI), SQLite (local development and tests); the engine's domain layer is storage-agnostic.

**Testing**: pytest; default is a fresh **in-memory SQLite** database per test (never the dev database file, per AGENTS.md); the same suite can run against PostgreSQL via `TEST_DATABASE_URL`. One test file per user story under the repository-root `tests/`. Pure-domain logic (ordering, status, arithmetic) is additionally tested without any database.

**Target Platform**: Linux free-tier host (synchronous, lazy, no workers or schedulers) + local development.

**Project Type**: backend billing domain module + persistence adapter + read-only report queries (the billing slice of a FastAPI service, `docs/03` §6.7.6).

**Performance Goals**: light MVP load (`docs/03` §14.5); determinism and correctness prioritized over scale. Allocation is O(payments × open bills) per tenancy, which is negligible at 22 rooms.

**Constraints**: no background scheduler (lazy generation on real usage); money integer minor units + explicit currency (no floats); append-only financial records (corrections are reversals); the billing engine MUST be independent of the ORM, the transaction source, the UI and the API (constitution Principle II); every query filters `organization_id`; month boundaries in the organization timezone.

**Scale/Scope**: single-organization MVP; 6 user stories across generation, allocation, adjustments, corrections, status/summaries and manual matching.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I — Financial correctness & immutable history**: Conforms. All money stays integer minor units with explicit currency (`docs/04` §3.4–3.5); the engine writes neither floats nor schema changes. All mutations are append-only: allocations, advance movements, adjustments and matches are new rows; a bill's `final_amount_minor` changes only alongside an appended `bill_adjustment` (`docs/04` §8.7); `transaction` is never updated or deleted (spec FR-059). Corrections are reversal/correction rows (spec FR-035–FR-040). **PASS**
- **Principle II — Billing engine independence**: Conforms. The engine is a pure domain package with no SQLAlchemy, source, UI or API imports; persistence is isolated in one adapter that maps rows to domain objects (`research.md` R-1). Adding a payment source requires no engine change. **PASS**
- **Principle III — Ingestion reliability & integrity**: Conforms. The engine consumes already-staged, already-confirmed, normalized transactions only; it performs no parsing and persists no commission data (spec Out of Scope; `docs/05` §2). **PASS**
- **Principle IV — Two-ledger separation**: Conforms. Utility provider payments never enter matching and never settle tenant bills; allocations attach only to the active-match tenancy's bills (spec FR-011, FR-026, FR-058; `docs/04` §8.3, §8.12). **PASS**
- **Principle V — Test-first financial logic**: Conforms. Each of the six stories ships a named test file written before its implementation; the advance reconciliation invariant has a dedicated test (spec FR-021, SC-008; `docs/04` §7.5). **PASS**
- **Database & Schema discipline**: Conforms. No schema change; UUIDs and `organization_id` scoping honored; derived state is computed, never stored (spec FR-055); month boundaries use `organization.timezone` (spec FR-003; ADR-028); corrected records use reversal rows. **PASS**

**Gate result**: all gates **PASS**; no unjustified violation, so `Complexity Tracking` is empty.

### Post-design re-check

Re-evaluated after data-model/contracts/quickstart design:

- The domain/persistence split (R-1) keeps Principle II structural: only `repository.py` and `views.py` import SQLAlchemy; `engine.py`, `status.py`, `reconciliation.py`, `clock.py` and `domain.py` do not.
- Money is never converted to float in the domain layer (integers only), so R-3 of `001` and Principle I hold across the boundary.
- Advance movements are written in the same database transaction as their allocation, so the reconciliation invariant is sound by construction (spec FR-019, FR-021; `docs/04` §8.8).
- Concurrency assertions that only PostgreSQL can show (row locks under the §6.9 lock order) are gated on `TEST_DATABASE_URL` and skip locally (R-12). **PASS**

## Project Structure

### Documentation (this feature)

```text
specs/002-billing-engine/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output — domain types + table-to-rule map only
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── engine.md        # Phase 1 output — the engine's callable contract
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root, described for the implementation phase — not created here)

```text
backend/src/billing/
├── __init__.py
├── domain.py          # pure domain dataclasses/value objects: Tenancy, MonthlyBill,
│                      #   Payment, Match, Allocation, AdvanceMovement, BillAdjustment,
│                      #   BillingOverride, StandardAmountChange (no SQLAlchemy)
├── clock.py           # business-timezone month helpers over stdlib zoneinfo (pure)
├── engine.py          # generation, allocation, advance, adjustments, corrections (pure)
├── status.py          # derived bill status + was_written_off + tenancy state (pure)
├── reconciliation.py  # advance reconciliation invariant (pure)
├── repository.py      # the ONLY ORM-dependent write path: load/save rows, transaction
│                      #   boundary and the docs/05 §6.9 lock order (SQLAlchemy)
└── views.py           # read-only reporting queries (SQLAlchemy)
tests/
├── conftest.py                 # existing shared fixtures (in-memory SQLite; PG via TEST_DATABASE_URL)
├── test_bill_generation.py            # US1
├── test_allocation_advance.py         # US2
├── test_bill_adjustments.py           # US3
├── test_corrections.py                # US4
├── test_status_summaries.py           # US5
└── test_manual_matching_scoping.py    # US6
```

**Structure Decision**: the billing engine is a `backend/src/billing/` package split into a **pure domain core** (`domain.py`, `clock.py`, `engine.py`, `status.py`, `reconciliation.py` — no SQLAlchemy) and a **persistence/reporting edge** (`repository.py`, `views.py` — SQLAlchemy). This makes Principle II structural rather than aspirational, and lets the financial algorithms be tested without a database. Tests live in the repository-root `tests/`, **one file per user story**, per the `001` precedent.

## Testing Strategy

- Every task names the test it is verified by; tests are written first within each story and must fail before the implementation lands (constitution Principle V).
- Default engine is a fresh **in-memory SQLite** database per test via the existing `tests/conftest.py`; tests must never open `utility_billing_dev.db` (AGENTS.md).
- Pure-domain tests (payment ordering, status formulas, advance arithmetic, M1 month set, M3 write-off arithmetic) run without a database; persistence tests exercise the adapter on SQLite.
- Calendar-month boundaries around 23:59/00:00 and the `Africa/Lagos` default are tested through `clock.py` and the generation story (`docs/03` §10.4, §15; ADR-028).
- Concurrency that can only be shown on PostgreSQL (serialized locks per the §6.9 order) is gated on `TEST_DATABASE_URL` and skipped locally (R-12).
- Test files map 1:1 to stories (list above); the advance reconciliation invariant is proven in `tests/test_allocation_advance.py`.

## Complexity Tracking

> Filled ONLY if Constitution Check has violations that must be justified

No Constitution Check violations. Section intentionally empty.

## Open Questions — resolved

1. **Does a `draft` tenancy receive bills?** No — generation bills active tenancies (and, per M1, backfills occupied ranges); a draft tenancy is neither (spec Clarifications; `docs/05` §5.1).
2. **Who builds the admin report freshness note?** Not the engine's concern; the engine supplies the latest `statement_end_date` among `confirmed`/`completed` import batches and the months that ended after it, and the reporting layer formats the note (spec FR-052; `docs/05` §14.4).
3. **Advance reconciliation cadence** stays as the explicit open question `docs/04` §13 item 6; the engine must at minimum be able to compute the invariant and flag a mismatch whenever billing state is written (spec FR-021).
4. **No schema change is required.** The existing tables carry every column the engine needs; `transaction` stays immutable and matching lives in `transaction_match` (spec Assumptions; `docs/04` §6.5).

## Implementation decisions

Rulings for decisions `/speckit.plan` had to make; each is grounded in the docs or a runbook ruling.

- **D-1 Domain/persistence boundary.** The engine's algorithms live in pure modules over `domain.py` value objects; `repository.py` alone imports SQLAlchemy, loads state, calls the pure functions, and writes results inside one transaction. Domain objects carry integer minor units and explicit currency; no float ever crosses the boundary.
- **D-2 Business-timezone month.** `clock.py` computes "the month of an instant" and enumerates month starts between two dates using `zoneinfo.ZoneInfo(organization.timezone)`; default `Africa/Lagos`. `ensure_bills_through` receives a month computed by this helper (`docs/03` §10.4; ADR-028).
- **D-3 Generation set and M1.** For a target month `m`, a tenancy is generated when either (a) the tenancy is `active` and `m` is the running month or a missing past month not before its start month, or (b) `m` is within `[start_date month, end_date month]` inclusive for a tenancy that ended earlier (Samuel's ruling M1; `docs/05` §5.4). Move-in partial months are skipped unless a `bill` override exists; `skip` overrides suppress the bill. Creation is idempotent against `UNIQUE (tenancy_id, billing_month)`. Generation only creates bills: applying existing advance to newly created bills is done by the allocation layer (US2, D-6), which extends `ensure_bills_through`, so no US1 task calls `apply_advance` (US2).
- **D-4 Standard amount resolution.** For an ended month, the amount is the value in force at the start of the following month (so a change at 00:00 on the 1st belongs to the new month); for the running month it is the current `billing_config` value (`docs/05` §5.2; `docs/04` §6.4).
- **D-5 Allocation.** Payments are ordered by (date/time asc, amount asc, internal id); a null time is 00:00 in the business timezone. For each payment, bills with remaining due are filled oldest billing month first; each fill creates one allocation; the remainder becomes an advance `created` movement linked to the payment. The write path runs `reconcile` for every touched payment before commit and fails closed (rolls back, raises) on a mismatch (`docs/05` §6.2–6.4, §7.1; `docs/04` §7.5).
- **D-6 Advance application.** On generation and after a rate change, the oldest unallocated remainder is applied to bills oldest-first, each creating an allocation and an `applied` movement; the generation-time application lives in the allocation layer's extension of `ensure_bills_through` (US2, T013), not in generation itself. Restored advance during unmatch is not re-applied, but advance held on the tenancy's other payments is applied to any bill that owes again after a reversal or correction (`docs/05` §7.2, §7.3).
- **D-7 Reversal-to-advance primitive (R1).** A helper reverses one allocation and appends exactly one `created` advance movement for the reversed amount; it is the only path used by rate drops, reduced-bill corrections, complete reversal and wrong-match correction (Samuel's ruling R1; `docs/05` §7.4, §11.2, §12.1).
- **D-8 Rate change.** Compute the set of current-month bills of active tenancies; for each, append a `rate_change` adjustment to the new amount and update `final_amount_minor`/`is_adjusted`; a rise is covered by normal advance application; a drop reverses the excess from payments in the exact reverse `docs/05` §6.2 order (latest date/time, then larger amount, then higher id), one `created` movement each, then applies advance oldest-first (`docs/05` §5.3).
- **D-9 Write-off (M3).** A `write_off` adjustment records `previous_amount_minor` = the final amount before and `new_amount_minor` = net allocated (0 if none); the written-off amount is previous minus new; bill history/detail must expose original, written-off and final amounts. No schema change (Samuel's ruling M3; `docs/05` §5.3, §8.4).
- **D-10 Complete reversal.** In one transaction: reverse each allocation via the D-7 primitive; append `reversed` movements for the payment's whole remaining logged advance; append the reversal match row; apply advance held on the tenancy's other payments to any bill that owes again; and run `reconcile` on every touched payment before commit, rolling back and raising on mismatch (`docs/05` §7.2, §12.1; `docs/04` §7.5, §8.12).
- **D-11 Wrong-match correction (R2).** In one transaction under the §6.9 lock order: reverse allocations, clear advance, append the reversal match row, then append the new match and re-run allocation; apply advance held on the old tenancy's other payments to any bill that owes again; run `reconcile` on every touched payment before commit; any failure rolls the whole unit back (Samuel's ruling R2; `docs/05` §6.9, §7.2, §12, §13; `docs/04` §7.5).
- **D-12 Lock order.** `repository.py` locks tenancies in ascending id order and open bills `FOR UPDATE` ordered by month; SQLite (no row locks) relies on the single-writer/`StaticPool` test model. A concurrency test asserting the serialized order is gated on `TEST_DATABASE_URL` (PostgreSQL) and skips locally (`docs/05` §6.9; `docs/03` §5.2.1).
- **D-13 Derived status.** `status.py` implements the `docs/05` §8.4-first ordering over the signed net from `docs/04` §7.1 and the tenancy aggregates of `docs/05` §9; nothing is stored (spec FR-043–FR-048).
- **D-14 Read-only views.** `views.py` returns DTOs for the summaries; it issues no writes, so requesting a view cannot change a payment or an allocation (spec FR-054; Samuel's ruling F-03).
- **D-15 Reporting set.** `views.py` takes an injected report date for the freshness data and computes the closed-tenancy total and per-tenancy list with org scoping; visibility-policy enforcement beyond org/tenant scoping belongs to the portal feature and is not implemented here (`docs/05` §14.4, §14.5; `docs/03` §9.2).
- **D-16 Manual matching.** A manual match appends a `transaction_match` row and then runs the normal allocation path; the action is audited (`docs/05` §12, §13).
