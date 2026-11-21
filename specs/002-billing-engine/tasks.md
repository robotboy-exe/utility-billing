---

description: "Task list for the Tenant Billing Engine feature"
---

# Tasks: Tenant Billing Engine

**Input**: Design documents from `/specs/002-billing-engine/`

**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required for user stories), [research.md](research.md), [data-model.md](data-model.md), [contracts/engine.md](contracts/engine.md), [quickstart.md](quickstart.md)

**Tests**: REQUIRED. This feature is financial logic; the constitution (Principle V) and plan.md "Testing Strategy" require test-first. Every task below names the test file/function that proves it; within each story the test task is written and made to FAIL before the implementation tasks land.

## Execution constraints (from the request)

- **One test file per user story (6 stories), in dependency order** — `tests/test_bill_generation.py` (US1), `tests/test_allocation_advance.py` (US2), `tests/test_bill_adjustments.py` (US3), `tests/test_corrections.py` (US4), `tests/test_status_summaries.py` (US5), `tests/test_manual_matching_scoping.py` (US6), reusing the existing shared `tests/conftest.py`.
- **No schema change.** The engine reads/writes the existing tables; if a column or table appears necessary, stop and escalate (plan "Schema guard").
- **Test run command** (AGENTS.md): `.venv/bin/python -m pytest tests -q`. Run only the current task's tests while working, e.g. `.venv/bin/python -m pytest tests/test_bill_generation.py::test_generation_is_idempotent -q`.
- **Concurrency that only PostgreSQL can show** names `TEST_DATABASE_URL` and skips when it is unset (plan D-12).
- **Scope**: tasks cover only what `spec.md` FR-001..FR-060 and the Step 3 checklist require. No utility spend, parsing, portal visibility, auth, or API/UI (spec Out of Scope).
- **Every task is unticked `[ ]`.**
- **Do not commit.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1..US6); setup, foundational, and polish tasks carry no story label
- Every task names the exact test file/function that proves it

## Path Conventions

- **Billing engine (plan.md "Project Structure")**: `backend/src/billing/` (`domain.py`, `clock.py`, `engine.py`, `status.py`, `reconciliation.py`, `repository.py`, `views.py`)
- **Tests**: repository-root `tests/`, one file per user story plus the existing `conftest.py`

## Test-file → story map

| Test file | Story | Priority | Requirements covered |
|---|---|---|---|
| `tests/test_bill_generation.py` | US1 | P1 | FR-001–FR-010, FR-057 |
| `tests/test_allocation_advance.py` | US2 | P2 | FR-011–FR-026, FR-014 (`test_payment_matched_later_with_earlier_date_fills_only_what_is_left`), FR-020 (R1) |
| `tests/test_bill_adjustments.py` | US3 | P3 | FR-027–FR-034, FR-060 |
| `tests/test_corrections.py` | US4 | P4 | FR-035–FR-042, FR-037 (R2) |
| `tests/test_status_summaries.py` | US5 | P5 | FR-043–FR-055 |
| `tests/test_manual_matching_scoping.py` | US6 | P6 | FR-056–FR-059 |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package skeleton and test fixtures

- [ ] T001 Create the billing package skeleton: `backend/src/billing/__init__.py` plus empty docstring-stubbed modules `domain.py`, `clock.py`, `engine.py`, `status.py`, `reconciliation.py`, `repository.py`, `views.py`. Pure setup; no proof required.
- [ ] T002 [P] Extend the existing `tests/conftest.py` with billing builders over the existing in-memory SQLite `db_engine` fixture: helpers to create an `organization` (with timezone), a `property`/`room`, a `tenancy` (status, `start_date`, `end_date`), a `monthly_bill`, and a matched `transaction` + `transaction_match` for a tenancy. Proved by: `tests/test_bill_generation.py::test_generation_creates_one_bill_for_active_tenancy`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure domain types and the single ORM write boundary all stories share.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 [P] Create `backend/src/billing/domain.py` with the pure domain value objects and enums of [data-model.md](data-model.md) §1 (`OrganizationContext`, `Tenancy`, `BillingConfig`, `StandardAmountChange`, `MonthlyBill`, `Payment`, `Match`, `Allocation`, `AdvanceMovement`, `BillAdjustment`, `ImportBatchSummary`, `AuditEntry`) using `int` minor units and a `currency` string, and **no** SQLAlchemy import (research.md R-1, R-13). Proved by: `tests/test_allocation_advance.py::test_partial_payment_reduces_outstanding`.
- [ ] T004 [P] Create `backend/src/billing/repository.py` scaffolding: the single ORM-dependent boundary that loads domain state from the existing models (`backend/src/models/`), the shared transaction context manager, the `docs/05` §6.9 lock-order helper (lock tenancies ascending id, then open bills `FOR UPDATE` by month), and the `audit_log` append helper for mutating operations. Proved by: `tests/test_allocation_advance.py::test_advance_movement_written_atomically_with_allocation`.

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Lazy rolling bill generation and month timing (Priority: P1) 🎯 MVP

**Goal**: `ensure_bills_through(organization_id, month)` creates missing bills for active and closed tenancies up to the business-timezone month, backfills through a tenancy's move-out month (M1), takes no override input, resolves the month's standard amount, and is idempotent.

**Independent Test**: With a controllable clock, assert the exact bill set for a fresh org, repeated calls, a closed tenancy, move-in/move-out months, a rate change at a month boundary, a `draft` tenancy, and a different timezone.

**Requirements**: FR-001–FR-010, FR-057.

### Tests for User Story 1 (write FIRST, ensure they FAIL) ⚠️

- [ ] T005 [P] [US1] Write `tests/test_bill_generation.py`: `test_generation_creates_one_bill_for_active_tenancy`, `test_generation_does_not_bill_vacant_rooms`, `test_generation_is_idempotent`, `test_generation_is_organization_scoped`, `test_m1_bills_through_moveout_month_then_stops`, `test_movein_month_billed_in_full_by_default`, `test_same_month_movein_and_moveout_billed_once_in_full`, `test_moveout_partial_month_billed_in_full`, `test_late_bill_uses_amount_in_force_at_month_end`, `test_rate_change_saved_at_month_start_belongs_to_new_month`, `test_running_month_uses_current_amount`, `test_draft_tenancy_receives_no_bill`, `test_draft_tenancy_never_billed`, `test_business_timezone_month_boundary_around_midnight`, `test_admin_report_request_generates_missing_bills`, `test_admin_dashboard_load_generates_missing_bills`, `test_generation_is_not_reachable_from_tenant_read_path`, `test_concurrent_generation_creates_one_bill_per_tenancy_month` (names `TEST_DATABASE_URL`; skips locally). Proved by: the functions themselves.

### Implementation for User Story 1

- [ ] T006 [US1] Create `backend/src/billing/clock.py` (pure): `business_month(instant, tz)` and `month_starts_between(start_date, end_date)` over stdlib `zoneinfo`, defaulting to the organization timezone (research.md R-2; `docs/03` §10.4; ADR-028). Proved by: `tests/test_bill_generation.py::test_business_timezone_month_boundary_around_midnight` and `tests/test_bill_generation.py::test_rate_change_saved_at_month_start_belongs_to_new_month`.
- [ ] T007 [US1] Implement generation planning in `backend/src/billing/engine.py`: `expected_bill_months(tenancy, target_month)` (M1 date-derived range; every month in range billed in full by default; no override input and no skip decision) and `resolve_standard_amount(config, changes, month, now)` (ended month = amount in force at start of the next month; running month = current) (plan D-3, D-4; `docs/05` §5.1, §5.2, §5.4). Proved by: `tests/test_bill_generation.py::test_m1_bills_through_moveout_month_then_stops`, `tests/test_bill_generation.py::test_late_bill_uses_amount_in_force_at_month_end`, `tests/test_bill_generation.py::test_movein_month_billed_in_full_by_default`, `tests/test_bill_generation.py::test_same_month_movein_and_moveout_billed_once_in_full`, `tests/test_bill_generation.py::test_draft_tenancy_receives_no_bill`, `tests/test_bill_generation.py::test_draft_tenancy_never_billed`, `tests/test_bill_generation.py::test_running_month_uses_current_amount`.
- [ ] T008 [US1] Implement `ensure_bills_through(organization_id, month)` in `backend/src/billing/repository.py`: load active and closed tenancies (`docs/05` §5.1: a `draft` tenancy is never billed), call `expected_bill_months` and `resolve_standard_amount`, and insert missing bills with conflict-ignore on `UNIQUE (tenancy_id, billing_month)`. Generation only creates bills; applying existing advance to them is added by T013 (US2), so a US1 task never calls the US2 `apply_advance` (plan D-3; contract §2; `docs/05` §5.1, §10; ADR-022). Proved by: `tests/test_bill_generation.py::test_generation_creates_one_bill_for_active_tenancy`, `tests/test_bill_generation.py::test_generation_does_not_bill_vacant_rooms`, `tests/test_bill_generation.py::test_generation_is_idempotent`, `tests/test_bill_generation.py::test_generation_is_organization_scoped`, `tests/test_bill_generation.py::test_movein_month_billed_in_full_by_default`, `tests/test_bill_generation.py::test_same_month_movein_and_moveout_billed_once_in_full`, `tests/test_bill_generation.py::test_moveout_partial_month_billed_in_full`, `tests/test_bill_generation.py::test_draft_tenancy_never_billed`, `tests/test_bill_generation.py::test_admin_report_request_generates_missing_bills`, `tests/test_bill_generation.py::test_admin_dashboard_load_generates_missing_bills`, `tests/test_bill_generation.py::test_concurrent_generation_creates_one_bill_per_tenancy_month`.
- [ ] T009 [US1] Wire the four admin-triggered entry points to call generation and ensure tenant-facing paths cannot: expose generation only through the admin adapter operations (dashboard load, allocation, import batch confirm, admin report request) and keep it out of the tenant read path (plan D-1; `docs/05` §5.1; `docs/03` §5.2.1; ADR-022). Proved by: `tests/test_bill_generation.py::test_generation_is_not_reachable_from_tenant_read_path` and `tests/test_bill_generation.py::test_admin_dashboard_load_generates_missing_bills`.

