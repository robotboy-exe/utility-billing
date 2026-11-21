# Feature Specification: Tenant Billing Engine

**Feature Branch**: `002-billing-engine`

**Created**: 2026-10-16

**Status**: Draft

**Input**: User description: "Build the tenant billing engine defined in docs/05-billing-engine.md: lazy rolling bill generation, chronological payment allocation, advance credit and its append-only movement ledger, derived bill and tenancy status, bill adjustments (rate change, write-off), corrections and reversals including wrong-match correction, and the billing summary views. Out of scope per docs/05 sections 1 and 2: utility provider payments, statement or PDF parsing, tenant portal visibility rules, authentication and authorization, frontend and API implementation. Everything must follow docs/05 and the table definitions in docs/04, plus the rulings in the runbook. Do not add requirements that are not in those docs or rulings. Where the docs are silent or conflict, mark the point NEEDS CLARIFICATION instead of inventing an answer."

## Overview

This feature delivers the tenant billing engine: the deterministic module that turns matched tenant payments into settled monthly bills, derives every billing balance and status, records advance credit in an append-only movement ledger, applies audited bill adjustments, and performs controlled corrections and reversals. It is the **Tenant Payment Ledger** only; utility provider payments are a separate ledger and never settle tenant bills (`docs/05` §1, §13; ADR-017).

`docs/05-billing-engine.md` is the source of intent and `docs/04-database.md` is the table contract. This specification states *what the engine must do* and cites `docs/05` (and `docs/04` where a table or derived rule is involved) by section rather than restating algorithms or columns. Where a point is settled by one of the runbook rulings it is cited as **Samuel's ruling `<id>`** and the ruling overrides any disagreeing prose.

