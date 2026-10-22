# Engine Contract: Tenant Billing Engine

**Feature**: `002-billing-engine` | **Date**: 2026-10-16

This is the callable contract the billing engine upholds: the pure-domain entry points, the persistence adapter's transactions, and the read-only views. Behaviour is defined in `docs/05-billing-engine.md` (cited per call); tables are `docs/04-database.md`. The module split is in [data-model.md](../data-model.md) §2; the structural decisions are in [research.md](../research.md).

## Purpose & scope

- **Pure domain functions** import no SQLAlchemy and no ingestion/UI/API code (`research.md` R-1).
- **The adapter** (`repository.py`) is the only write path; it owns the transaction and the `docs/05` §6.9 lock order.
- **Views** (`views.py`) are read-only.

## 1. Pure domain contract (`engine.py`, `clock.py`, `status.py`, `reconciliation.py`)

| Function | Inputs → Outputs | Rule |
|---|---|---|
| `business_month(instant, tz)` | instant, IANA tz → `date` (first day) | `docs/03` §10.4; ADR-028 |
| `month_starts_between(start, end)` | two dates → ordered month starts | M1 range; `docs/05` §5.4 |
| `expected_bill_months(tenancy, target_month, overrides)` | tenancy, target → set of months to bill | Every month in range is billed in full by default; a skip override recorded before generation suppresses a month (bill never changes the amount); US1; M1; docs/05 §5.1, §5.4 |
| `resolve_standard_amount(config, changes, month, now)` | config, change history, month → minor amount | Ended month = amount in force at start of next month; running = current (`docs/05` §5.2; `docs/04` §6.4) |
| `order_payments(payments)` | payments → ordered payments | date/time asc, amount asc, internal id; null time = 00:00 tz (`docs/05` §6.2) |
| `allocate(bills, payments)` | state → allocation plan + advance events | Oldest bill first; one allocation per fill; remainder → `created` (`docs/05` §6.3–6.4, §7.1) |
| `apply_advance(bills, remainders)` | state → allocation plan + `applied` events | Oldest remainder first, oldest bill first (`docs/05` §7.2) |
| `reverse_allocation(allocation)` | one allocation → reversal row + one `created` movement | Samuel's ruling R1; the only reversal-to-advance primitive (`docs/05` §7.4, §11.2) |
| `rate_change_plan(bills, payments, config, changes, new_amount, now)` | state + new amount → adjustments + reversals + advance + new standard amount | Current-month active bills only; rise/drop semantics; persists the new standard amount for following months (`docs/05` §5.3) |
| `write_off_plan(tenancy, bills, net_allocated_by_bill)` | closed tenancy + its bills + net → one adjustment per bill with a balance | Whole-tenancy action; `previous_amount_minor` = before, `new_amount_minor` = net allocated (Samuel's rulings M3 and S5; `docs/05` §5.3, §8.4, §11.1) |
| `complete_reversal_plan(payment, allocations, movements, match)` | state → reversals + `reversed` advances + reversal match | `docs/05` §12.1; `docs/04` §8.12 |
| `correct_match_plan(payment, allocations, movements, match, new_tenancy)` | state → reversal + unmatch + new match + allocations | Samuel's ruling R2; `docs/05` §6.9, §12, §13 |
| `bill_status(final_amount, net_allocated, has_write_off)` | values → status | Final-0 checks first; signed net per `docs/04` §7.1 (`docs/05` §8.1–8.4) |
| `was_written_off(adjustments)` | adjustments → bool | `docs/05` §8.4 |
| `tenancy_state(bills, advances)` | state → totals, two-amount outstanding, net position, overall status | `docs/05` §9; `docs/04` §7.2–7.6 |
| `reconcile(payment, allocations, movements)` | state → ok / mismatch | Derived unallocated vs logged advance; a payment with no active match is skipped (outside the identity) (`docs/05` §7.4; `docs/04` §7.5) |

Plans are pure data: the adapter persists them. A plan that would violate an invariant (allocation cap, negative remainder, unmatch with non-zero net) is rejected before any write (`docs/04` §8.1, §8.12).

## 2. Persistence adapter contract (`repository.py`)

Every method loads its domain state, calls the pure functions, writes the plan, and commits as **one database transaction**. If any write fails, the whole unit rolls back (Samuel's ruling R2; `docs/05` §6.9).

| Method | Transaction & lock order | Rule |
|---|---|---|
| `ensure_bills_through(organization_id, month)` | call generation; lock tenancies ascending id; lock open bills by month | Creation only creates bills; the allocation layer's extension (T013) applies existing advance to new bills, including a `closed` tenancy's own bills generated after closure (its advance pays them oldest first, any remainder stays recorded, and no other tenancy takes it — Samuel's ruling S7); `docs/05` §5.1, §6.9, §7.2, §7.5; ADR-022; idempotent against `UNIQUE (tenancy_id, billing_month)` |
| `allocate_for_tenancy(tenancy_id)` | call `ensure_bills_through` **inside this transaction**; lock tenancy and open bills; apply existing advance on new bills, including a `closed` tenancy's own bills generated after closure (Samuel's ruling S7); write allocations + advance movements; run `reconcile` per touched payment before commit | `docs/05` §6.9, §7.2, §7.5; fail closed on a reconciliation mismatch (`docs/04` §7.5) |
| `confirm_import_batch(batch_id)` | call `ensure_bills_through` **inside this transaction**; lock the `import_batch` row and re-check status; then allocation | `docs/03` §5.2.1 (consumes matched payments only); a double confirm allocates once |
| `confirm_rate_change(new_amount, admin_id, note, now)` | same lock order; **no** `ensure_bills_through`; persist the new standard amount, adjustments, reversals and `created`/`applied` movements; run `reconcile` for every touched payment | `docs/05` §5.3, §6.9, §7.4 |
| `record_write_off(tenancy_id, admin_id, note)` | same lock order; refuse if the tenancy is not closed; one `write_off` adjustment per bill with a balance; one audit entry per adjustment; auto public note + optional custom note | `docs/05` §5.3, §11.1; Samuel's ruling S5 |
| `complete_reversal(transaction_id, admin_id)` | reverse allocations (R1), append `reversed` advances, append reversal match, apply other-payment advance to bills that owe again, including a `closed` tenancy whose own advance pays its own bills generated after closure (Samuel's ruling S7), run `reconcile` | `docs/05` §7.2, §7.5, §12.1; `docs/04` §8.12 |
| `correct_match(transaction_id, new_tenancy_id, admin_id)` | reverse allocations, clear advance, reverse-match, new match, re-allocate, apply other-payment advance to bills that owe again, including a `closed` tenancy whose own advance pays its own bills generated after closure (Samuel's ruling S7), run `reconcile`, write the audit entry in the same transaction | Samuel's ruling R2; `docs/05` §6.9, §7.2, §7.5, §13 |
| `match_manually(transaction_id, tenancy_id, admin_id)` | append match, then allocate | `docs/05` §12, §13 |

Contract rules:
- `transaction` rows are never updated or deleted (spec FR-059; `docs/04` §11.1).
- `monthly_bill.final_amount_minor` is written only together with its `bill_adjustment` (`docs/04` §8.7).
- Every mutating method writes its `audit_log` entry; a whole-tenancy write-off writes one audit entry per adjustment (`docs/05` §12, §13; `docs/04` §6.5, §6.9).
- Every read and write filters `organization_id` (`docs/04` §8.9).

## 3. Read-only view contract (`views.py`)

| View | Returns | Rule |
|---|---|---|
| `tenant_billing_summary(organization_id, tenancy_id)` | two-amount outstanding, advance, net position, current-month status, bills, payments-with-months | `docs/05` §14.1 |
| `property_billing_summary(organization_id, property_id)` | room list, two-amount due and status per room, adjustment notices, two-amount outstanding | `docs/05` §14.2 |
| `payment_history(organization_id, tenancy_id)` | received date, amount, matched tenancy, allocated months and amounts, remainder | `docs/05` §14.3 |
| `admin_report_freshness(organization_id)` | latest `statement_end_date` among `confirmed`/`completed` batches; months ended after it (running month not flagged) | `docs/05` §14.4 |
| `closed_tenancy_outstanding(organization_id)` | closed-tenancy total + per-tenancy list (room, tenant names/contacts, balance, months) | `docs/05` §14.5 |

Views issue no INSERT/UPDATE/DELETE, so a view never changes a payment or an allocation (spec FR-054, Samuel's ruling F-03). The admin adapter operations call `ensure_bills_through` before the view runs (`docs/05` §5.1, §14.4).

## 4. Concurrency contract

- The §6.9 lock order is exercised only where row locks exist. Tests that assert serialized locking name `TEST_DATABASE_URL` and skip when it is unset (`research.md` R-12); SQLite uses the single-writer `StaticPool` test model.