**Checkpoint**: US1 fully functional and testable independently.

---

## Phase 4: User Story 2 - Chronological payment allocation and advance credit (Priority: P2)

**Goal**: Deterministic oldest-first allocation and the append-only advance movement ledger with its reconciliation invariant, including the R1 reversal-to-advance primitive.

**Independent Test**: Seed bills and matched payments (oldest-first, newest-first, identical timestamps, overpayment, payment-before-bill) and assert allocations, advance, ledger and reconciliation.

**Requirements**: FR-011–FR-026, FR-020 (R1).

### Tests for User Story 2 (write FIRST, ensure they FAIL) ⚠️

- [ ] T010 [P] [US2] Write `tests/test_allocation_advance.py`: `test_partial_payment_reduces_outstanding`, `test_overpayment_creates_advance`, `test_oldest_bill_filled_first`, `test_payment_received_after_month_end_allocates_to_oldest`, `test_payment_before_bill_held_as_advance_then_fills_bill`, `test_new_bill_generation_applies_existing_advance_oldest_first`, `test_newest_first_input_is_reordered_oldest_first`, `test_identical_timestamps_tie_break_by_amount_then_id`, `test_payment_without_time_counts_as_business_midnight`, `test_allocation_only_to_active_match_tenancy_bills`, `test_allocation_calls_ensure_bills_through_inside_its_transaction`, `test_allocation_failure_midway_writes_nothing`, `test_batch_confirm_locks_batch_and_rechecks_status`, `test_batch_confirm_calls_ensure_bills_through_inside_its_transaction`, `test_double_confirm_of_same_batch_allocates_once`, `test_reprocessing_payment_allocates_nothing_new`, `test_manual_source_payment_allocated_like_imported`, `test_advance_ledger_reconciles_with_derived_balance`, `test_advance_reconciliation_mismatch_is_flagged`, `test_reconciliation_skips_payment_unmatched_by_correction`, `test_reconciliation_mismatch_on_write_rolls_back_and_raises`, `test_advance_movement_written_atomically_with_allocation`, `test_closed_tenancy_advance_stays_recorded_and_not_taken`, `test_closed_tenancy_advance_pays_bill_generated_after_closure`, `test_roommate_change_has_no_effect`, `test_allocation_cap_never_exceeded`, `test_concurrent_allocations_on_one_tenancy_never_overallocate` (names `TEST_DATABASE_URL`; skips locally), `test_manual_match_to_closed_tenancy_fills_its_outstanding_bills_oldest_first`, `test_payment_remainder_on_closed_tenancy_is_advance_that_stays_recorded`, `test_payment_matched_later_with_earlier_date_fills_only_what_is_left`, `test_payment_splits_across_three_bills_2000_2000_1000`, `test_overpayment_across_two_bills_leaves_1000_advance`, `test_any_allocation_reversal_appends_one_created_movement` (R1). Proved by: the functions themselves.

### Implementation for User Story 2

