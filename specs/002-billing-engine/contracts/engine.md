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
| `expected_bill_months(tenancy, target_month, overrides)` | tenancy, target → set of months to bill | US1; M1; `docs/05` §5.1, §5.4 |
| `resolve_standard_amount(config, changes, month, now)` | config, change history, month → minor amount | Ended month = amount in force at start of next month; running = current (`docs/05` §5.2; `docs/04` §6.4) |
| `order_payments(payments)` | payments → ordered payments | date/time asc, amount asc, internal id; null time = 00:00 tz (`docs/05` §6.2) |
| `allocate(bills, payments)` | state → allocation plan + advance events | Oldest bill first; one allocation per fill; remainder → `created` (`docs/05` §6.3–6.4, §7.1) |
| `apply_advance(bills, remainders)` | state → allocation plan + `applied` events | Oldest remainder first, oldest bill first (`docs/05` §7.2) |
| `reverse_allocation(allocation)` | one allocation → reversal row + one `created` movement | Samuel's ruling R1; the only reversal-to-advance primitive (`docs/05` §7.4, §11.2) |
| `rate_change_plan(bills, payments, config, changes, new_amount, now)` | state + new amount → adjustments + reversals + advance | Current-month active bills only; rise/drop semantics (`docs/05` §5.3) |
| `write_off_plan(bill, net_allocated)` | bill + net → adjustment | `previous_amount_minor` = before, `new_amount_minor` = net allocated (Samuel's ruling M3; `docs/05` §5.3, §8.4) |
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
| `ensure_bills_through(organization_id, month)` | call generation; lock tenancies ascending id; lock open bills by month | Generation only creates bills (no advance application here); `docs/05` §5.1, §6.9; ADR-022; idempotent against `UNIQUE (tenancy_id, billing_month)` |
| `allocate_for_tenancy(tenancy_id)` | call `ensure_bills_through` **inside this transaction**; lock tenancy and open bills; apply existing advance on new bills; write allocations + advance movements; run `reconcile` per touched payment before commit | `docs/05` §6.9, §7.2; fail closed on a reconciliation mismatch (`docs/04` §7.5) |
| `confirm_import_batch(batch_id)` | call `ensure_bills_through` **inside this transaction**; lock the `import_batch` row and re-check status; then allocation | `docs/03` §5.2.1 (consumes matched payments only); a double confirm allocates once |
| `confirm_rate_change(new_amount, admin_id, note, now)` | same lock order; **no** `ensure_bills_through` | `docs/05` §5.3, §6.9 |
| `record_write_off(bill_id, admin_id, note)` | same lock order; refuse if the tenancy is not closed | `docs/05` §5.3, §11.1 |
| `complete_reversal(transaction_id, admin_id)` | reverse allocations (R1), append `reversed` advances, append reversal match, apply other-payment advance to bills that owe again, run `reconcile` | `docs/05` §7.2, §12.1; `docs/04` §8.12 |
| `correct_match(transaction_id, new_tenancy_id, admin_id)` | reverse allocations, clear advance, reverse-match, new match, re-allocate, apply other-payment advance to bills that owe again, run `reconcile` | Samuel's ruling R2; `docs/05` §6.9, §7.2, §13 |
| `match_manually(transaction_id, tenancy_id, admin_id)` | append match, then allocate | `docs/05` §12, §13 |

Contract rules:
- `transaction` rows are never updated or deleted (spec FR-059; `docs/04` §11.1).
- `monthly_bill.final_amount_minor` is written only together with its `bill_adjustment` (`docs/04` §8.7).
- Every mutating method writes its `audit_log` entry (`docs/05` §12, §13).
- Every read and write filters `organization_id` (`docs/04` §8.9).

## 3. Read-only view contract (`views.py`)

| View | Returns | Rule |
|---|---|---|
| `tenant_billing_summary(organization_id, tenancy_id)` | two-amount outstanding, advance, net position, current-month status, bills, payments-with-months | `docs/05` §14.1 |
| `property_billing_summary(organization_id, property_id)` | room list, two-amount due and status per room, adjustment notices, two-amount outstanding | `docs/05` §14.2 |
| `payment_history(organization_id, tenancy_id)` | received date, amount, matched tenancy, allocated months and amounts, remainder | `docs/05` §14.3 |
| `admin_report_freshness(organization_id)` | latest `statement_end_date` among `confirmed`/`completed` batches; months ended after it (running month not flagged) | `docs/05` §14.4 |
| `closed_tenancy_outstanding(organization_id)` | closed-tenancy total + per-tenancy list (room, tenant names/contacts, balance, months) | `docs/05` §14.5 |

Views issue no INSERT/UPDATE/DELETE, so requesting one cannot change a payment or allocation (spec FR-054).

## 4. Concurrency contract

- The §6.9 lock order is exercised only where row locks exist. Tests that assert serialized locking name `TEST_DATABASE_URL` and skip when it is unset (`research.md` R-12); SQLite uses the single-writer `StaticPool` test model.
