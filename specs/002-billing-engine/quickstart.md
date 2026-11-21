# Quickstart / Validation Guide: Tenant Billing Engine

**Feature**: `002-billing-engine` | **Date**: 2026-10-16 | **Spec**: [spec.md](spec.md)

A runnable validation guide proving the billing engine works end-to-end. Design details live in [research.md](research.md), [data-model.md](data-model.md) and [contracts/engine.md](contracts/engine.md); implementation code lives in the implementation phase (`tasks.md`), not here.

## Prerequisites

- Python 3.11+ with the existing project dependency set (`backend/pyproject.toml`); no extra libraries are required (`zoneinfo` is standard library).
- **Local/dev and tests use in-memory SQLite** (no server). Tests must never open the development database file (AGENTS.md).
- The schema from feature `001-database-schema` is already applied/created; this feature adds no schema change.
- PostgreSQL is only needed for the concurrency and engine-equivalence pass. Set `TEST_DATABASE_URL=postgresql+psycopg://...` to run the same suite there.

## Setup

```bash
# From the repository root, using the project virtual environment:
.venv/bin/python -m pytest tests -q                 # in-memory SQLite, full suite
.venv/bin/python -m pytest tests/test_bill_generation.py -q    # one story at a time

# PostgreSQL variant (CI/deploy, not local):
TEST_DATABASE_URL=postgresql+psycopg://... .venv/bin/python -m pytest tests -q
```

Tests are one file per user story: `tests/test_bill_generation.py` (US1), `test_allocation_advance.py` (US2), `test_bill_adjustments.py` (US3), `test_corrections.py` (US4), `test_status_summaries.py` (US5), `test_manual_matching_scoping.py` (US6).

## Validation scenarios

### 1. Lazy rolling generation (US1; SC-003, SC-004)
- An active tenancy with no bills → generation creates one bill for the month; vacant rooms get none; a second call creates no duplicate (`docs/05` §5.1).
- A tenancy moving in in March with `end_date` 20 June, untouched until a September generation → March–June bills (June in full), no July/August/September bill (Samuel's ruling M1).
- Move-in month billed in full by default; its whole outstanding balance can be written off by the admin. Move-out partial month billed in full (`docs/05` §5.3, §5.4). A `draft` tenancy is never billed (`docs/05` §5.1).
- An admin dashboard load generates missing bills before the dashboard view runs (`docs/05` §5.1, §14.4).
- A standard-amount change at 00:00 on the 1st → the previous month keeps the old amount, the new month takes the new amount (`docs/05` §5.2).
- Month boundaries around 23:59/00:00 in `Africa/Lagos` and a second timezone (`docs/03` §10.4).

### 2. Allocation and advance (US2; SC-001, SC-002, SC-008)
- ₦4,000 bill + ₦1,000 payment → ₦3,000 remaining; ₦4,000 + ₦5,000 → paid + ₦1,000 advance (`docs/05` §6.5, §6.6).
- Oldest-first fill; newest-first input reordered; identical timestamps tie-broken by amount then id; no-time payment = 00:00 (`docs/05` §6.2, §6.7, §6.8).
- Payment before bill held as advance, then fills the bill on generation (`docs/05` §7.3).
- `derived_unallocated == logged_advance` for every matched payment; a hand-broken ledger is flagged (`docs/05` §7.4; `docs/04` §7.5).
- Any allocation reversal appends exactly one `created` movement (Samuel's ruling R1).

### 3. Adjustments (US3; SC-005, SC-006)
- Rate rise: a fully-paid ₦4,000 bill becomes billed ₦5,000, paid ₦4,000 (`docs/05` §5.3).
- Rate drop: the excess is reversed from the payments in the reverse §6.2 order into advance, then applied oldest-first; past months and closed tenancies untouched (`docs/05` §5.3, §11.2).
- Write-off of a closed tenancy: one action records one `write_off` adjustment for every bill with a balance; standard ₦4,000, paid ₦1,000, written off ₦3,000 → final ₦1,000; history shows original, written-off and final amounts (Samuel's rulings M3, S5; `docs/05` §8.4, §11.1).
- The whole-tenancy write-off on an active tenancy is refused (`docs/05` §5.3).
- Move-in month bill write-off, active tenancy: standard ₦4,000, move-in month unpaid → one `write_off` adjustment, final 0, the bill reads Written off. Part-paid move-in bill: ₦1,000 paid, write-off of the rest → final ₦1,000, the bill reads Paid and is flagged (Samuel's ruling S8; `docs/05` §5.3, §8.4). Refused with nothing written when the bill does not exist or has nothing outstanding.
- Rate change: a bill with a write-off adjustment is final and is never adjusted; the whole-tenancy write-off after a move-in write-off skips the now-zero bill (`docs/05` §5.3).

### 4. Corrections and reversals (US4; SC-007, SC-010)
- Complete reversal: allocations undone, advance cleared, payment unmatched, every affected bill owes again (`docs/05` §12.1).
- Wrong-match correction is one transaction under the §6.9 lock order; a forced failure writes nothing (Samuel's ruling R2; `docs/04` §8.12).
- Unmatch is refused while net allocations are non-zero; a match is never edited (`docs/05` §12, §13).
- A manual match to a closed tenancy fills its outstanding bills oldest first; any remainder is advance that stays recorded (`docs/05` §13, §7.5; Samuel's ruling S6).
- The serialized-lock assertion names `TEST_DATABASE_URL` and skips locally (PostgreSQL only).

### 5. Status and summaries (US5; SC-009)
- Status for unpaid/partial/paid, and the final-0 rules (Written off vs No charge) with the flag (`docs/05` §8.1–8.4).
- 22 rooms at ₦4,000 on 1 August → ₦8,000 from earlier months, ₦88,000 this month; fully-paid ratio denominator counts active-tenancy rooms; no-charge month shows "No charge this month" (`docs/05` §9).
- Payment history shows received and allocated months (`docs/05` §14.3); freshness data and closed-tenancy view behave per `docs/05` §14.4–14.5.
- A view request changes no payment or allocation (spec FR-054).

### 6. Manual matching and scoping (US6)
- Manual match appends a match row and allocates by the normal rules; utility provider payments bypass (`docs/05` §13).
- Re-processing a processed payment allocates nothing new (`docs/05` §6.1, §6.4).
- Two organizations never cross-scope (`docs/04` §8.9).

## Expected outcome

All scenarios green on in-memory SQLite locally, with PostgreSQL-only concurrency assertions skipping without `TEST_DATABASE_URL` and running in CI. This satisfies spec success criteria SC-001..SC-012 and the constitution's test-first financial-logic requirement (Principle V).