- [ ] T011 [US2] Implement the pure allocation core in `backend/src/billing/engine.py`: `order_payments(payments)` (date/time asc, amount asc, internal id; null time = 00:00 business tz), `allocate(bills, payments)` (oldest bill first, one allocation per fill, remainder → `created`), and `apply_advance(bills, remainders)` (oldest remainder, oldest bill first, `applied`) (plan D-5, D-6; `docs/05` §6.2–6.4, §7.1–7.3). Proved by: `tests/test_allocation_advance.py::test_partial_payment_reduces_outstanding`, `tests/test_allocation_advance.py::test_overpayment_creates_advance`, `tests/test_allocation_advance.py::test_oldest_bill_filled_first`, `tests/test_allocation_advance.py::test_payment_received_after_month_end_allocates_to_oldest`, `tests/test_allocation_advance.py::test_payment_before_bill_held_as_advance_then_fills_bill`, `tests/test_allocation_advance.py::test_newest_first_input_is_reordered_oldest_first`, `tests/test_allocation_advance.py::test_identical_timestamps_tie_break_by_amount_then_id`, `tests/test_allocation_advance.py::test_payment_without_time_counts_as_business_midnight`, `tests/test_allocation_advance.py::test_payment_splits_across_three_bills_2000_2000_1000`, `tests/test_allocation_advance.py::test_overpayment_across_two_bills_leaves_1000_advance`.
- [ ] T012 [US2] Implement `backend/src/billing/reconciliation.py` (pure): the derived-unallocated vs logged-advance invariant, returning a mismatch result, and skipping any payment that has no active match (an unmatched payment has no net advance and is outside the identity; a payment unmatched by a correction must not look like a mismatch) (`docs/05` §7.4; `docs/04` §7.5, §8.2). Proved by: `tests/test_allocation_advance.py::test_advance_ledger_reconciles_with_derived_balance`, `tests/test_allocation_advance.py::test_advance_reconciliation_mismatch_is_flagged`, and `tests/test_allocation_advance.py::test_reconciliation_skips_payment_unmatched_by_correction`.
- [ ] T013 [US2] Implement `allocate_for_tenancy(tenancy_id)` and the allocation half of `confirm_import_batch(batch_id)` in `backend/src/billing/repository.py`. Both entry points call `ensure_bills_through(organization_id, month)` **inside their own transaction** before allocating (so a concurrent allocation or confirm cannot race generation), and `confirm_import_batch` locks the `import_batch` row and re-checks its status before writing (the double-confirm guard), all in the §6.9 transaction/lock order. Extend `ensure_bills_through` so that, after it creates new bills, it applies existing advance to them with `apply_advance` (oldest remainder first, oldest bill first, `applied` movements, atomic with the allocations), including a closed tenancy's own bills generated after closure: its advance pays them oldest first, any remainder stays recorded, and no other tenancy's bill takes it (Samuel's ruling S7; `docs/05` §7.2, §7.5). A payment matched to a closed tenancy is still allocated to that tenancy's outstanding bills by the normal rules (Samuel's ruling S6; `docs/05` §13). Run allocation, write `payment_allocation` + `advance_movement` rows atomically (created/applied), enforce the allocation cap, and **before commit** run `reconcile` for every payment touched, rolling the transaction back and raising an integrity error on any mismatch (fail closed, like the import control totals) (plan D-5, D-6; contract §2; `docs/05` §6.4, §6.9, §7.2; `docs/04` §8.1, §8.8, §7.5; `docs/03` §5.2.1). Proved by: `tests/test_allocation_advance.py::test_allocation_only_to_active_match_tenancy_bills`, `tests/test_allocation_advance.py::test_reprocessing_payment_allocates_nothing_new`, `tests/test_allocation_advance.py::test_manual_source_payment_allocated_like_imported`, `tests/test_allocation_advance.py::test_advance_movement_written_atomically_with_allocation`, `tests/test_allocation_advance.py::test_closed_tenancy_advance_stays_recorded_and_not_taken`, `tests/test_allocation_advance.py::test_roommate_change_has_no_effect`, `tests/test_allocation_advance.py::test_allocation_cap_never_exceeded`, `tests/test_allocation_advance.py::test_payment_before_bill_held_as_advance_then_fills_bill`, `tests/test_allocation_advance.py::test_new_bill_generation_applies_existing_advance_oldest_first`, `tests/test_allocation_advance.py::test_allocation_calls_ensure_bills_through_inside_its_transaction`, `tests/test_allocation_advance.py::test_allocation_failure_midway_writes_nothing`, `tests/test_allocation_advance.py::test_batch_confirm_locks_batch_and_rechecks_status`, `tests/test_allocation_advance.py::test_double_confirm_of_same_batch_allocates_once`, `tests/test_allocation_advance.py::test_batch_confirm_calls_ensure_bills_through_inside_its_transaction`, `tests/test_allocation_advance.py::test_reconciliation_mismatch_on_write_rolls_back_and_raises`, `tests/test_allocation_advance.py::test_closed_tenancy_advance_pays_bill_generated_after_closure`, `tests/test_allocation_advance.py::test_concurrent_allocations_on_one_tenancy_never_overallocate`, `tests/test_allocation_advance.py::test_manual_match_to_closed_tenancy_fills_its_outstanding_bills_oldest_first`, `tests/test_allocation_advance.py::test_payment_remainder_on_closed_tenancy_is_advance_that_stays_recorded`, `tests/test_allocation_advance.py::test_payment_matched_later_with_earlier_date_fills_only_what_is_left`.
- [ ] T014 [US2] Implement the R1 reversal-to-advance primitive in `backend/src/billing/engine.py`: `reverse_allocation(allocation)` returns a `reversal` allocation plus **exactly one** `created` advance movement for the reversed amount; this is the only primitive used by rate drops, reduced-bill corrections, complete reversal and wrong-match correction (Samuel's ruling R1; `docs/05` §7.4, §11.2, §12; `docs/04` §7.5). Proved by: `tests/test_allocation_advance.py::test_any_allocation_reversal_appends_one_created_movement`.

**Checkpoint**: US1 and US2 independently functional.

---

## Phase 5: User Story 3 - Bill adjustments: rate change and write-off (Priority: P3)

**Goal**: Audited rate changes over current-month bills of active tenancies (rise and drop) and audited write-offs of closed tenancies, with the R1 primitive and M3 arithmetic.

**Independent Test**: Apply a rise and a drop to unpaid/part-paid/paid current-month bills, then write off a closed tenancy, asserting adjustments, advance movements and derived amounts.

**Requirements**: FR-027–FR-034, FR-060.

### Tests for User Story 3 (write FIRST, ensure they FAIL) ⚠️

- [ ] T015 [P] [US3] Write `tests/test_bill_adjustments.py`: `test_rate_rise_makes_paid_bill_part_paid`, `test_rate_rise_paid_by_advance`, `test_rate_drop_excess_becomes_advance_in_reverse_order`, `test_rate_drop_applies_advance_to_oldest_outstanding`, `test_rate_change_never_touches_past_months`, `test_rate_change_never_touches_closed_tenancy`, `test_rate_change_never_touches_write_off`, `test_rate_change_month_is_business_timezone_month_of_save_moment`, `test_rate_change_to_zero_makes_bills_no_charge_and_returns_payments_as_advance`, `test_reduced_bill_below_allocated_frees_excess`, `test_rate_change_adjustment_records_note_and_admin`, `test_rate_change_persists_new_standard_amount_for_following_months`, `test_confirm_rate_drop_persists_reversals_and_created_movements`, `test_confirm_rate_rise_applies_advance_and_persists_movements`, `test_confirm_rate_change_to_zero_persists_advance`, `test_rate_change_adjusts_unpaid_part_paid_and_paid_bills_together`, `test_rate_drop_part_paid_below_new_amount_adjusts_without_reversal`, `test_rate_rise_leaves_unpaid_bill_unpaid`, `test_rate_change_runs_in_one_transaction_and_failure_writes_nothing`, `test_rate_change_does_not_call_ensure_bills_through`, `test_rate_change_creates_audit_entry`, `test_rate_drop_tie_break_larger_amount_then_higher_id_taken_first`, `test_rate_drop_reverse_order_independent_of_allocation_order`, `test_rate_change_and_allocation_serialize_under_lock_order` (names `TEST_DATABASE_URL`; skips locally), `test_write_off_closed_tenancy_zeroes_balance`, `test_write_off_history_shows_original_written_off_final` (M3), `test_write_off_records_note_and_admin_identity`, `test_write_off_creates_audit_entry`, `test_write_off_sets_adjusted_flag`, `test_write_off_refused_on_active_tenancy`, `test_write_off_tenancy_writes_one_adjustment_per_owing_bill`, `test_write_off_has_auto_generated_note_and_optional_custom_note`, `test_partial_payment_then_write_off_of_the_rest_on_closed_tenancy`, `test_no_arbitrary_per_room_amount_override`, `test_bill_amount_change_requires_adjustment`, `test_movein_bill_write_off_on_active_tenancy_zeroes_balance`, `test_movein_bill_write_off_on_closed_tenancy`, `test_movein_bill_write_off_part_paid_reads_paid_and_flagged`, `test_movein_bill_write_off_refused_for_any_other_bill`, `test_movein_bill_write_off_refused_when_bill_missing_or_nothing_outstanding`, `test_movein_bill_write_off_has_no_chosen_amount`, `test_movein_bill_write_off_records_note_admin_and_audit_entry`, `test_whole_tenancy_write_off_after_movein_write_off_skips_zero_balance_bill`, `test_rate_change_skips_bill_with_write_off_adjustment`, `test_rate_change_skips_part_written_off_movein_bill_on_active_tenancy`. Proved by: the functions themselves.

### Implementation for User Story 3

- [ ] T016 [US3] Implement `rate_change_plan(bills, payments, config, changes, new_amount, now)` in `backend/src/billing/engine.py`: select current-month bills of active tenancies, excluding every bill that already has a write-off adjustment (a written-off bill is final), append one `rate_change` adjustment each (paid or not), and on a drop reverse the excess from the payments in the exact reverse `docs/05` §6.2 order via T014, then apply advance oldest-first; a change to 0 makes those bills no charge and returns the money already allocated to them as advance (plan D-8; `docs/05` §5.3, §9; ADR-010, ADR-023). Proved by: `tests/test_bill_adjustments.py::test_rate_rise_makes_paid_bill_part_paid`, `tests/test_bill_adjustments.py::test_rate_rise_paid_by_advance`, `tests/test_bill_adjustments.py::test_rate_drop_excess_becomes_advance_in_reverse_order`, `tests/test_bill_adjustments.py::test_rate_drop_applies_advance_to_oldest_outstanding`, `tests/test_bill_adjustments.py::test_rate_change_never_touches_past_months`, `tests/test_bill_adjustments.py::test_rate_change_never_touches_closed_tenancy`, `tests/test_bill_adjustments.py::test_rate_change_never_touches_write_off`, `tests/test_bill_adjustments.py::test_rate_change_to_zero_makes_bills_no_charge_and_returns_payments_as_advance`, `tests/test_bill_adjustments.py::test_reduced_bill_below_allocated_frees_excess`, `tests/test_bill_adjustments.py::test_rate_drop_tie_break_larger_amount_then_higher_id_taken_first`, `tests/test_bill_adjustments.py::test_rate_drop_reverse_order_independent_of_allocation_order`, `tests/test_bill_adjustments.py::test_rate_change_skips_bill_with_write_off_adjustment`, `tests/test_bill_adjustments.py::test_rate_change_skips_part_written_off_movein_bill_on_active_tenancy`.
- [ ] T017 [US3] Implement `write_off_plan(tenancy, bills, net_allocated_by_bill)` in `backend/src/billing/engine.py`: a whole-tenancy plan with one `write_off` adjustment for every bill of the closed tenancy that still has a balance; each records `previous_amount_minor` = final amount before and `new_amount_minor` = net allocated (0 if none); the written-off amount is previous minus new; a chosen amount or selection is not supported (parked); expose original / written-off / final for history and detail views (Samuel's rulings M3 and S5; plan D-9; `docs/05` §5.3, §8.4, §11.1). Also implement `move_in_write_off_plan(tenancy, bills, net_allocated_by_bill)` (pure): one `write_off` adjustment on the move-in month bill of an active or a closed tenancy with a balance, no chosen amount, no other bill, and a refusal result when the bill is missing or has nothing outstanding (Samuel's ruling S8; plan D-9; `docs/05` §5.3, §5.4; §15 item 19). Proved by: `tests/test_bill_adjustments.py::test_write_off_closed_tenancy_zeroes_balance`, `tests/test_bill_adjustments.py::test_write_off_history_shows_original_written_off_final`, `tests/test_bill_adjustments.py::test_write_off_refused_on_active_tenancy`, `tests/test_bill_adjustments.py::test_write_off_tenancy_writes_one_adjustment_per_owing_bill`, `tests/test_bill_adjustments.py::test_movein_bill_write_off_on_active_tenancy_zeroes_balance`, `tests/test_bill_adjustments.py::test_movein_bill_write_off_on_closed_tenancy`, `tests/test_bill_adjustments.py::test_movein_bill_write_off_part_paid_reads_paid_and_flagged`, `tests/test_bill_adjustments.py::test_movein_bill_write_off_refused_for_any_other_bill`, `tests/test_bill_adjustments.py::test_movein_bill_write_off_has_no_chosen_amount`.
- [ ] T018 [US3] Implement `confirm_rate_change(new_amount, admin_id, note, now)` in `backend/src/billing/repository.py`: the current month is the business-timezone month of the save moment, same lock order as allocation, **without** calling `ensure_bills_through`; exclude every bill that already has a write-off adjustment (a written-off bill is final); in one transaction persist the new standard amount (`standard_amount_change` row and `billing_config`) so following months use it, the adjustments + `final_amount_minor` + `is_adjusted`, the reversal allocations and their `created` movements on a drop, the advance application (`applied` movements) on a rise, a drop and a change to 0, and the audit entry; before commit run `reconcile` for every payment touched, rolling back and raising an integrity error on a mismatch (plan D-8, D-12; contract §2; `docs/05` §5.3, §6.9, §7.4; `docs/03` §10.4; `docs/04` §8.7). Proved by: `tests/test_bill_adjustments.py::test_rate_change_adjustment_records_note_and_admin`, `tests/test_bill_adjustments.py::test_rate_change_never_touches_past_months`, `tests/test_bill_adjustments.py::test_rate_change_month_is_business_timezone_month_of_save_moment`, `tests/test_bill_adjustments.py::test_rate_change_persists_new_standard_amount_for_following_months`, `tests/test_bill_adjustments.py::test_confirm_rate_drop_persists_reversals_and_created_movements`, `tests/test_bill_adjustments.py::test_confirm_rate_rise_applies_advance_and_persists_movements`, `tests/test_bill_adjustments.py::test_confirm_rate_change_to_zero_persists_advance`, `tests/test_bill_adjustments.py::test_rate_change_adjusts_unpaid_part_paid_and_paid_bills_together`, `tests/test_bill_adjustments.py::test_rate_drop_part_paid_below_new_amount_adjusts_without_reversal`, `tests/test_bill_adjustments.py::test_rate_rise_leaves_unpaid_bill_unpaid`, `tests/test_bill_adjustments.py::test_rate_change_runs_in_one_transaction_and_failure_writes_nothing`, `tests/test_bill_adjustments.py::test_rate_change_does_not_call_ensure_bills_through`, `tests/test_bill_adjustments.py::test_rate_change_creates_audit_entry`, `tests/test_bill_adjustments.py::test_rate_change_and_allocation_serialize_under_lock_order`, `tests/test_bill_adjustments.py::test_rate_change_skips_bill_with_write_off_adjustment`, `tests/test_bill_adjustments.py::test_rate_change_skips_part_written_off_movein_bill_on_active_tenancy`.
- [ ] T019 [US3] Implement `record_write_off(tenancy_id, admin_id, note)` in `backend/src/billing/repository.py`: refuse a non-closed tenancy; in one transaction write one `write_off` adjustment for every bill of the closed tenancy that still has a balance (each with its previous/new amount per M3), carrying the auto-generated public note with the optional custom note and the admin identity; set each affected bill's adjusted flag and write one audit entry per adjustment (`docs/04` §6.5 does not say otherwise; audit_log §6.9) (plan D-9; contract §2; `docs/05` §5.3, §11.1; ADR-025; Samuel's ruling S5). Also implement `record_move_in_write_off(tenancy_id, admin_id, note)`: same single-transaction rules applied to the one move-in month bill of an active or a closed tenancy, refusing with nothing written when that bill does not exist or has nothing outstanding, so a later whole-tenancy write-off skips a bill that already has no balance (Samuel's ruling S8; plan D-9; contract §2; `docs/05` §5.3, §5.4, §8.4; §15 item 19). Proved by: `tests/test_bill_adjustments.py::test_write_off_closed_tenancy_zeroes_balance`, `tests/test_bill_adjustments.py::test_write_off_records_note_and_admin_identity`, `tests/test_bill_adjustments.py::test_write_off_creates_audit_entry`, `tests/test_bill_adjustments.py::test_write_off_sets_adjusted_flag`, `tests/test_bill_adjustments.py::test_no_arbitrary_per_room_amount_override`, `tests/test_bill_adjustments.py::test_bill_amount_change_requires_adjustment`, `tests/test_bill_adjustments.py::test_write_off_tenancy_writes_one_adjustment_per_owing_bill`, `tests/test_bill_adjustments.py::test_write_off_has_auto_generated_note_and_optional_custom_note`, `tests/test_bill_adjustments.py::test_partial_payment_then_write_off_of_the_rest_on_closed_tenancy`, `tests/test_bill_adjustments.py::test_movein_bill_write_off_refused_when_bill_missing_or_nothing_outstanding`, `tests/test_bill_adjustments.py::test_movein_bill_write_off_records_note_admin_and_audit_entry`, `tests/test_bill_adjustments.py::test_whole_tenancy_write_off_after_movein_write_off_skips_zero_balance_bill`.

**Checkpoint**: US1–US3 independently functional.

---

## Phase 6: User Story 4 - Corrections and reversals (Priority: P4)

**Goal**: Complete reversal (bank-reversed / confirmed duplicate) and the atomic R2 wrong-match correction under the §6.9 lock order.

**Independent Test**: Correct a wrong match and re-match atomically; complete-reverse a payment and assert bills owe again; force a failure and assert nothing was written.

**Requirements**: FR-035–FR-042, FR-037 (R2).

### Tests for User Story 4 (write FIRST, ensure they FAIL) ⚠️

- [ ] T020 [P] [US4] Write `tests/test_corrections.py`: `test_complete_reversal_bank_reversed_payment`, `test_complete_reversal_confirmed_duplicate`, `test_reversal_end_state_no_match_no_allocation_no_advance`, `test_reversal_makes_affected_bills_owe_again`, `test_other_advance_pays_bill_that_owes_again_after_reversal`, `test_advance_restored_from_reversed_payment_is_not_reapplied`, `test_other_advance_on_closed_tenancy_pays_bill_that_owes_again_after_reversal`, `test_unmatch_refused_while_net_allocations_not_zero`, `test_wrong_match_correction_appends_reversal_then_new_match`, `test_match_is_never_edited_or_repointed`, `test_other_advance_pays_bill_that_owes_again_after_correction`, `test_wrong_match_correction_is_audited`, `test_partial_writeoff_then_reversal_keeps_written_off_flag`, `test_reversal_after_rate_drop_leaves_bills_as_adjusted_not_original`, `test_standalone_reversal_is_audited`, `test_correction_does_not_call_ensure_bills_through`, `test_wrong_match_correction_is_atomic_under_lock_order` (R2), `test_wrong_match_correction_atomic_no_partial_writes` (R2), `test_concurrent_generation_and_reversal_serialize` (names `TEST_DATABASE_URL`; skips locally). Proved by: the functions themselves.

### Implementation for User Story 4

- [ ] T021 [US4] Implement `complete_reversal_plan(payment, allocations, movements, match)` in `backend/src/billing/engine.py`: reverse each allocation via T014 (`created`), append `reversed` movements for the payment's whole remaining logged advance, append the reversal match row (plan D-10; `docs/05` §12.1; `docs/04` §8.12). Proved by: `tests/test_corrections.py::test_complete_reversal_bank_reversed_payment`, `tests/test_corrections.py::test_complete_reversal_confirmed_duplicate`, `tests/test_corrections.py::test_reversal_end_state_no_match_no_allocation_no_advance`, `tests/test_corrections.py::test_reversal_makes_affected_bills_owe_again`, `tests/test_corrections.py::test_partial_writeoff_then_reversal_keeps_written_off_flag`, `tests/test_corrections.py::test_reversal_after_rate_drop_leaves_bills_as_adjusted_not_original`.
- [ ] T022 [US4] Implement `correct_match_plan(payment, allocations, movements, match, new_tenancy)` in `backend/src/billing/engine.py`: reverse allocations (T014), clear advance, produce the reversal match row, the new match row, and the re-allocation plan (Samuel's ruling R2; `docs/05` §6.9, §12, §13). Proved by: `tests/test_corrections.py::test_wrong_match_correction_appends_reversal_then_new_match` and `tests/test_corrections.py::test_match_is_never_edited_or_repointed`.
- [ ] T023 [US4] Implement `complete_reversal(transaction_id, admin_id)` in `backend/src/billing/repository.py`: one transaction under the §6.9 lock order for T021, writing the audit entry; after reversing the payment's allocations, apply advance held on the tenancy's **other** payments to any bill that owes again (normal advance application via T011, oldest remainder first then oldest bill; advance restored from the reversed payment itself is never re-applied; a `closed` tenancy's own advance pays its own bills generated after closure, and no other tenancy takes it — Samuel's ruling S7); before commit run `reconcile` for every payment touched, rolling back and raising an integrity error on mismatch (plan D-10; contract §2; `docs/05` §7.2, §7.5, §12.1; `docs/04` §7.5). Proved by: `tests/test_corrections.py::test_standalone_reversal_is_audited`, `tests/test_corrections.py::test_correction_does_not_call_ensure_bills_through`, `tests/test_corrections.py::test_other_advance_pays_bill_that_owes_again_after_reversal`, `tests/test_corrections.py::test_advance_restored_from_reversed_payment_is_not_reapplied`, `tests/test_corrections.py::test_other_advance_on_closed_tenancy_pays_bill_that_owes_again_after_reversal`.
- [ ] T024 [US4] Implement `correct_match(transaction_id, new_tenancy_id, admin_id)` and the unmatch guard in `backend/src/billing/repository.py`: refuse to unmatch while the signed net allocations are non-zero; run reverse-allocation, unmatch, new match and re-allocation in one transaction; after reversing the old tenancy's allocations, apply advance held on the old tenancy's **other** payments to any bill that owes again (same rule as T023, including a `closed` tenancy whose own advance pays its own bills generated after closure — Samuel's ruling S7); write the audit entry in the same transaction; before commit run `reconcile` for every payment touched, rolling back and raising an integrity error on mismatch (Samuel's ruling R2; plan D-11; contract §2; `docs/05` §7.2, §7.5; `docs/04` §8.12, §7.5). Proved by: `tests/test_corrections.py::test_unmatch_refused_while_net_allocations_not_zero`, `tests/test_corrections.py::test_other_advance_pays_bill_that_owes_again_after_correction`, `tests/test_corrections.py::test_wrong_match_correction_is_audited`.
- [ ] T025 [US4] Prove R2 atomicity and the lock order: assert a forced failure mid-correction writes nothing and leaves the prior match/allocations intact, and add the PostgreSQL-only serialized-lock test gated on `TEST_DATABASE_URL` (Samuel's ruling R2; plan D-12; `docs/05` §6.9). Proved by: `tests/test_corrections.py::test_wrong_match_correction_is_atomic_under_lock_order`, `tests/test_corrections.py::test_wrong_match_correction_atomic_no_partial_writes`, `tests/test_corrections.py::test_concurrent_generation_and_reversal_serialize`.

**Checkpoint**: US1–US4 independently functional.

---

## Phase 7: User Story 5 - Derived status and billing summaries (Priority: P5)

**Goal**: Derived bill status + `was_written_off`, tenancy billing state, and the read-only summary/report views.

**Independent Test**: Produce each status (including final amount 0 with/without write-off), assert the two-amount outstanding with the docs' numbers, and prove a view request mutates nothing.

**Requirements**: FR-043–FR-055.

### Tests for User Story 5 (write FIRST, ensure they FAIL) ⚠️

- [ ] T026 [P] [US5] Write `tests/test_status_summaries.py`: `test_bill_status_unpaid_partial_paid`, `test_bill_status_written_off_takes_precedence`, `test_bill_status_no_charge`, `test_was_written_off_flag`, `test_part_paid_bill_with_rest_written_off_reads_paid_and_flagged`, `test_current_month_status_from_running_month_bill`, `test_outstanding_two_amounts_22_rooms_example`, `test_running_month_counts_as_outstanding_no_due_label`, `test_room_with_earlier_month_owing_is_not_fully_paid`, `test_no_charge_bill_does_not_block_fully_paid`, `test_overall_status_owing_settled_in_advance`, `test_net_position_is_outstanding_minus_advance`, `test_fully_paid_ratio_denominator_active_tenancy_rooms`, `test_no_charge_month_shows_no_charge_message`, `test_no_charge_month_judged_from_standard_amount`, `test_tenant_billing_summary_fields`, `test_property_summary_two_amounts_and_status_per_room`, `test_property_summary_has_no_due_wording`, `test_tenant_facing_property_totals_count_active_tenancies_only`, `test_property_billing_summary_includes_adjustment_notices`, `test_payment_history_shows_allocated_months`, `test_admin_report_freshness_note_and_month_flagging`, `test_freshness_does_not_flag_running_month`, `test_freshness_ignores_manual_entries`, `test_closed_tenancy_outstanding_separate_admin_only`, `test_closed_tenancy_list_shows_room_names_contacts_balance_months`, `test_views_never_change_payments_or_allocations`, `test_no_stored_derived_state_columns`. Proved by: the functions themselves.

### Implementation for User Story 5

- [ ] T027 [US5] Implement `bill_status(final_amount, net_allocated, has_write_off)` and `was_written_off(adjustments)` in `backend/src/billing/status.py` (pure): final-0 checks first (Written off / No charge), then Unpaid / Partial / Paid over the signed net of `docs/04` §7.1; supply the flag (plan D-13; `docs/05` §8.1–8.4; `docs/04` §7.1). Proved by: `tests/test_status_summaries.py::test_bill_status_unpaid_partial_paid`, `tests/test_status_summaries.py::test_bill_status_written_off_takes_precedence`, `tests/test_status_summaries.py::test_bill_status_no_charge`, `tests/test_status_summaries.py::test_was_written_off_flag`, `tests/test_status_summaries.py::test_part_paid_bill_with_rest_written_off_reads_paid_and_flagged`.
- [ ] T028 [US5] Implement `tenancy_state(bills, advances)` in `backend/src/billing/status.py` (pure): totals, two-amount outstanding (earlier months / this month), advance, net position, current-month and overall status; handle the no-charge month and the fully-paid ratio rules (plan D-13; `docs/05` §9; `docs/04` §7.2–7.6; ADR-027). Proved by: `tests/test_status_summaries.py::test_outstanding_two_amounts_22_rooms_example`, `tests/test_status_summaries.py::test_running_month_counts_as_outstanding_no_due_label`, `tests/test_status_summaries.py::test_room_with_earlier_month_owing_is_not_fully_paid`, `tests/test_status_summaries.py::test_no_charge_bill_does_not_block_fully_paid`, `tests/test_status_summaries.py::test_overall_status_owing_settled_in_advance`, `tests/test_status_summaries.py::test_net_position_is_outstanding_minus_advance`, `tests/test_status_summaries.py::test_fully_paid_ratio_denominator_active_tenancy_rooms`, `tests/test_status_summaries.py::test_no_charge_month_shows_no_charge_message`, `tests/test_status_summaries.py::test_no_charge_month_judged_from_standard_amount`, `tests/test_status_summaries.py::test_current_month_status_from_running_month_bill`.
- [ ] T029 [US5] Implement `tenant_billing_summary`, `property_billing_summary` and `payment_history` in `backend/src/billing/views.py` (read-only), including adjustment notices, two-amount amounts and status per room with no due wording, active-tenancy-only tenant-facing totals, and per-month allocated amounts, all org-scoped (plan D-14; contract §3; `docs/05` §14.1–14.3). Proved by: `tests/test_status_summaries.py::test_tenant_billing_summary_fields`, `tests/test_status_summaries.py::test_property_summary_two_amounts_and_status_per_room`, `tests/test_status_summaries.py::test_property_summary_has_no_due_wording`, `tests/test_status_summaries.py::test_tenant_facing_property_totals_count_active_tenancies_only`, `tests/test_status_summaries.py::test_property_billing_summary_includes_adjustment_notices`, `tests/test_status_summaries.py::test_payment_history_shows_allocated_months`.
- [ ] T030 [US5] Implement `admin_report_freshness` and `closed_tenancy_outstanding` in `backend/src/billing/views.py` (read-only, org-scoped): freshness from the latest `statement_end_date` among `confirmed`/`completed` import batches and the months ended after it, not flagging the running month and ignoring manual entries for the date; closed-tenancy total separate from active outstanding with the per-tenancy list of room, tenant names/contacts, balance and months (plan D-15; contract §3; `docs/05` §14.4, §14.5). Proved by: `tests/test_status_summaries.py::test_admin_report_freshness_note_and_month_flagging`, `tests/test_status_summaries.py::test_freshness_does_not_flag_running_month`, `tests/test_status_summaries.py::test_freshness_ignores_manual_entries`, `tests/test_status_summaries.py::test_closed_tenancy_outstanding_separate_admin_only`, `tests/test_status_summaries.py::test_closed_tenancy_list_shows_room_names_contacts_balance_months`.
- [ ] T031 [US5] Read-only guard and derived-state guard: ensure no view issues a write and assert no derived-state column exists; a view never changes a payment or an allocation (FR-054, Samuel's ruling F-03); the admin adapter operations call `ensure_bills_through` before the view runs (`docs/05` §5.1, §14.4) (plan D-14; spec FR-054, FR-055; `docs/04` §7). Proved by: `tests/test_status_summaries.py::test_views_never_change_payments_or_allocations` and `tests/test_status_summaries.py::test_no_stored_derived_state_columns`.

**Checkpoint**: US1–US5 independently functional.

---

## Phase 8: User Story 6 - Manual matching, idempotent reprocessing, and organization scoping (Priority: P6)

**Goal**: Manual matching, provider-payment bypass, and organization scoping across engine and views.

**Independent Test**: Manually match an unmatched payment and assert allocation; assert a provider payment creates no allocation; run with two organizations and assert no leakage.

**Requirements**: FR-056–FR-059.

### Tests for User Story 6 (write FIRST, ensure they FAIL) ⚠️

- [ ] T032 [P] [US6] Write `tests/test_manual_matching_scoping.py`: `test_manual_match_appends_match_and_allocates`, `test_manual_match_is_audited`, `test_second_active_match_refused`, `test_provider_payment_bypasses_matching`, `test_engine_scopes_all_queries_to_organization`, `test_views_scope_all_queries_to_organization`, `test_transaction_rows_are_never_updated_or_deleted`, `test_allocation_movement_adjustment_match_rows_never_updated_or_deleted`. Proved by: the functions themselves.

### Implementation for User Story 6

- [ ] T033 [US6] Implement `match_manually(transaction_id, tenancy_id, admin_id)` in `backend/src/billing/repository.py`: append the `transaction_match` row, audit it, then run the normal allocation path; a manual match to a closed tenancy is allowed, fills its outstanding bills oldest-first, and any remainder is advance that stays recorded (plan D-16; contract §2; `docs/05` §12, §13, §7.5; Samuel's ruling S6). Proved by: `tests/test_manual_matching_scoping.py::test_manual_match_appends_match_and_allocates`, `tests/test_manual_matching_scoping.py::test_manual_match_is_audited`, `tests/test_manual_matching_scoping.py::test_second_active_match_refused`.
- [ ] T034 [US6] Ensure utility provider payments bypass matching: matching/allocation must not run for `utility_bill_payment` transactions (contract §2; `docs/05` §13; `docs/04` §6.6, §8.3). Proved by: `tests/test_manual_matching_scoping.py::test_provider_payment_bypasses_matching`.
- [ ] T035 [US6] Enforce organization scoping in `repository.py` and `views.py`: every read and write filters `organization_id`, and `transaction` rows are never updated or deleted; allocation, advance-movement, adjustment and match rows are never updated or deleted (spec FR-057, FR-059; `docs/04` §8.9, §11.1). Proved by: `tests/test_manual_matching_scoping.py::test_engine_scopes_all_queries_to_organization`, `tests/test_manual_matching_scoping.py::test_views_scope_all_queries_to_organization`, `tests/test_manual_matching_scoping.py::test_transaction_rows_are_never_updated_or_deleted`, `tests/test_manual_matching_scoping.py::test_allocation_movement_adjustment_match_rows_never_updated_or_deleted`.

**Checkpoint**: All six stories independently functional.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Full-suite verification and quickstart validation

- [ ] T036 Run the full suite on in-memory SQLite from the repository root: `.venv/bin/python -m pytest tests -q` (AGENTS.md). Must be green across the six story files before the feature is considered done. Proved by: the full-suite run itself.
- [ ] T037 [P] Run the same full suite against PostgreSQL when a PG URL is configured (CI/deploy): `TEST_DATABASE_URL=postgresql+psycopg://... .venv/bin/python -m pytest tests -q`, which un-skips the concurrency tests (plan D-12; quickstart.md). Locally, with no PG URL, the PostgreSQL variants skip and do not fail. Proved by: `tests/test_corrections.py::test_concurrent_generation_and_reversal_serialize`, `tests/test_bill_generation.py::test_concurrent_generation_creates_one_bill_per_tenancy_month`, `tests/test_allocation_advance.py::test_concurrent_allocations_on_one_tenancy_never_overallocate`, and `tests/test_bill_adjustments.py::test_rate_change_and_allocation_serialize_under_lock_order`.
- [ ] T038 [P] Walk [quickstart.md](quickstart.md) validation scenarios 1–6 as a smoke pass and confirm each named test exists and passes. Proved by: the quickstart run itself.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Stories (Phases 3–8)**: All depend on Foundational. They are in dependency order (US1 → US2 → US3 → US4 → US5 → US6):
  - US2 uses the repository transaction boundary (T004) and is built on generation (US1).
  - US3 uses the R1 primitive (T014 in US2) for rate drops and reduced-bill corrections.
  - US4 uses the R1 primitive (T014) and the transaction/lock helper (T004).
  - US5 reads bills, allocations and adjustments written by US1–US4.
  - US6 uses the allocation path (US2) and adds manual matching and scoping.
- **Polish (Phase 9)**: Depends on all stories.

### Within Each User Story

- The test task is written and made to FAIL before the implementation tasks land (constitution Principle V).
- Implementation tasks that edit the same module file are sequential (not `[P]`); pure planning functions precede the repository write path.
- R1's implementation (T014, US2) is deliberately not later than its first use (US3 rate drops, US4 corrections); R2's proof (T025, US4) is inside the same story as its implementation.

### Parallel Opportunities

- Phase 1: T002 is a different file from T001.
- Phase 2: T003 and T004 are different files (`[P]`).
- Phases 3–8: each story's **single test file** task is a different file and can run in parallel with other stories' test files (`[P]`). Model/engine changes within a story share one file and run sequentially.

---

## Sequence check (no forward dependencies)

Every function a task calls is implemented in an earlier task or in the same story. Generation (US1) only creates bills; applying existing advance to newly created bills is added by T013 (US2), so no US1 task calls a US2 function.

- `business_month` / `month_starts_between` (T006, US1) are called by `expected_bill_months` (T007, US1).
- `expected_bill_months` / `resolve_standard_amount` (T007, US1) are called by `ensure_bills_through` (T008, US1).
- `order_payments` / `allocate` / `apply_advance` (T011, US2) are called by `allocate_for_tenancy` and the `confirm_import_batch` half of T013 (US2). T013 also **extends** `ensure_bills_through` (created by T008, US1) so that it applies existing advance via `apply_advance`; the link is US1-creates → US2-extends, never the reverse, so no task calls a later story's function.
- `reverse_allocation` (T014, US2) is called by `rate_change_plan` (T016, US3), reduced-bill handling (T017, US3), `complete_reversal_plan` (T021, US4) and `correct_match_plan` (T022, US4) — all later, none earlier.
- `write_off_plan` (T017, US3) is called by `record_write_off` (T019, US3).
- `move_in_write_off_plan` (T017, US3) is called by `record_move_in_write_off` (T019, US3).
- `apply_advance` (T011, US2) is also called by `complete_reversal` (T023, US4) and `correct_match` (T024, US4) to re-fill the bills that owe again after a reversal, including a `closed` tenancy's own bills generated after closure (Samuel's ruling S7) — an earlier story, not a later one.
- `reconcile` (T012, US2) is called by the write paths `allocate_for_tenancy` / `confirm_import_batch` (T013, US2), `confirm_rate_change` (T018, US3), `complete_reversal` (T023, US4) and `correct_match` (T024, US4) — earlier or same story.
- `bill_status` / `tenancy_state` (T027–T028, US5) are called by `views.py` (T029–T030, US5).
- `match_manually` (T033, US6) calls the allocation path from US2.

No task calls a function created in a later story.

---

## Coverage matrix — Step 3 items and Step 2 rulings

| Item (runbook) | Task(s) | Named test(s) |
|---|---|---|
| 1. `ensure_bills_through` + callers only; allocation and batch confirm call it inside their own transaction | T008, T009, T013 | `test_generation_is_not_reachable_from_tenant_read_path`, `test_admin_report_request_generates_missing_bills`, `test_admin_dashboard_load_generates_missing_bills`, `test_allocation_calls_ensure_bills_through_inside_its_transaction`, `test_allocation_failure_midway_writes_nothing`, `test_batch_confirm_locks_batch_and_rechecks_status`, `test_batch_confirm_calls_ensure_bills_through_inside_its_transaction`, `test_double_confirm_of_same_batch_allocates_once` |
| 2. business-timezone month | T006 | `test_business_timezone_month_boundary_around_midnight` |
| 3. move-in month billed in full by default; move-in bill write-off | T007, T008, T017 | `test_movein_month_billed_in_full_by_default`, `test_same_month_movein_and_moveout_billed_once_in_full`, `test_movein_bill_write_off_on_active_tenancy_zeroes_balance` |
| 4. late bill amount at month end; 00:00 1st = new month | T007 | `test_late_bill_uses_amount_in_force_at_month_end`, `test_rate_change_saved_at_month_start_belongs_to_new_month` |
| 5. `draft` tenancy billing | T007 | `test_draft_tenancy_receives_no_bill`, `test_draft_tenancy_never_billed` |
| 6. payment order (date/time, amount, id; null time) | T011 | `test_newest_first_input_is_reordered_oldest_first`, `test_identical_timestamps_tie_break_by_amount_then_id`, `test_payment_without_time_counts_as_business_midnight` |
| 6a. allocation worked numbers (§4.4, §6.7) | T011 | `test_payment_splits_across_three_bills_2000_2000_1000`, `test_overpayment_across_two_bills_leaves_1000_advance` |
| 7. July payment allocated to June shows both months | T029 | `test_payment_history_shows_allocated_months` |
| 8. allocation only to active-match tenancy; providers never settle | T013, T034 | `test_allocation_only_to_active_match_tenancy_bills`, `test_provider_payment_bypasses_matching` |
| 9. advance applied to new and existing bills; created/applied/reversed logged; identity skips unmatched; a closed tenancy's advance pays its own later bill (S7) | T011, T012, T013 | `test_payment_before_bill_held_as_advance_then_fills_bill`, `test_new_bill_generation_applies_existing_advance_oldest_first`, `test_advance_movement_written_atomically_with_allocation`, `test_reconciliation_skips_payment_unmatched_by_correction`, `test_closed_tenancy_advance_pays_bill_generated_after_closure` |
| 10. derived vs logged advance mismatch flagged, including on a write | T012, T013, T023, T024 | `test_advance_reconciliation_mismatch_is_flagged`, `test_reconciliation_mismatch_on_write_rolls_back_and_raises` |
| 11. re-processing allocates nothing new; manual-after-import allocated normally; late-matched payment fills only what is left | T013 | `test_reprocessing_payment_allocates_nothing_new`, `test_manual_source_payment_allocated_like_imported`, `test_payment_matched_later_with_earlier_date_fills_only_what_is_left` |
| 12. manual-entry payment like imported; org-scoping | T013, T035 | `test_manual_source_payment_allocated_like_imported`, `test_engine_scopes_all_queries_to_organization` |
| 13. derived bill status + `was_written_off`; final-0 first; part-paid rest written off reads paid and flagged | T027 | `test_bill_status_unpaid_partial_paid`, `test_bill_status_written_off_takes_precedence`, `test_bill_status_no_charge`, `test_was_written_off_flag`, `test_part_paid_bill_with_rest_written_off_reads_paid_and_flagged` |
| 14. No charge vs written off; no-charge month from standard amount | T027, T028 | `test_bill_status_no_charge`, `test_no_charge_month_judged_from_standard_amount` |
| 15. outstanding as two amounts; 22-room numbers; earlier-month owing blocks fully paid; net position | T028 | `test_outstanding_two_amounts_22_rooms_example`, `test_room_with_earlier_month_owing_is_not_fully_paid`, `test_net_position_is_outstanding_minus_advance` |
| 16. fully-paid ratio denominator; no-charge message; no-charge bill does not block fully paid; overall status | T028 | `test_fully_paid_ratio_denominator_active_tenancy_rooms`, `test_no_charge_month_shows_no_charge_message`, `test_no_charge_bill_does_not_block_fully_paid`, `test_overall_status_owing_settled_in_advance` |
| 17. property summary two amounts/status/no due wording; tenant-facing totals active only; closed-tenancy view/list; report note | T029, T030 | `test_property_billing_summary_includes_adjustment_notices`, `test_property_summary_two_amounts_and_status_per_room`, `test_property_summary_has_no_due_wording`, `test_tenant_facing_property_totals_count_active_tenancies_only`, `test_closed_tenancy_outstanding_separate_admin_only`, `test_closed_tenancy_list_shows_room_names_contacts_balance_months`, `test_admin_report_freshness_note_and_month_flagging`, `test_freshness_does_not_flag_running_month`, `test_freshness_ignores_manual_entries` |
| 18. rate change semantics (rise/drop/reverse order; business-tz month of save; persisted standard amount, reversals, movements, reconcile) | T016, T018 | `test_rate_rise_makes_paid_bill_part_paid`, `test_rate_rise_paid_by_advance`, `test_rate_drop_excess_becomes_advance_in_reverse_order`, `test_rate_drop_applies_advance_to_oldest_outstanding`, `test_rate_change_never_touches_past_months`, `test_rate_change_never_touches_closed_tenancy`, `test_rate_change_never_touches_write_off`, `test_rate_change_month_is_business_timezone_month_of_save_moment`, `test_rate_change_to_zero_makes_bills_no_charge_and_returns_payments_as_advance`, `test_rate_change_persists_new_standard_amount_for_following_months`, `test_confirm_rate_drop_persists_reversals_and_created_movements`, `test_confirm_rate_rise_applies_advance_and_persists_movements`, `test_confirm_rate_change_to_zero_persists_advance`, `test_rate_change_adjusts_unpaid_part_paid_and_paid_bills_together`, `test_rate_drop_part_paid_below_new_amount_adjusts_without_reversal`, `test_rate_rise_leaves_unpaid_bill_unpaid`, `test_rate_change_runs_in_one_transaction_and_failure_writes_nothing`, `test_rate_change_does_not_call_ensure_bills_through`, `test_rate_change_creates_audit_entry`, `test_rate_drop_tie_break_larger_amount_then_higher_id_taken_first`, `test_rate_drop_reverse_order_independent_of_allocation_order`, `test_rate_change_and_allocation_serialize_under_lock_order` |
| 19. whole-tenancy write-off only closed; move-in bill write-off on active or closed; note/admin/audit/flag; refuse whole-tenancy on active; refuse move-in with nothing outstanding | T017, T019 | `test_write_off_closed_tenancy_zeroes_balance`, `test_write_off_refused_on_active_tenancy`, `test_rate_change_never_touches_write_off`, `test_write_off_records_note_and_admin_identity`, `test_write_off_creates_audit_entry`, `test_write_off_sets_adjusted_flag`, `test_write_off_tenancy_writes_one_adjustment_per_owing_bill`, `test_write_off_has_auto_generated_note_and_optional_custom_note`, `test_movein_bill_write_off_on_active_tenancy_zeroes_balance`, `test_movein_bill_write_off_on_closed_tenancy`, `test_movein_bill_write_off_part_paid_reads_paid_and_flagged`, `test_movein_bill_write_off_refused_for_any_other_bill`, `test_movein_bill_write_off_refused_when_bill_missing_or_nothing_outstanding`, `test_movein_bill_write_off_has_no_chosen_amount`, `test_movein_bill_write_off_records_note_admin_and_audit_entry`, `test_whole_tenancy_write_off_after_movein_write_off_skips_zero_balance_bill` |
| 19a. a bill with a write-off adjustment is final; a rate change skips it, including an active tenancy's part-written-off move-in bill | T016, T018 | `test_rate_change_skips_bill_with_write_off_adjustment`, `test_rate_change_skips_part_written_off_movein_bill_on_active_tenancy`, `test_rate_change_never_touches_write_off` |
| 20. reduced bill frees excess via reversal + created; reversal after rate drop leaves adjusted bills | T016, T021 | `test_reduced_bill_below_allocated_frees_excess`, `test_reversal_after_rate_drop_leaves_bills_as_adjusted_not_original` |
| 21. unmatch refused while net allocations non-zero; match never edited; second match refused; ledger rows immutable | T022, T024, T033, T035 | `test_unmatch_refused_while_net_allocations_not_zero`, `test_match_is_never_edited_or_repointed`, `test_second_active_match_refused`, `test_allocation_movement_adjustment_match_rows_never_updated_or_deleted` |
| 22. complete reversal (see Step 2); other advance re-fills bills that owe again, including a closed tenancy's own later bill (S7) | T021, T023 | `test_complete_reversal_bank_reversed_payment`, `test_reversal_end_state_no_match_no_allocation_no_advance`, `test_other_advance_pays_bill_that_owes_again_after_reversal`, `test_advance_restored_from_reversed_payment_is_not_reapplied`, `test_other_advance_on_closed_tenancy_pays_bill_that_owes_again_after_reversal`, `test_partial_payment_then_write_off_of_the_rest_on_closed_tenancy` |
| **R1** reversal appends exactly one `created` | T014 | `test_any_allocation_reversal_appends_one_created_movement` |
| **R2** wrong-match correction one transaction, atomic, lock order; other advance re-fills; audited | T022, T024, T025 | `test_wrong_match_correction_appends_reversal_then_new_match`, `test_wrong_match_correction_is_atomic_under_lock_order`, `test_wrong_match_correction_atomic_no_partial_writes`, `test_other_advance_pays_bill_that_owes_again_after_correction`, `test_wrong_match_correction_is_audited` |
| **M1** bills run through the move-out month | T007, T008 | `test_m1_bills_through_moveout_month_then_stops` |
| **M3** write-off history shows the whole truth | T017 | `test_write_off_history_shows_original_written_off_final` |
| **F-03** views never change payments/allocations | T031 | `test_views_never_change_payments_or_allocations` |
| **S7** closed tenancy's advance stays recorded and pays its own later bills | T013, T023 | `test_closed_tenancy_advance_stays_recorded_and_not_taken`, `test_closed_tenancy_advance_pays_bill_generated_after_closure`, `test_other_advance_on_closed_tenancy_pays_bill_that_owes_again_after_reversal` |
| **S6** closed tenancy pays later | T013, T019, T033 | `test_manual_match_to_closed_tenancy_fills_its_outstanding_bills_oldest_first`, `test_payment_remainder_on_closed_tenancy_is_advance_that_stays_recorded`, `test_partial_payment_then_write_off_of_the_rest_on_closed_tenancy` |
| **S1** a move-in month is billed in full by default; no skip and no opt-out | T007, T008 | `test_movein_month_billed_in_full_by_default`, `test_same_month_movein_and_moveout_billed_once_in_full` |
| **S5** whole-tenancy write-off of a closed tenancy stays one action, one adjustment per bill with a balance | T017, T019 | `test_write_off_closed_tenancy_zeroes_balance`, `test_write_off_tenancy_writes_one_adjustment_per_owing_bill` |
| **S8** no billing override; move-in month bill write-off; rate-change finality | T007, T008, T015, T016, T017, T018, T019 | `test_movein_bill_write_off_on_active_tenancy_zeroes_balance`, `test_movein_bill_write_off_on_closed_tenancy`, `test_movein_bill_write_off_part_paid_reads_paid_and_flagged`, `test_movein_bill_write_off_refused_for_any_other_bill`, `test_movein_bill_write_off_refused_when_bill_missing_or_nothing_outstanding`, `test_movein_bill_write_off_has_no_chosen_amount`, `test_movein_bill_write_off_records_note_admin_and_audit_entry`, `test_whole_tenancy_write_off_after_movein_write_off_skips_zero_balance_bill`, `test_rate_change_skips_bill_with_write_off_adjustment`, `test_rate_change_skips_part_written_off_movein_bill_on_active_tenancy` |
| Roommate change has no effect | T013 | `test_roommate_change_has_no_effect` |
| Bank-reversed / confirmed duplicate complete reversal | T021, T023 | `test_complete_reversal_bank_reversed_payment`, `test_complete_reversal_confirmed_duplicate` |

## Coverage — docs/05 §16 scenarios and §15 edge cases

| `docs/05` §16 scenario | Test |
|---|---|
| ₦4,000 outstanding, ₦1,000 paid | `test_partial_payment_reduces_outstanding` |
| ₦4,000 outstanding, ₦5,000 paid | `test_overpayment_creates_advance` |
| Two bills, one payment covers both | `test_oldest_bill_filled_first` |
| Payment splits across three bills (§4.4) | `test_payment_splits_across_three_bills_2000_2000_1000` |
| Overpayment across two bills (§6.7) | `test_overpayment_across_two_bills_leaves_1000_advance` |
| Payment after month end | `test_payment_received_after_month_end_allocates_to_oldest` |
| Payment before bill exists | `test_payment_before_bill_held_as_advance_then_fills_bill` |
| New bill while advance exists | `test_payment_before_bill_held_as_advance_then_fills_bill`, `test_new_bill_generation_applies_existing_advance_oldest_first` |
| Bill adjusted downward | `test_rate_drop_excess_becomes_advance_in_reverse_order`, `test_rate_change_to_zero_makes_bills_no_charge_and_returns_payments_as_advance` |
| Bill adjusted upward | `test_rate_rise_makes_paid_bill_part_paid` |
| Duplicate payment imported | `test_reprocessing_payment_allocates_nothing_new`, `test_double_confirm_of_same_batch_allocates_once` |
| Payment reversed / confirmed duplicate | `test_complete_reversal_bank_reversed_payment`, `test_other_advance_pays_bill_that_owes_again_after_reversal`, `test_advance_restored_from_reversed_payment_is_not_reapplied`, `test_other_advance_on_closed_tenancy_pays_bill_that_owes_again_after_reversal` |
| Ledger vs derived balance mismatch flagged | `test_advance_reconciliation_mismatch_is_flagged`, `test_reconciliation_skips_payment_unmatched_by_correction`, `test_reconciliation_mismatch_on_write_rolls_back_and_raises` |
| Standard amount raised mid-month | `test_rate_rise_makes_paid_bill_part_paid`, `test_rate_change_month_is_business_timezone_month_of_save_moment`, `test_rate_change_persists_new_standard_amount_for_following_months`, `test_rate_rise_leaves_unpaid_bill_unpaid` |
| Standard amount lowered mid-month | `test_rate_drop_excess_becomes_advance_in_reverse_order`, `test_confirm_rate_drop_persists_reversals_and_created_movements`, `test_rate_drop_part_paid_below_new_amount_adjusts_without_reversal`, `test_rate_drop_tie_break_larger_amount_then_higher_id_taken_first` |
| Standard amount changed, closed tenancy | `test_rate_change_never_touches_closed_tenancy` |
| Move-in partial month | `test_movein_month_billed_in_full_by_default`, `test_movein_bill_write_off_on_active_tenancy_zeroes_balance` |
| Move-in and move-out in the same month | `test_same_month_movein_and_moveout_billed_once_in_full` |
| Move-out partial month | `test_moveout_partial_month_billed_in_full` |
| Debt written off | `test_write_off_closed_tenancy_zeroes_balance`, `test_write_off_records_note_and_admin_identity`, `test_write_off_creates_audit_entry`, `test_write_off_sets_adjusted_flag`, `test_write_off_tenancy_writes_one_adjustment_per_owing_bill`, `test_write_off_has_auto_generated_note_and_optional_custom_note` |
| Move-in bill written off | `test_movein_bill_write_off_on_active_tenancy_zeroes_balance`, `test_movein_bill_write_off_part_paid_reads_paid_and_flagged` |
| Rate change on a written-off bill | `test_rate_change_skips_bill_with_write_off_adjustment`, `test_rate_change_skips_part_written_off_movein_bill_on_active_tenancy` |
| Allocation / import confirm runs generation inside its transaction (§6.9) | `test_allocation_calls_ensure_bills_through_inside_its_transaction`, `test_allocation_failure_midway_writes_nothing`, `test_batch_confirm_locks_batch_and_rechecks_status`, `test_batch_confirm_calls_ensure_bills_through_inside_its_transaction` |
| Wrong-match correction; other advance re-fills the old tenancy (§12, §13) | `test_other_advance_pays_bill_that_owes_again_after_correction`, `test_wrong_match_correction_is_audited` |
| Closed tenancy pays later (§13, §7.5) | `test_manual_match_to_closed_tenancy_fills_its_outstanding_bills_oldest_first`, `test_payment_remainder_on_closed_tenancy_is_advance_that_stays_recorded` |

| `docs/05` §15 edge case | Test |
|---|---|
| Partial payments / overpayments | `test_partial_payment_reduces_outstanding`, `test_overpayment_creates_advance` |
| Multiple outstanding months / late payments | `test_oldest_bill_filled_first`, `test_payment_received_after_month_end_allocates_to_oldest` |
| Payments before bills / bills after advance | `test_payment_before_bill_held_as_advance_then_fills_bill`, `test_new_bill_generation_applies_existing_advance_oldest_first` |
| Duplicate / reversed payments | `test_reprocessing_payment_allocates_nothing_new`, `test_complete_reversal_bank_reversed_payment`, `test_other_advance_pays_bill_that_owes_again_after_reversal`, `test_advance_restored_from_reversed_payment_is_not_reapplied` |
| Adjusted bills after allocation | `test_reduced_bill_below_allocated_frees_excess`, `test_rate_change_to_zero_makes_bills_no_charge_and_returns_payments_as_advance`, `test_reversal_after_rate_drop_leaves_bills_as_adjusted_not_original` |
| Closure with outstanding / with advance | `test_write_off_closed_tenancy_zeroes_balance`, `test_closed_tenancy_advance_stays_recorded_and_not_taken`, `test_closed_tenancy_advance_pays_bill_generated_after_closure`, `test_other_advance_on_closed_tenancy_pays_bill_that_owes_again_after_reversal`, `test_partial_payment_then_write_off_of_the_rest_on_closed_tenancy` |
| Roommate changes | `test_roommate_change_has_no_effect` |
| Identical timestamps | `test_identical_timestamps_tie_break_by_amount_then_id` |
| Manual match after import | `test_manual_match_appends_match_and_allocates`, `test_second_active_match_refused`, `test_manual_match_to_closed_tenancy_fills_its_outstanding_bills_oldest_first`, `test_batch_confirm_locks_batch_and_rechecks_status`, `test_double_confirm_of_same_batch_allocates_once` |
| Payment matched later with an earlier date | `test_payment_matched_later_with_earlier_date_fills_only_what_is_left` |
| Move-in billed by default; move-in bill write-off | `test_movein_month_billed_in_full_by_default`, `test_movein_bill_write_off_on_active_tenancy_zeroes_balance`, `test_movein_bill_write_off_part_paid_reads_paid_and_flagged` |
| Move-out billed then written off | `test_write_off_closed_tenancy_zeroes_balance` |
| Rate raised/lowered mid-month (mixed paid states) | `test_rate_rise_makes_paid_bill_part_paid`, `test_rate_drop_excess_becomes_advance_in_reverse_order`, `test_rate_change_month_is_business_timezone_month_of_save_moment`, `test_rate_change_adjusts_unpaid_part_paid_and_paid_bills_together` |
| Write-off of closed tenancy balance | `test_write_off_closed_tenancy_zeroes_balance`, `test_write_off_records_note_and_admin_identity`, `test_write_off_creates_audit_entry`, `test_write_off_sets_adjusted_flag`, `test_write_off_tenancy_writes_one_adjustment_per_owing_bill`, `test_write_off_has_auto_generated_note_and_optional_custom_note` |
| Write-off of the move-in month bill (`§15` item 19) | `test_movein_bill_write_off_on_active_tenancy_zeroes_balance`, `test_movein_bill_write_off_refused_for_any_other_bill`, `test_movein_bill_write_off_has_no_chosen_amount` |
| Allocation runs generation in its own transaction | `test_allocation_calls_ensure_bills_through_inside_its_transaction`, `test_allocation_failure_midway_writes_nothing` |

---

## Notes

- `[P]` = different files, no dependency on an incomplete task. Within a story the engine/repository file is shared, so implementation tasks are not `[P]`.
- `[Story]` labels map each task to its user story for traceability.
- Tests for financial invariants MUST fail before implementation (constitution Principle V).
- Never point tests at `utility_billing_dev.db`; use the in-memory SQLite fixture (AGENTS.md).
- Run only the current task's tests while working; run the full suite at a story checkpoint.
- Do not commit (per the request).

---

## Gaps

Real open points only; each is decided or escalated.

- **(1) Advance-reconciliation timing and fail-closed on write** — decided by Samuel 2026-10-17 (S3): checked before commit on every write; no all-payments check in the MVP. Every repository write path (T013, T018, T023, T024) runs `reconcile` for each payment it touches before commit and, on a mismatch, rolls the transaction back and raises an integrity error (fail closed, the same idea as the import control totals). The operational cadence behind the write-time check is `docs/04` §13 item 6; grounded in `docs/05` §7.4 and `docs/04` §7.5.
- **(2) Duplicate payment** — detection is the import duplicate key (`docs/04` §10; `docs/05` §12.1); the engine proves idempotence only.
- **(3) Parked** — write-off of a chosen amount or selection; an admin-wide reconciliation check.
- **(4) Move-in write-off exists because bills are generated lazily** — bills are created on the first dashboard load, payment, import or report of the month, so a skip decision had to be recorded before the bill existed and the window usually closed first (Samuel's ruling S8). The move-in month bill is now billed in full and the admin writes off its whole outstanding balance; there is no skip decision.
- **Lock order** — lock order cannot be proven on SQLite; PostgreSQL-gated tests carry it.