The engine builds on the existing persisted schema (`transaction` is fully immutable and carries no tenancy or matching columns; matches live in the append-only `transaction_match` table; `monthly_bill`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change`, `billing_config`, and `organization` already exist). This feature adds no schema change; it reads and writes those tables through the billing engine and the reporting queries, and the engine reads and writes no `billing_override` table (there is no per-tenancy, per-month billing override).

## Principles

The engine follows the three billing ground rules of `docs/05` §3.6, which constrain every requirement below:

1. Bills, payments and advance credit each belong to one tenancy and are reconciled against that tenancy only. A payment of one tenancy never affects a bill of another.
2. Advance credit exists to pay the bills of the tenancy that owns it, whether that tenancy is active or closed.
3. Every bill that has an amount due is to be paid and reconciled unless the admin explicitly writes it off.

## Clarifications

### Session 2026-10-16

- Q: Does a tenancy in `draft` status receive bills? → A: No. Bills are generated for active and closed tenancies, and (per Samuel's ruling M1) backfilled for months inside a tenancy's occupied range through its move-out month. A `draft` tenancy is neither active nor closed, so it receives no bill (`docs/05` §5.1; `docs/04` §6.3 `tenancy_status`).
- Q: Which component builds the admin report freshness note? → A: The engine supplies the data (the latest `statement_end_date` among `confirmed`/`completed` import batches and which months ended after it) and the reporting layer formats the note (plan D-15) (`docs/05` §14.4).
- Q: When must the advance reconciliation invariant be checked? → A: The engine must be able to compute the invariant (derived unallocated vs. logged advance) and flag a mismatch as an integrity error; the check runs before commit on every write path that changes a payment's allocations or advance movements, with no all-payments check in the MVP (Samuel's ruling S3; `docs/05` §7.4; `docs/04` §7.5). The operational cadence beyond that is `docs/04` §13 item 6.

## User Scenarios & Testing *(mandatory)*

The user stories below are independent, testable slices in dependency order: generation (US1) precedes allocation and advance (US2); adjustments (US3) and corrections (US4) build on allocation; derived status and summaries (US5) read what the earlier stories write; manual matching and scoping (US6) complete the engine. No story depends on a later story.

### User Story 1 - Lazy rolling bill generation and month timing (Priority: P1)

Whenever an admin action that needs current bills runs (dashboard load, payment allocation, import batch confirm, admin report request), the engine creates any missing monthly bills for active and closed tenancies, for every month up to and including the current business-timezone month. Generation itself only creates bills; applying existing advance credit to newly generated bills is part of allocation (US2, FR-017). It never bills vacant rooms, never duplicates a bill, never bills a month after a tenancy's move-out month, and a bill generated late for an already-ended month uses the standard amount that was in force at the end of that month.

**Why this priority**: Every other behaviour needs bills to exist, and lazy generation is the project's replacement for a scheduled job on free hosting (ADR-022). It is the first dependency of the engine.

**Independent Test**: With a controllable clock and one provisioned organization, call the generation function and assert the exact set of bills it creates for a fresh organization, for repeated calls (idempotence), for a closed tenancy with a move-out date months earlier, for a move-in month (billed in full, its whole outstanding balance then write-offable by the admin), and for a rate change saved at a month boundary.

**Acceptance Scenarios**:

1. **Given** an active tenancy and no bills, **When** generation runs for a month, **Then** exactly one bill exists for that tenancy-month and vacant rooms have none (`docs/05` §5.1).
2. **Given** generation has already run for a month, **When** it runs again for the same month, **Then** no additional bill is created (`docs/05` §5.1; ADR-022).
3. **Given** a tenancy that moved in in March and has an `end_date` of 20 June, and no admin action between then and September, **When** generation runs in September, **Then** bills exist for March, April, May and June only — June billed in full — and no July, August or September bill exists (Samuel's ruling M1; `docs/05` §5.1).
4. **Given** a tenancy whose move-in month is a partial month, **When** generation runs for that month, **Then** the bill is created at the full standard amount by default (`docs/05` §5.3, §5.4, §15); **When** the admin writes off the bill's whole outstanding balance, **Then** it is one `write_off` adjustment on that bill and the balance is zero (`docs/05` §5.3, §5.4).
5. **Given** a tenancy whose move-out month is a partial month, **When** generation runs for that month, **Then** the bill is created in full, and the admin can write it off after closure with the whole-tenancy write-off (`docs/05` §5.3, §5.4).
6. **Given** a standard-amount change saved exactly at 00:00 on the 1st of a month, **When** a bill is generated late for the previous month and for the new month, **Then** the previous month takes the amount in force at the end of that previous month and the new month takes the new amount (`docs/05` §5.2; `docs/04` §6.4 `standard_amount_change`).
7. **Given** a tenancy in `draft` status, **When** generation runs, **Then** no bill is created for it (`docs/05` §5.1).
8. **Given** an organization with a different IANA business timezone, **When** generation runs around a month boundary at 23:59 and 00:00, **Then** the month passed to generation is the business-timezone month (`docs/03` §10.4; ADR-028).

---

### User Story 2 - Chronological payment allocation and advance credit (Priority: P2)

For each tenancy, the engine processes its matched tenant payments oldest-first and fills the tenancy's outstanding bills from oldest billing month to newest; any remainder becomes advance credit linked to the original payment. Advance credit is derived, and every advance event is written to the append-only advance movement ledger in the same transaction as the allocation that caused it. Restoring advance after an allocation is reversed is recorded as a new `created` movement, never as `reversed`.

**Why this priority**: Allocation is the core financial behaviour and feeds adjustments and corrections. Advance logging must exist before rate changes and corrections, which depend on it (`docs/05` §6, §7).

**Independent Test**: With one tenancy, seed bills and matched payments (including oldest-first, newest-first input, identical timestamps, overpayment, and payment-before-bill), run allocation and assert allocations, advance balance, the movement ledger, and the reconciliation identity.

**Acceptance Scenarios**:

1. **Given** a ₦4,000 bill and a ₦1,000 payment, **When** allocation runs, **Then** the bill has ₦1,000 allocated, ₦3,000 remains, and status is partially paid (`docs/05` §6.5, §16).
2. **Given** a ₦4,000 bill and a ₦5,000 payment, **When** allocation runs, **Then** the bill is paid and the tenancy holds ₦1,000 advance (`docs/05` §6.6, §16; §17 rule 5).
3. **Given** a June and a July bill and a ₦4,000 payment received on 15 July, **When** allocation runs, **Then** June is filled first and July is unpaid; payment history shows received month July and allocated month June (`docs/05` §6.8, §3.2, §14.3).
4. **Given** a payment received before any bill exists, **When** allocation runs, **Then** the whole amount is held as advance; **When** a bill is later generated, **Then** the advance fills it automatically (`docs/05` §7.3, §16).
5. **Given** two payments with identical date/time and different amounts, **When** allocation runs, **Then** the smaller amount is processed first, and if still tied, the lower internal identifier (`docs/05` §6.2).
6. **Given** a statement listing rows newest-first, **When** allocation runs, **Then** payments are reordered oldest-first with no reliance on stored row order or import sequence (`docs/05` §6.2).
7. **Given** a payment with no time of day, **When** it is ordered, **Then** it counts as 00:00 in the organization's business timezone (`docs/05` §6.2).
8. **Given** a payment whose active match is a tenancy, **When** allocation runs, **Then** its allocations attach only to that tenancy's bills; a utility provider payment never settles a tenant bill (`docs/05` §13, §17 rule 12; `docs/04` §8.12).
9. **Given** a payment that already has allocations, **When** the engine processes it again, **Then** no new allocation is created and the sum of signed allocations never exceeds the payment amount (`docs/05` §6.1, §6.4; `docs/04` §8.1).
10. **Given** a manually entered payment (`source` manual), **When** it is matched, **Then** it is allocated by the same rules as an imported payment (`docs/05` §13, §14.4; `docs/06` §17.2).
11. **Given** an allocation reversal, **When** the engine records it, **Then** exactly one `created` advance movement is appended for the reversed amount and the reconciliation identity still holds (Samuel's ruling R1; `docs/05` §7.4, §12; `docs/04` §7.5).
12. **Given** a tenancy closed while holding advance, **When** it is inspected, **Then** the advance stays recorded on its original payment, still reconciles, is applied to that tenancy's own bills generated after closure by normal advance application (oldest first) with any remainder staying recorded, and no other tenancy's bill (including a later tenancy in the same room) takes it (Samuel's ruling S7; `docs/05` §7.2, §7.5, §17 rule 22).

---

### User Story 3 - Bill adjustments: rate change and write-off (Priority: P3)

When the admin changes the org-wide standard amount mid-month, every current-month bill of an active tenancy is set to the new amount by a recorded adjustment, paid or not, while past months and closed tenancies are untouched. A rise makes a paid bill part paid (advance may cover the difference); a drop returns the excess to the payments as advance and re-applies it. A write-off zeroes a closed tenancy's outstanding balance through one audited adjustment per bill with a balance, and the admin can also write off the whole outstanding balance of a tenancy's move-in month bill, on an active or a closed tenancy, through one audited adjustment on that bill.

**Why this priority**: Adjustments are the only permitted way a bill amount changes, and they depend on allocation and the advance ledger (a drop needs the R1 reversal-to-advance primitive).

**Independent Test**: With current-month bills in unpaid, part-paid and fully-paid states, apply a rate rise and a rate drop and assert the adjustments, allocations, advance movements and derived amounts, then write off a closed tenancy's balance and, separately, a tenancy's move-in month bill, and assert the results.

**Acceptance Scenarios**:

1. **Given** a current-month fully-paid bill of ₦4,000 and a rate rise to ₦5,000, **When** the admin saves the new amount, **Then** the bill is billed ₦5,000, paid ₦4,000, ₦1,000 still to pay, as a recorded adjustment (`docs/05` §5.3).
2. **Given** a current-month bill paid above a new lower amount, **When** the rate drops, **Then** a reversal allocation returns the excess to the payment as one `created` advance movement each, in the exact reverse of the payment order in §6.2 (latest date/time, then larger amount, then higher id), and the advance is then applied to the oldest outstanding bill, otherwise it waits for the next bill (`docs/05` §5.3, §11.2; Samuel's ruling R1).
3. **Given** a tenancy that closed last month, **When** a rate change is saved, **Then** its bills are not touched (`docs/05` §5.3, §17 rule 16; ADR-023).
4. **Given** past-month bills, **When** a rate change is saved, **Then** past months are never adjusted (`docs/05` §5.3).
5. **Given** a reduced bill whose new amount is below what is allocated, **When** the adjustment is recorded, **Then** the excess is freed by a reversal allocation plus one `created` movement (`docs/05` §11.2).
6. **Given** a closed tenancy with an outstanding balance, **When** the admin writes it off, **Then** one write-off action records one `write_off` adjustment for every bill with a balance, zeroing the whole outstanding balance, carrying the auto-generated public note with an optional custom note and the admin identity, creating one audit entry per adjustment and setting the adjusted flag on each affected bill, and no record is deleted (`docs/05` §5.3, §11.1, §17 rule 19; `docs/04` §6.5).
7. **Given** an active tenancy, **When** the whole-tenancy write-off is attempted, **Then** it is refused; only the move-in month bill write-off is available on an active tenancy (`docs/05` §5.3).
8. **Given** a bill with a write-off adjustment, **When** a rate change is saved, **Then** the bill is final and the rate change never touches it, including an active tenancy's part-written-off move-in bill (`docs/05` §5.3, §9).
9. **Given** an admin saving any adjustment, **Then** the stored record holds adjustment type, previous amount, new amount, timestamp, an auto-generated public note with optional custom note, and the admin identity (`docs/05` §11.1; `docs/04` §6.5).
10. **Given** any attempt to change a bill amount other than by rate change or write-off, **Then** it is rejected; there are no arbitrary per-room amount overrides (`docs/05` §5.3, §17 rule 15; `docs/04` §8.7).
11. **Given** a tenancy's move-in month bill with an outstanding balance, open or closed tenancy, **When** the admin writes it off, **Then** one `write_off` adjustment on that bill zeroes its whole outstanding balance (`docs/05` §5.3, §5.4).
12. **Given** a move-in month bill written off, **Then** `previous_amount_minor` is the final amount before and `new_amount_minor` is the net allocated amount, the adjusted flag is set and one audit entry is written; a bill with no balance was already Paid or No charge (`docs/05` §5.3, §8.4, §11.1).
13. **Given** the move-in write-off, **Then** only that one bill is adjusted, no amount is chosen, and no other bill of the tenancy can be written off this way; the whole-tenancy write-off remains closed-only (`docs/05` §5.3).
14. **Given** a move-in month bill that does not exist, or has nothing outstanding, **When** the move-in write-off is requested, **Then** it is refused with a clear message and nothing is written (Samuel's ruling S8; `docs/05` §5.3).
15. **Given** a move-in month bill already written off to nothing, **When** the whole-tenancy write-off runs after closure, **Then** it skips that bill because it has no balance (`docs/05` §5.3).

---

### User Story 4 - Corrections and reversals (Priority: P4)

The admin can reverse a bank-reversed payment or confirm a committed duplicate, which undoes the payment completely in one database transaction (allocations reversed, advance cleared, payment unmatched, affected bills owing again). A wrong match is corrected as one atomic operation under the allocation lock order: reverse allocations, clear advance, append the reversal match row, then append the new match when re-matching; if any part fails, nothing is written.

**Why this priority**: Corrections protect the integrity of the ledger and depend on allocation and advance logging. They must not partially apply.

**Independent Test**: Seed a payment matched to the wrong tenancy with allocations and advance, correct the match and re-match, and assert the exact end state and atomicity; separately complete-reverse a payment and assert bills owe again.

**Acceptance Scenarios**:

1. **Given** a committed payment, **When** the admin records a bank reversal or confirms a duplicate, **Then** its allocations are reversed (each returning its amount as advance via one `created` movement), its whole remaining advance is cleared by `reversed` movements, and it is unmatched (`docs/05` §12.1, §17 rule 21; `docs/04` §8.12).
2. **Given** a completed reversal, **Then** the end state is: no active match, no net allocations and no advance on the reversed payment; each affected bill owes again what it owed before the payment (as changed by any adjustment recorded since), and advance held on the tenancy's **other** payments is then applied by normal advance application (oldest remainder first, oldest bill first) to any bill that owes again, while advance restored from the reversed payment itself is not re-applied (`docs/05` §7.2, §7.5, §12.1).
3. **Given** a payment matched to the wrong tenancy that holds allocations, **When** the admin corrects the match, **Then** allocations are reversed, advance is cleared, the reversal match row is appended, and the new match is appended — all in one database transaction under the `docs/05` §6.9 lock order; a partial failure writes nothing (Samuel's ruling R2; `docs/04` §8.12).
4. **Given** a payment whose net allocations (signed sum) are not zero, **When** the admin tries to unmatch it, **Then** the unmatch is refused (`docs/05` §12, §13; `docs/04` §8.12).
5. **Given** a wrong match, **When** it is corrected, **Then** the match row is never edited or re-pointed; a reversal match row and a new match row are appended instead (`docs/05` §12, §13).
6. **Given** a stand-alone reversal that is not part of a re-match, **When** it is recorded, **Then** it is audited (`docs/05` §12).
7. **Given** a bill that was part written off and whose payment is later reversed, **When** status is derived again, **Then** the status follows the §8.4 formulas and the "was written off" flag stays true (`docs/05` §8.4).
8. **Given** any correction, **Then** no financial record is deleted or silently rewritten; corrections are appended (`docs/05` §3.4, §12, §17 rule 11).
9. **Given** a rate change or a correction/reversal, **Then** it uses the §6.9 lock order and does **not** call the generation function (`docs/05` §6.9; `docs/03` §5.2.1).

---

### User Story 5 - Derived status and billing summaries (Priority: P5)

The engine derives bill status (Unpaid, Partial, Paid, Written off, No charge), a "was written off" flag, tenancy billing state (outstanding as two amounts, advance, net position, current-month and overall status), and the reporting views the docs require: tenant billing summary, property billing summary with adjustment notices, payment history, the admin report freshness data, and the admin-only closed-tenancy outstanding total with a per-tenancy list. All views are read-only.

**Why this priority**: Status and reports are how the billing state is consumed; they read records produced by the earlier stories, so they come after them.

**Independent Test**: Build bills and payments that produce each status (including a final amount of 0 with and without a write-off), then assert statuses, the two-amount outstanding figures with the docs' worked numbers, the fully-paid ratio in normal and no-charge months, and that a view request mutates nothing.

**Acceptance Scenarios**:

1. **Given** a bill with a final amount above 0, **When** status is derived, **Then** net allocated = 0 is Unpaid, 0 < net allocated < final is Partial, and net allocated ≥ final is Paid (`docs/05` §8.1–8.3; `docs/04` §7.1).
2. **Given** a bill whose final amount is 0 with a write-off adjustment, **Then** it reads Written off; with final amount 0 and no write-off, **Then** it reads No charge; the final-amount-0 checks come first (`docs/05` §8.4; `docs/04` §7.1).
3. **Given** a part-paid bill whose unpaid part is written off, **Then** the final amount equals what was paid and the bill reads Paid, and the "was written off" flag is true (`docs/05` §8.4).
4. **Given** 22 rooms at ₦4,000 and a run on 1 August, **When** the outstanding is reported, **Then** it shows from earlier months ₦8,000 and this month ₦88,000, and the running month's bill counts from the day it is generated with no "not yet due" label (`docs/05` §9, §7.3, §14.1, §14.2; §17 rule 24).
5. **Given** a normal month, **Then** the fully-paid ratio denominator is the number of rooms with an active tenancy (vacant rooms excluded); in a no-charge month the fully-paid count and ratio are replaced by "No charge this month" (`docs/05` §9; `docs/03` §11.2; ADR-027).
6. **Given** a month whose standard amount is 0, **Then** it is judged no-charge from the standard amount, not from the bills, and money already allocated to that month's bills becomes advance (`docs/05` §9).
7. **Given** the property billing summary, **Then** it includes the bill adjustment notices and applies visibility rules server-side (`docs/05` §14.2; `docs/03` §9.2).
8. **Given** a payment, **Then** payment history shows received date, amount, matched tenancy, allocated month(s), amount per month, and any remaining unallocated amount (`docs/05` §14.3).
9. **Given** the admin report freshness data, **Then** it states "payments recorded up to <date>" using the latest `statement_end_date` among `confirmed`/`completed` import batches, flags months that ended after that date but not the running month, and notes that manual entries are not covered by the date (`docs/05` §14.4).
10. **Given** a closed tenancy with an outstanding balance not written off, **Then** the admin dashboard shows its own total, separate from and never added into active-tenancy outstanding, with a per-tenancy list of room, tenants' names and contact details, balance and months covered; tenants never see it (`docs/05` §14.5; `docs/03` §9.2).
11. **Given** any summary or list view, **When** it is requested, **Then** it changes no payment and no allocation (`docs/05` §14; read-only views).
12. **Given** any derived value, **Then** it is computed from authoritative records and never stored as an independently mutable copy (`docs/04` §7; constitution Database & Schema).

---

### User Story 6 - Manual matching, idempotent reprocessing, and organization scoping (Priority: P6)

Unmatched tenant payments can be matched manually, which appends a match row; after matching, the engine allocates by the normal rules. Re-processing a payment that has already been processed allocates nothing new. Every query the engine issues is scoped by `organization_id`.

**Why this priority**: Manual matching is a fallback around automatic alias matching; scoping is a cross-cutting safety requirement. Both depend on allocation.

**Independent Test**: Match an unmatched payment manually and assert allocation follows; run the engine twice over the same payment and assert no new allocations; run the engine with two organizations and assert records never cross.

**Acceptance Scenarios**:

1. **Given** an unmatched tenant payment, **When** the admin matches it manually, **Then** a `transaction_match` row is appended, the action is audited, and the engine allocates by the normal chronological rules (`docs/05` §13, §12).
2. **Given** a payment already processed, **When** the engine runs again, **Then** no new allocation is created (`docs/05` §6.1, §6.4).
3. **Given** two organizations, **When** the engine and its reports run, **Then** every read and write is scoped to one `organization_id` and no record from another organization is visible or affected (`docs/04` §8.9; constitution Database & Schema).
4. **Given** a utility provider payment, **When** matching runs, **Then** it bypasses tenancy matching and creates no allocation (`docs/05` §13, §17 rule 12; `docs/04` §6.6).

---

### Edge Cases

- Partial payments, overpayments, multiple outstanding months, payments before bills exist, bills generated after advance exists, and late payments covering older months (`docs/05` §15 items 1–6).
- Duplicate payments, bank-reversed payments, and adjusted bills after allocation (`docs/05` §15 items 7–9).
- Tenancy closure with an outstanding balance and with advance credit (`docs/05` §15 items 10–11; §7.5).
- Roommate changes within a tenancy (add, remove, replace) change no bill, payment, allocation or advance (`docs/05` §5.5, §15 item 12; §17 rule 23).
- Multiple payments with identical timestamps (`docs/05` §15 item 13; §6.2).
- Payments matched manually after the initial import (`docs/05` §15 item 14).
- Move-in partial month billed in full by default, its whole outstanding balance write-offable by the admin; move-out partial month billed in full, then written off after closure (`docs/05` §15 items 15–16; §5.3, §5.4).
- Standard amount raised or lowered mid-month with some current-month bills fully paid, some part paid and some unpaid (`docs/05` §15 item 17).
- Write-off of a tenancy's move-in month bill (`docs/05` §15 item 19; §5.3).
- Advance reconciliation mismatch between the derived balance and the logged ledger is flagged as an integrity error (`docs/05` §7.4; `docs/04` §7.5).

## Requirements *(mandatory)*

### Functional Requirements

Bills are generated and timed (US1).

- **FR-001**: The engine MUST expose one generation entry point `ensure_bills_through(organization_id, month)` that creates any missing monthly bill for each active or closed tenancy within its billing range for each month up to and including `month`, with no background scheduler (`docs/05` §5.1; `docs/03` §5.2.1; ADR-022).
- **FR-002**: Only the admin dashboard load, payment allocation, import batch confirm, and admin report requests MAY call generation; tenant-session requests, including the tenant portal, MUST NOT (`docs/05` §5.1; `docs/03` §5.2.1; ADR-022).
- **FR-003**: `month` and every calendar-month boundary MUST be computed in the organization's IANA business timezone, default `Africa/Lagos`, with instants stored in UTC (`docs/03` §10.4; ADR-028; `docs/04` §6.2).
- **FR-004**: A tenancy MUST be billed for every month from move-in through the month of its `end_date` inclusive, even when generation runs months later; no bill may be created for a month after the `end_date` month (Samuel's ruling M1; `docs/05` §5.1).
- **FR-005**: A move-in month MUST be billed in full by default, with no skip decision and no opt-out at generation; the admin MAY write off its whole outstanding balance (FR-060). A move-out partial month MUST be billed in full by default and MAY be written off after closure with the whole-tenancy write-off (`docs/05` §5.3, §5.4, §15; §17 rule 18; Samuel's ruling S8).
- **FR-006**: A bill generated late for an already-ended month MUST take the standard amount in force at the end of that month, taken from `standard_amount_change`; the running month's bill MUST take the amount currently in force; a change saved exactly at 00:00 on the 1st belongs to the new month (`docs/05` §5.2; `docs/04` §6.4).
- **FR-007**: Generation MUST be idempotent and safe to run repeatedly and concurrently, creating no duplicate bill (`docs/05` §5.1, §10; `docs/03` §5.2.1; `docs/04` §8.6).
- **FR-008**: Vacant rooms MUST NOT receive bills, and a `draft` tenancy MUST NOT receive bills (`docs/05` §5.1).
- **FR-009**: There MUST be no per-tenancy, per-month billing override; generation MUST NOT take any override input and MUST NOT change any bill amount except through a recorded adjustment (`docs/05` §5.2, §5.4, §10).
- **FR-010**: Admin report requests MUST generate any missing bills as part of serving the report (`docs/05` §5.1, §14.4).

Payments are allocated and advance is tracked (US2).

- **FR-011**: Only matched tenant payments MUST enter the billing engine; a utility provider payment MUST NEVER settle a tenant bill (`docs/05` §13, §17 rule 12; `docs/06` §17.2; `docs/04` §8.3, §8.12).
- **FR-012**: For each tenancy, payments MUST be processed chronologically: date/time ascending, then smaller amount first, then internal transaction identifier; no stored row order or import sequence may be used, and a statement's newest-first order MUST be reordered oldest-first (`docs/05` §6.2; §17 rule 2).
- **FR-013**: A payment with no time of day MUST be ordered as 00:00 in the business timezone (`docs/05` §6.2).
- **FR-014**: Each payment's unallocated amount MUST be applied to the tenancy's bills with remaining due, from oldest billing month to newest, creating one allocation per bill filled, until the bill is paid or the payment is exhausted (`docs/05` §6.3, §6.4). A payment matched after other payments of the tenancy were already allocated is processed when it is matched: it fills only what is still open, and existing allocations are not re-ordered (Samuel's ruling S4; `docs/05` §6.2).
- **FR-015**: The sum of signed allocations for a payment MUST NEVER exceed the payment amount (`docs/05` §6.4; `docs/04` §8.1).
- **FR-016**: Any payment remainder after all fillable bills are filled MUST become advance credit linked to the original payment, recorded as one `created` advance movement (`docs/05` §6.4, §7.1; `docs/04` §7.4).
- **FR-017**: Advance credit MUST be applied automatically when a new monthly bill is generated, and after a rate change; when applied it uses the oldest unallocated payment remainder first, fills bills oldest-first, creates allocation records, reduces the remainder, and records each application as an `applied` advance movement (`docs/05` §7.2, §7.3).
- **FR-018**: Advance credit MUST remain linked to its original payment and its balance MUST always be derived from payment unallocated remainders, never stored as a mutable number (`docs/05` §4.6, §7.4; `docs/04` §7.4).
- **FR-019**: Every advance event MUST be written to the append-only advance movement ledger in the same database transaction as the allocation that caused it, with types `created`, `applied`, `reversed`; `reversed` MUST only ever undo a `created` movement, and restoring an applied allocation MUST be a new `created` movement (`docs/05` §7.4, §12; `docs/04` §4, §7.4, §7.5, §8.8).
- **FR-020**: Whenever any payment allocation is reversed, the engine MUST append exactly one `created` advance movement to that payment for the reversed amount and MUST NOT use a `reversed` movement for this (Samuel's ruling R1; `docs/05` §7.4, §12; `docs/04` §7.5).
- **FR-021**: For every matched tenant payment the derived unallocated remainder MUST equal the logged advance (sum of `created` minus `applied` minus `reversed`); any disagreement MUST be flagged as an integrity error (`docs/05` §7.4; `docs/04` §7.5). Every write path that changes a payment's allocations or advance movements MUST run this check for that payment before the transaction commits; on a mismatch the transaction rolls back and an integrity error is raised; there is no all-payments check in the MVP (Samuel's ruling S3; `docs/05` §7.4; `docs/04` §7.5).
- **FR-022**: Advance held by a closed tenancy MUST stay recorded and visible on its original payment and still reconcile, and MUST NOT be refunded, written off, moved, or taken by any other tenancy's bill (including a later tenancy in the same room); it MUST be applied by normal advance application to that tenancy's own bills generated after closure, oldest first, and any remainder MUST stay recorded (Samuel's ruling S7; `docs/05` §7.2, §7.5; §17 rule 22). A payment matched to a closed tenancy is still allocated to that tenancy's outstanding bills by the normal rules (`docs/05` §13; Samuel's ruling S6).
- **FR-023**: Re-processing a payment that has already been processed MUST allocate nothing new (`docs/05` §6.1, §6.4; `docs/04` §8.1).
- **FR-024**: A manually entered payment (`source` manual) MUST be handled like any imported payment once matched (`docs/05` §13, §14.4; `docs/06` §17.2).
- **FR-025**: Adding, removing or replacing a roommate within the same tenancy MUST change no bill, payment, allocation or advance credit (`docs/05` §5.5; §17 rule 23).
- **FR-026**: A payment allocation's bill MUST belong to the tenancy of the payment's active match; a transaction without an active match MUST have no net allocations and no net advance (`docs/05` §13; `docs/04` §8.12).

Bill adjustments are applied (US3).

- **FR-027**: A mid-month rate change MUST set every current-month bill of an active tenancy to the new amount by a recorded `rate_change` adjustment, whether the bill is unpaid, part paid or fully paid; it MUST never adjust past months or closed tenancies, and a bill that has a write-off adjustment is final and MUST be excluded from the rate change (`docs/05` §5.3, §9; §17 rule 16; ADR-010, ADR-023).
- **FR-028**: A rate change MUST take effect at the moment the admin saves it, and the current month is the business-timezone month of that moment (`docs/05` §5.3). The new standard amount applies to every following month (`docs/05` §5.3; §17 rule 16).
- **FR-029**: On a rate rise, a fully-paid bill MUST become part paid and the difference remain owed; if the tenancy holds advance, normal advance application MUST pay the difference (`docs/05` §5.3).
- **FR-030**: On a rate drop, if the new amount is below what is already paid on a bill, the excess MUST be removed by a reversal allocation and become advance linked to the payment it came from, with one `created` advance movement per reversal allocation; where the bill was paid by more than one payment the difference MUST be taken in the exact reverse of the §6.2 order (latest date/time, then larger amount, then higher id); the advance MUST then be applied to the tenancy's oldest outstanding bill, otherwise it waits for the next bill (`docs/05` §5.3, §11.2; Samuel's ruling R1).
- **FR-031**: If a reduced bill's new amount is lower than what is allocated, the excess MUST be freed by a reversal allocation plus one `created` movement (`docs/05` §11.2).
- **FR-032**: One write-off action MUST zero a closed tenancy's whole outstanding balance for every bill that still has a balance, through one recorded `write_off` adjustment per such bill; writing off a chosen amount or a chosen selection of bills is not supported in the MVP. The whole-tenancy write-off MUST be possible only for a closed tenancy, MUST carry the auto-generated public note with an optional custom note and the admin identity, MUST create one audit entry per adjustment, and MUST set each affected bill's adjusted flag; a whole-tenancy write-off on an active tenancy MUST be refused. A bill that has a write-off adjustment is final and a rate change MUST never touch it (`docs/05` §5.3, §5.4, §11.1; §17 rules 18, 19, 20; `docs/04` §6.5; ADR-025).
- **FR-033**: Every adjustment MUST store adjustment type, previous amount, new amount, timestamp, an auto-generated public note with an optional custom note, and the admin identity; a bill's final amount MUST change only through a recorded adjustment and any such change MUST be audited (`docs/05` §11.1; §17 rules 10, 17; `docs/04` §6.5, §8.7; constitution Database & Schema).
- **FR-034**: There MUST be no arbitrary per-room bill amount override; the only adjustable parameter is the org-wide standard monthly amount (`docs/05` §5.3; §17 rule 15; ADR-023).
- **FR-060**: The admin MAY write off the whole outstanding balance of a tenancy's move-in month bill, on an active or a closed tenancy, through one recorded `write_off` adjustment on that bill; no chosen amount is accepted, no other bill of the tenancy can be written off this way, and the whole-tenancy write-off stays closed-only. The adjustment MUST carry the auto-generated public note with an optional custom note and the admin identity, MUST record `previous_amount_minor` as the final amount before and `new_amount_minor` as the net allocated amount, MUST create one audit entry, and MUST set the bill's adjusted flag; the derived status then follows §8.4. The action MUST be refused, writing nothing, when the move-in month bill does not exist or has nothing outstanding. A bill that has a write-off adjustment is final and MUST never be adjusted by a rate change (`docs/05` §5.3, §5.4, §8.4, §11.1; §15 item 19; Samuel's ruling S8).

Corrections and reversals are performed (US4).

- **FR-035**: When the admin records a bank reversal or confirms a committed duplicate, the engine MUST undo the payment completely in one database transaction, in order: reverse the payment's allocations (each returning its amount as advance via one `created` movement), then clear the payment's whole remaining advance by `reversed` movements, then unmatch the payment (`docs/05` §12.1; §17 rule 21; `docs/04` §8.12).
- **FR-036**: After a complete reversal the payment MUST have no active match, no net allocations and no advance, and every affected bill MUST owe again what it owed before the payment as changed by any adjustment recorded since; advance held on the tenancy's **other** payments MUST then be applied by normal advance application to any bill that owes again, while advance restored from the reversed payment itself MUST NOT be re-applied (`docs/05` §7.2, §7.5, §12.1).
- **FR-037**: A wrong-match correction MUST be one database transaction under the `docs/05` §6.9 lock order: reverse allocations, clear advance, append the reversal match row, and append the new match when re-matching; after reversing the old tenancy's allocations, advance held on the old tenancy's **other** payments MUST be applied by normal advance application to any bill that owes again, while advance restored from the corrected payment itself MUST NOT be re-applied; if any part fails, nothing is written (Samuel's ruling R2; `docs/05` §7.2, §12, §13; `docs/04` §8.12).
- **FR-038**: A payment MUST be unmatchable only when its net allocations (signed sum) are zero; a match MUST never be edited or re-pointed — correction appends a reversal match row and a new match row (`docs/05` §12, §13; `docs/04` §8.12).
- **FR-039**: A stand-alone reversal that is not part of a re-match MUST be audited (`docs/05` §12).
- **FR-040**: Corrections MUST NOT delete or silently rewrite financial records; they append reversal or correction records and recalculate derived balances (`docs/05` §3.4, §12; §17 rule 11; constitution Principle I).
- **FR-041**: A rate change and a payment reversal or match correction MUST use the same lock order as allocation (`docs/05` §6.9) and MUST NOT call `ensure_bills_through` (`docs/05` §6.9; `docs/03` §5.2.1).
- **FR-042**: If a payment on a part-written-off bill is later reversed, the status MUST be derived again from the §8.4 formulas and the "was written off" flag MUST stay true (`docs/05` §8.4).

Status and summaries are derived (US5).

- **FR-043**: Bill status MUST be derived (never stored) as: final amount 0 with a `write_off` adjustment → Written off; final amount 0 without a `write_off` adjustment → No charge; otherwise net allocated = 0 → Unpaid, 0 < net allocated < final → Partially paid, net allocated ≥ final → Paid; the final-amount-0 checks come first, and net allocated is the signed sum in `docs/04` §7.1 (`docs/05` §8.1–8.4; `docs/04` §7.1).
- **FR-044**: The engine MUST supply a "was written off" yes/no flag that is true for every bill with a `write_off` adjustment, separate from the status (`docs/05` §8.4; `docs/04` §4, §7.1).
- **FR-045**: For each tenancy the engine MUST derive total billed, total allocated, outstanding balance, advance credit, net position, current-month status, and overall status (`docs/05` §9).
- **FR-046**: Outstanding balance MUST be reported as two amounts — from earlier months (months that have ended) and this month (the running month) — whose total is the outstanding balance, with no "not yet due" label or due date for the running month (`docs/05` §9, §14.1, §14.2; `docs/04` §7.3; §17 rule 24).
- **FR-047**: A room MUST count as fully paid when its active tenancy's outstanding balance is 0 in every month; a No charge bill MUST NOT stop a room counting as fully paid; the fully-paid ratio denominator MUST be the number of rooms with an active tenancy, excluding vacant rooms; in a no-charge month the count and ratio MUST be replaced by "No charge this month" (`docs/05` §9; `docs/03` §11.2; ADR-027).
- **FR-048**: A month MUST be judged no-charge from the standard amount for that month (not from the bills), money already allocated to that month's bills MUST become advance, and bills of closed tenancies MUST keep their amounts (frozen; payments and write-offs are still recorded against them) (`docs/05` §9).
- **FR-049**: The engine MUST support the tenant billing summary: two-amount outstanding, advance credit, net position, current-month status, the list of monthly bills, and the list of payments with allocated months (`docs/05` §14.1).
- **FR-050**: The engine MUST support the property billing summary: room list, two-amount amount due per room, billing status per room, bill adjustment notices, two-amount outstanding with no due-date wording, and server-side visibility (`docs/05` §14.2; `docs/03` §9.2).
- **FR-051**: Payment history MUST show received date, amount, matched tenancy, allocated billing month(s), amount allocated to each month, and any remaining unallocated amount (`docs/05` §14.3).
- **FR-052**: The engine MUST supply the admin report freshness data: "payments recorded up to <date>" where the date is the latest `statement_end_date` among `confirmed`/`completed` import batches, plus which months ended after that date (the running month is not flagged), noting that manual entries are not covered by the date (`docs/05` §14.4).
- **FR-053**: The engine MUST support the admin-only closed-tenancy outstanding view: a total for closed tenancies' un-written-off outstanding, separate from and never added into active-tenancy outstanding, with a per-tenancy list of room, tenants' names and contact details, balance and months covered; tenants MUST NOT see it (`docs/05` §14.5; `docs/03` §9.2).
- **FR-054**: Summary and list views MUST NEVER change a payment or an allocation (read-only) (`docs/05` §14; Samuel's ruling F-03).
- **FR-055**: No derived value (bill status, bill remaining, tenancy outstanding, advance balance, net position, utility spend) MUST be stored as an independently mutable field (`docs/04` §7; constitution Database & Schema).

Manual matching and scoping (US6).

- **FR-056**: Matching, automatic or manual, MUST append a `transaction_match` row; a payment is matched once; a match is never re-pointed; after matching the engine MUST allocate by the normal chronological rules and the action MUST be audited (`docs/05` §12, §13; `docs/04` §6.5).
- **FR-057**: Every query the engine issues MUST filter by `organization_id` (`docs/04` §8.9; constitution Database & Schema).
- **FR-058**: Utility provider payments MUST bypass tenancy matching and MUST create no allocation (`docs/05` §13; §17 rule 12; `docs/04` §6.6, §8.3).
- **FR-059**: The `transaction` table MUST remain fully immutable: the engine MUST NOT update or delete any `transaction` row; corrections use reversals, not edits (`docs/04` §6.5, §11.1; `docs/05` §3.4; constitution Principle I).

### Key Entities *(include if feature involves data)*

- **organization**: the isolation root carrying the business timezone (`docs/04` §6.2; ADR-028).
- **tenancy / room / tenant**: the occupancy a bill attaches to; status `draft | active | closed` with `start_date` and `end_date`; roommate changes do not affect billing (`docs/04` §6.3; `docs/05` §5.5).
- **monthly_bill**: one bill per tenancy per billing month; standard amount, final amount, adjusted flag, derived status (`docs/04` §6.5).
- **transaction / transaction_match**: immutable matched tenant payments and append-only match history (`docs/04` §6.5).
- **payment_allocation**: append-only link from a payment to a bill, signed by allocation type for derivation (`docs/04` §6.5).
- **advance_movement**: append-only advance-credit ledger (`created | applied | reversed`) reconciled against the derived balance (`docs/04` §6.5; ADR-021).
- **bill_adjustment**: append-only `rate_change` or `write_off` records with note and admin identity (`docs/04` §6.5).
- **billing_config / standard_amount_change**: the org-wide standard amount and its append-only change history (`docs/04` §6.4).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: ₦4,000 outstanding with ₦1,000 paid yields ₦3,000 outstanding; ₦4,000 outstanding with ₦5,000 paid yields a paid bill and ₦1,000 advance (`docs/05` §6.5, §6.6, §16).
- **SC-002**: Two bills and one payment covering both fill the oldest bill first; a payment received after month end allocates to the oldest outstanding bill; a payment received before a bill exists is held as advance until generation, then fills the bill (`docs/05` §6.7, §6.8, §7.3, §16).
- **SC-003**: A move-in month is billed in full by default and the admin can write off its whole outstanding balance; a move-out partial month is billed in full and the whole-tenancy write-off zeroes the balance after closure (`docs/05` §5.3, §5.4, §16).
- **SC-004**: A tenancy that moved in in March with an `end_date` of 20 June, untouched until a September generation, produces March–June bills (June in full) and no July/August/September bill (Samuel's ruling M1).
- **SC-005**: A standard amount raised mid-month adjusts every current-month bill of an active tenancy, including fully-paid ones (they become part paid), and leaves past months untouched; lowered mid-month, the difference on bills paid above the new amount becomes advance; closed tenancies are untouched (`docs/05` §5.3, §16; §17 rule 16).
- **SC-006**: A debt write-off zeroes the balance via an audited adjustment with all records preserved; for standard ₦4,000, paid ₦1,000, written off ₦3,000, the final amount is ₦1,000, and bill history/detail shows the original amount, the written-off amount and the final amount (Samuel's ruling M3; `docs/05` §5.3, §8.4, §16).
- **SC-007**: A payment reversed or confirmed as a duplicate is undone completely: allocations undone, advance cleared, payment unmatched, and each affected bill owes again; advance held on the tenancy's other payments is then applied to any bill that owes again, while advance restored from the reversed payment itself is not re-applied (`docs/05` §7.2, §7.5, §12.1, §16; §17 rule 21).
- **SC-008**: The advance movement ledger reconciles with the derived balance for every matched payment, and any mismatch is flagged as an integrity error (`docs/05` §7.4, §16; §17 rule 13).
- **SC-009**: On 1 August a 22-room property at ₦4,000 shows outstanding of ₦8,000 from earlier months and ₦88,000 this month; the fully-paid ratio denominator is rooms with an active tenancy; in a no-charge month the count and ratio read "No charge this month" (`docs/05` §9, §7.3; `docs/03` §11.2).
- **SC-010**: Recording a reversed or duplicate payment is a complete reversal in one transaction; correcting a wrong match is atomic (no partial writes) and follows the §6.9 lock order (Samuel's rulings R2 and the complete-reversal ruling; `docs/04` §8.12).
- **SC-011**: Every functional requirement above is exercised by at least one named automated test, and tests for financial logic are written before the implementation (constitution Principle V).
- **SC-012**: Locked billing rules 1–24 (`docs/05` §17) hold as acceptance scenarios: allocations populate bills and are chronological oldest-first; partial payments reduce outstanding; overpayments create advance; payment date does not determine billing month; the engine's reconciliation is final; advance is linked to its payment and applied automatically except during unmatch, including to a closed tenancy's own bills generated after closure; payments and allocations are immutable and bills change only through audited adjustments; corrections use reversals; provider payments do not settle tenant bills; the advance ledger reconciles; generation is lazy; no per-room amount overrides; the running month counts as outstanding from generation with no due label.

## Assumptions

- The persisted schema (`docs/04`) already exists; this feature adds no schema change and builds on the existing models under `backend/src/` and uses no `billing_override` table (removed from `docs/04`; dropping it from the existing 001 code is a separate later change, Samuel's decision 2026-11-21) (`transaction` immutable; matches in `transaction_match`). If the engine appears to need a schema change, that is escalated rather than made.
- `docs/05-billing-engine.md` is the source of intent and `docs/04-database.md` is the table/derived-rule contract; `docs/03` §5.2.1, §9.2, §10.4 and §11.1–11.2 constrain callers, visibility, timezone and reporting.
- Money is integer minor units with explicit currency; all financial records are append-only; the transaction table stays fully immutable (constitution; `docs/04` §3.4–3.5, §11.1).
- PostgreSQL is production and SQLite is local/tests; tests default to a fresh in-memory SQLite database and never the development database file (`docs/03` §6.6; AGENTS.md).
- The business timezone is one per organization, default `Africa/Lagos` (ADR-028).
- Samuel's rulings R1, R2, M1, S3, S4, S5, S6, S7 and S8 take precedence over any disagreeing prose; `docs/05` §5.1 now states the same billing range as M1, so no conflict remains.

## Out of Scope (parked — do not specify or decide here)

Per the runbook and `docs/05` §1–§2, the following are excluded from this feature and MUST NOT be specified or decided:

- Utility provider payments, statement/PDF parsing, tenant portal visibility rules, authentication and authorization, and frontend or API implementation (`docs/05` §1, §2).
- Tenancy-management actions (the close-tenancy action and the end-date edit rule).
- The admin alert and bank-account action for a closed tenancy holding advance.
- How a reversed or duplicate payment is marked once unmatched.
- Write-off notice visibility.
- The portal "as of" date.
- The catch-up screen.
- Tenant-triggered generation.
- The icon design for written-off bills.
