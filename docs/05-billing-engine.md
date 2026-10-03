# Billing Engine

Document: `docs/05-billing-engine.md`  
Version: `0.4.0`
Status: Draft — accepted MVP billing rules
Last Updated: 2026-10-03  
Related documents: `03-mvp-architecture.md`, `04-database.md`, `06-transaction-ingestion.md`

Changes in this version: Lazy bill generation is named `ensure_bills_through(organization_id, month)` with the ADR-022 caller list — admin dashboard load, payment allocation, import batch confirm, admin report requests; tenant-session requests, including the tenant portal, are not callers — and the month computed in the organization timezone (ADR-028); the payment allocation section gains the ADR-022 transaction and locking order; the engine's independence is stated against any statement parser rather than specific CSV/XLSX formats.

---

## 1. Purpose

This document defines the tenant billing engine.

The tenant billing engine is responsible for:

- Monthly tenant utility bills.
- Tenant payment allocation.
- Outstanding balance calculation.
- Partial payment handling.
- Advance payment handling.
- Late-payment reconciliation.
- Billing status derivation.
- Bill adjustment handling at the billing level.

This document covers only the **Tenant Payment Ledger**.

It does not cover:

- Utility provider payments such as BEDC payments.
- Utility spend reporting.
- Bank/PDF statement parsing.
- Tenant portal visibility rules.
- Authentication or authorization.

Utility provider payments are a separate ledger defined in the architecture and transaction ingestion documents.

---

## 2. Scope

The billing engine operates on:

- Tenancies.
- Monthly bills.
- Matched tenant payments.
- Payment allocations.
- Advance credits.
- Bill adjustments.

The billing engine does not depend on:

- PDF parsing.
- Any statement parser.
- Payvice Avantus-specific statement rules.
- Frontend implementation.
- API implementation.
- Utility provider payment records.

The billing engine must remain independent of transaction source.

---

## 3. Core Principles

### 3.1 The billing engine is the final authority

The billing engine determines:

- Which monthly bill a payment settles.
- Whether a tenancy is owing.
- Whether a tenancy is fully paid.
- Whether a tenancy has advance credit.
- The current outstanding balance.
- The current advance balance.

No other module overrides the billing engine’s derived financial state except through controlled corrections.

---

### 3.2 Payment date does not determine billing month

A payment’s date is the date the money was received.

It does not determine which monthly bill the payment settles.

Example:

- A tenant owes June.
- The tenant pays in July.
- The payment settles June.
- The payment receipt date remains July.

The billing engine decides the billing month based on outstanding bills and allocation rules.

---

### 3.3 Payments fill outstanding records chronologically

Tenant payments are processed in chronological order.

For each tenancy:

1. Payments are sorted from earliest to latest.
2. Each payment is applied to outstanding bills.
3. Bills are filled from oldest billing month to newest billing month.
4. Any remaining payment amount becomes advance credit.

The statement may list transactions newest-first, but the billing engine must process them oldest-first.

---

### 3.4 Financial history is immutable

Payments, bills, and allocations must not be silently rewritten.

Corrections must be represented through:

- Reversal allocations.
- Correction allocations.
- Bill adjustment records.
- Audit-logged admin actions.

---

### 3.5 Derived state comes from authoritative records

Billing status should be derived from:

- Monthly bill amounts.
- Payment allocations.
- Reversals/corrections.
- Advance credits.

Reports should not maintain independent copies of financial truth.

Advance credit balance is derived from payment allocations; its individual movements are additionally recorded in an append-only advance movement ledger for auditability.

---

## 4. Definitions

### 4.1 Monthly Bill

A monthly bill represents the amount due from a tenancy for a specific billing month.

A monthly bill has:

- Tenancy.
- Billing month.
- Standard amount.
- Final amount due.
- Adjustment indicator.
- Allocated amount.
- Remaining amount due.
- Status.

There must be only one monthly bill per tenancy per billing month.

---

### 4.2 Final Amount Due

The final amount due is the amount the tenancy is expected to pay for that billing month.

It is normally the standard monthly amount.

It may differ from the standard amount only through a recorded adjustment (a rate change or a write-off); see Section 5.3.

---

### 4.3 Tenant Payment

A tenant payment is a matched incoming payment belonging to a tenancy.

In the Payvice Avantus statement format, tenant payments originate from `FUNDING/` credit rows.

A tenant payment has:

- Tenancy.
- Payment received date/time.
- Amount.
- Source transaction reference.
- Allocated amount.
- Unallocated amount.

---

### 4.4 Payment Allocation

A payment allocation connects part or all of a tenant payment to a specific monthly bill.

One payment may produce multiple allocations.

Example:

```text
₦5,000 payment
→ May bill: ₦2,000
→ June bill: ₦2,000
→ July bill: ₦1,000
```

Allocations are the authoritative link between payments and bills.

---

### 4.5 Outstanding Balance

Outstanding balance is the total amount still due across a tenancy’s monthly bills after allocations.

Example:

- Total bills due: ₦4,000
- Payments allocated: ₦1,000
- Outstanding balance: ₦3,000

---

### 4.6 Advance Credit

Advance credit exists when a tenant payment exceeds all currently fillable monthly bills.

Example:

- Total bills due: ₦4,000
- Payment received: ₦5,000
- Amount allocated: ₦4,000
- Advance credit: ₦1,000

Advance credit remains linked to the original payment.

The advance balance is derived, and every advance movement is recorded in an append-only ledger (see Section 7.4).

---

### 4.7 Net Tenant Position

Net tenant position is:

```text
Net position = Outstanding balance - Advance credit
```

Possible states:

| Outstanding | Advance | Meaning |
|---:|---:|---|
| ₦3,000 | ₦0 | Tenant owes ₦3,000 |
| ₦0 | ₦1,000 | Tenant has ₦1,000 advance |
| ₦0 | ₦0 | Tenant is fully settled |

In normal operation, the engine should apply advance credit to existing outstanding bills, so a tenancy should usually be either owing or in advance, not both.

---

## 5. Monthly Bill Rules

### 5.1 Bill generation

Bills are generated **automatically and rolling** (lazy generation) by one function, `ensure_bills_through(organization_id, month)`, with no background scheduler. Callers: admin dashboard load, payment allocation, import batch confirm, admin report requests. Tenant-session requests, including the tenant portal, are not callers.

The month is computed in the organization's business timezone (ADR-028).

For that month:
- Each active tenancy receives one bill.
- Vacant rooms do not receive bills.
- Generation is idempotent.
- Generation is synchronous and triggered by real usage, not a background scheduler.
- Generation is automatic and rolling. There is no manual generation or scheduled job.

---

### 5.2 Standard amount

The standard monthly amount applies uniformly to all active tenancies. There is no per-tenancy or per-room amount override; the only per-tenancy/month override is the force-bill or force-skip decision, which never changes the amount.

Rules:

- The standard amount is the same for all rooms unless admin changes it.
- Changing the standard amount affects newly generated bills.
- Already generated bills are not silently rewritten when the standard amount changes.

---

### 5.3 Rate-change adjustments and write-offs (no per-room overrides)

There are no arbitrary per-room bill amount adjustments. The only adjustable parameter is the standard monthly amount.

**Rate change:** when the standard amount changes mid-month, unsettled current-month bills are adjusted by the delta via recorded adjustments. Settled bills and past months are never adjusted. Each adjustment is append-only, audited, carries an auto-generated public note with an optional custom note, and shows the admin's identity.

**Write-off:** when the admin foregoes a closed tenancy's debt, a write-off adjustment zeroes the outstanding balance. Records are never hard-deleted.

---

### 5.4 Mid-month occupancy

Partial-month billing follows the move-in/move-out asymmetry:
- **Move-in partial month:** not billed by default; admin can opt in to bill at the full standard amount.
- **Move-out partial month:** billed in full by default; admin can forego via write-off after closure, or exempt with foreknowledge.
- A per-tenancy, per-month billing override supports both the opt-in and the exemption.
- Proration is not automatic and not the default.

---

## 6. Payment Allocation Algorithm

The allocation process is deterministic.

### 6.1 Inputs

For a given tenancy, the engine uses:

- All monthly bills belonging to the tenancy.
- All matched tenant payments belonging to the tenancy.
- Existing payment allocations.
- Existing reversals or corrections.
- Existing unallocated payment remainders.

---

### 6.2 Payment ordering

Payments are processed in chronological order.

Ordering rules:

1. Payment date/time ascending.
2. If date/time is identical, statement row order or import sequence.
3. If still identical, amount ascending.
4. If still identical, internal transaction identifier.

The statement source may list rows newest-first. The engine must reorder them oldest-first.

---

### 6.3 Bill ordering

Bills are filled in billing-month order.

Ordering rule:

```text
Oldest unpaid or partially paid billing month first
→ then next oldest
→ then current month
→ then future months, if applicable
```

---

### 6.4 Allocation behavior

For each tenant payment:

1. Determine the payment’s unallocated amount.
2. Find the tenancy’s bills with remaining amount due.
3. Sort those bills by billing month ascending.
4. Allocate the payment to each bill until either:
   - The bill is fully paid, or
   - The payment is exhausted.
5. Create one allocation record per bill filled.
6. If the payment still has an unallocated remainder after all fillable bills are filled, classify the remainder as advance credit.

---

### 6.5 Partial payment example

Initial state:

| Bill Month | Amount Due | Allocated | Remaining |
|---|---:|---:|---:|
| June 2026 | ₦4,000 | ₦0 | ₦4,000 |

Payment received:

```text
₦1,000
```

Result:

| Bill Month | Amount Due | Allocated | Remaining | Status |
|---|---:|---:|---:|---|
| June 2026 | ₦4,000 | ₦1,000 | ₦3,000 | Partially paid |

Tenancy state:

```text
Outstanding balance: ₦3,000
Advance credit: ₦0
```

This matches the rule:

> If ₦4,000 is outstanding and ₦1,000 is paid, the records now reflect that ₦3,000 is still outstanding.

---

### 6.6 Overpayment example

Initial state:

| Bill Month | Amount Due | Allocated | Remaining |
|---|---:|---:|---:|
| June 2026 | ₦4,000 | ₦0 | ₦4,000 |

Payment received:

```text
₦5,000
```

Result:

| Bill Month | Amount Due | Allocated | Remaining | Status |
|---|---:|---:|---:|---|
| June 2026 | ₦4,000 | ₦4,000 | ₦0 | Paid |

Tenancy state:

```text
Outstanding balance: ₦0
Advance credit: ₦1,000
```

This matches the rule:

> If ₦4,000 is outstanding and ₦5,000 is paid, the records now show an advance of ₦1,000.

---

### 6.7 Multiple outstanding bills example

Initial state:

| Bill Month | Amount Due | Allocated | Remaining |
|---|---:|---:|---:|
| May 2026 | ₦2,000 | ₦0 | ₦2,000 |
| June 2026 | ₦2,000 | ₦0 | ₦2,000 |

Payment received:

```text
₦5,000
```

Allocation:

| Bill Month | Amount Due | Allocated | Remaining | Status |
|---|---:|---:|---:|---|
| May 2026 | ₦2,000 | ₦2,000 | ₦0 | Paid |
| June 2026 | ₦2,000 | ₦2,000 | ₦0 | Paid |

Tenancy state:

```text
Outstanding balance: ₦0
Advance credit: ₦1,000
```

---

### 6.8 Late payment example

Initial state:

| Bill Month | Amount Due | Allocated | Remaining |
|---|---:|---:|---:|
| June 2026 | ₦4,000 | ₦0 | ₦4,000 |
| July 2026 | ₦4,000 | ₦0 | ₦4,000 |

Payment received:

```text
15 July 2026: ₦4,000
```

Even though the payment was received in July, the engine allocates it to the oldest outstanding bill.

Result:

| Bill Month | Amount Due | Allocated | Remaining | Status |
|---|---:|---:|---:|---|
| June 2026 | ₦4,000 | ₦4,000 | ₦0 | Paid |
| July 2026 | ₦4,000 | ₦0 | ₦4,000 | Unpaid |

Payment history should show:

- Received month: July.
- Allocated month: June.

---

### 6.9 Transaction and locking order

Allocation and batch confirm run in one database transaction. Within it: call `ensure_bills_through(organization_id, month)`; on confirm, lock the `import_batch` row and re-check its status; lock tenancies in ascending id order; lock open bills `FOR UPDATE` ordered by month; write allocations and advance movements before commit (ADR-022).

---

## 7. Advance Credit Handling

### 7.1 Advance creation

Advance credit is created when a matched tenant payment has an unallocated remainder after all existing fillable bills have been filled.

The remainder remains linked to the original payment.

When advance credit is created, an append-only advance movement of type `created` is recorded, linked to the original payment.

---

### 7.2 Advance application

When a new monthly bill is generated, existing advance credit should be applied automatically.

Advance application rules:

1. Use the oldest unallocated payment remainder first.
2. Fill outstanding bills from oldest billing month to newest.
3. Create allocation records from the original payment to the newly filled bills.
4. Reduce the unallocated remainder accordingly.
5. Update advance balance.
6. Record each application as an advance movement of type `applied`.

---

### 7.3 Payment before bill generation example

A tenant pays ₦5,000 before any bill exists.

Initial result:

```text
Outstanding balance: ₦0
Advance credit: ₦5,000
```

Later, a bill is generated (lazily):

| Bill Month | Amount Due |
|---|---:|
| June 2026 | ₦4,000 |

Billing engine applies advance:

| Bill Month | Amount Due | Allocated | Remaining | Status |
|---|---:|---:|---:|---|
| June 2026 | ₦4,000 | ₦4,000 | ₦0 | Paid |

Tenancy state:

```text
Outstanding balance: ₦0
Advance credit: ₦1,000
```

---

### 7.4 Advance movement ledger and reconciliation

The advance balance is always derived as the unallocated remainder of matched tenant payments. It is never stored as a mutable number.

Every advance event is written to an append-only advance movement ledger in the same database transaction as the corresponding allocation:

- `created` — advance credit created from a payment's unallocated remainder.
- `applied` — advance credit applied to a monthly bill.
- `reversed` — a `created` movement undone by a correction (advance credit clawed back). It never undoes an `applied` movement; restoring an applied allocation records a new `created` movement.

Reconciliation invariant: For each tenant payment, the derived unallocated remainder must equal the sum of `created` movements minus `applied` and `reversed` movements. If these disagree, the system flags an integrity error. This identity holds because `reversed` only ever offsets a `created` movement; undoing an `applied` movement is recorded as a new `created` movement, never as `reversed`.

This makes advance credit auditable and tamper-evident without introducing a second mutable source of truth.

---

## 8. Bill Status Rules

Bill status is derived. "Allocated amount" below is the signed net defined in `04-database.md` Section 7.1: allocation amounts are added for `automatic`/`manual`/`correction` and subtracted for `reversal`.

### 8.1 Unpaid

A bill is unpaid when:

```text
Allocated amount = 0
```

---

### 8.2 Partially paid

A bill is partially paid when:

```text
0 < Allocated amount < Final amount due
```

---

### 8.3 Paid

A bill is paid when:

```text
Allocated amount >= Final amount due
```

A bill should not normally be over-allocated.

If an allocation exceeds the final amount due because of a later bill adjustment or correction, the excess must be handled through the correction mechanism.

---

## 9. Tenancy Billing State

For each tenancy, the engine derives:

| Field | Meaning |
|---|---|
| Total billed | Sum of final amounts due across all bills |
| Total allocated | Sum of valid allocations |
| Outstanding balance | Amount still owed across bills |
| Advance credit | Unallocated tenant payment remainder |
| Net position | Outstanding balance minus advance credit |
| Current month status | Status of the current month’s bill |
| Overall status | Owing, settled, or in advance |

---

## 10. Interaction with Bill Generation

When bills are generated (lazily):
- Create missing monthly bills for active tenancies.
- Do not duplicate existing bills.
- Apply any billing overrides (force-bill or force-skip).
- Skip move-in partial months unless an override forces billing.
- Reconcile existing advance credits and create allocations where appropriate.
- Update derived tenancy billing state.
Bill generation must be safe to run repeatedly.

---

## 11. Interaction with Bill Adjustments

### 11.1 Adjustment before allocation

Adjustments arise only from rate changes or write-offs. An adjustment stores: adjustment type, original amount, new amount, timestamp, auto-generated public note with optional custom note, and admin identity.

---

### 11.2 Adjustment after allocation

If a bill already has allocations, adjustment must preserve financial integrity:
- Existing allocations remain part of history.
- The final amount due changes only through an adjustment record.
- Derived remaining due is recalculated.
- If the adjusted amount is lower than the allocated amount, the excess is handled through controlled correction.
- No allocation history may be silently rewritten.

---

## 12. Corrections and Reversals

Corrections are required when:

- A payment was matched to the wrong tenancy.
- An allocation was applied incorrectly.
- A bill amount was adjusted after allocation.
- A duplicate payment was accidentally imported.
- Admin needs to manually reallocate a payment.

Correction principles:

- Do not delete financial records.
- Create reversal or correction entries.
- Preserve original history.
- Recalculate derived balances.
- Record the correction in the audit log.
- Record advance reversals in the advance movement ledger: use type `reversed` only to undo a `created` movement, and record the restoration of an applied allocation as a new `created` movement (never as `reversed`).

Detailed correction workflow belongs in the database and billing implementation documents.

---

## 13. Manual Matching and Allocation

Only matched tenant payments enter the billing engine.

Unmatched payments:

- Do not affect tenancy billing records.
- Remain in the unmatched queue.
- Can be manually matched by admin.

After manual matching:

- The billing engine processes the payment according to the normal chronological allocation rules.
- The action is audited.

Manual reallocation may be supported later, but automatic allocation is the default.

---

## 14. Reporting Requirements

The billing engine must support the following reporting views.

### 14.1 Tenant billing summary

For a tenancy:

- Current outstanding balance.
- Current advance credit.
- Net position.
- Current month bill status.
- List of monthly bills.
- List of payments with allocated months.

---

### 14.2 Property billing summary

For a property:

- Room list.
- Amount due per room.
- Billing status per room.
- Bill adjustment notices.
- Visibility rules applied server-side.

This view is defined by the architecture visibility policy.

---

### 14.3 Payment history

For each tenant payment, reports should show:

- Payment received date.
- Payment amount.
- Matched tenancy.
- Allocated billing month or months.
- Amount allocated to each month.
- Remaining unallocated amount, if any.

---

## 15. Edge Cases

The billing engine must handle:

1. Partial payments.
2. Overpayments.
3. Multiple outstanding months.
4. Payments received before bills are generated.
5. Bills generated after advance credit exists.
6. Late payments covering older months.
7. Duplicate payments.
8. Reversed payments.
9. Adjusted bills after allocation.
10. Tenancy closure with outstanding balance.
11. Tenancy closure with advance credit.
12. Roommate changes within the same tenancy.
13. Multiple payments with identical timestamps.
14. Payments matched manually after initial import.
15. Move-in partial month skipped by default, then opted in.
16. Move-out partial month billed, then written off after closure.
17. Standard amount changed mid-month with some current-month bills settled and others unsettled.
18. Write-off of a closed tenancy's outstanding balance.
19. Billing override forcing a bill or a skip for a specific tenancy-month.

---

## 16. Testing Scenarios

At minimum, automated tests should cover:

| Scenario | Expected result |
|---|---|
| ₦4,000 outstanding, ₦1,000 paid | ₦3,000 outstanding |
| ₦4,000 outstanding, ₦5,000 paid | Bill paid, ₦1,000 advance |
| Two bills due, one payment covering both | Oldest bill filled first |
| Payment received after month end | Allocates to oldest outstanding bill |
| Payment received before bill exists | Held as advance until bill generation |
| New bill generated while advance exists | Advance fills bill automatically |
| Bill adjusted downward after payment | Excess becomes controlled correction/advance |
| Bill adjusted upward after payment | Bill becomes partially paid or unpaid |
| Duplicate payment imported | Duplicate detection prevents double allocation |
| Payment reversed | Allocations reversed and balances recalculated |
| Advance movement ledger vs derived balance | Ledger reconciles; any mismatch flagged as integrity error |
| Standard amount changed mid-month | Only unsettled current-month bills adjusted; settled bills and past months untouched |
| Move-in partial month | Not billed by default; billed when admin opts in |
| Move-out partial month | Billed in full; write-off zeroes balance after closure |
| Debt written off | Balance zeroed via audited adjustment; records preserved |

---

## 17. Locked Billing Rules

The following rules are locked for MVP:

1. Tenant payments populate tenancy billing records through allocation.
2. Payments are processed chronologically.
3. Bills are filled from oldest billing month to newest.
4. Partial payments reduce outstanding balances.
5. Overpayments create advance credit.
6. Payment date does not determine billing month.
7. The billing engine’s reconciliation is final.
8. Advance credit is linked to the original payment.
9. Advance credit is applied automatically to existing or newly generated bills.
10. Bills, payments, and allocations are immutable historical records.
11. Corrections use controlled reversal/adjustment mechanisms.
12. Utility provider payments do not settle tenant bills.
13. Advance credit movements are recorded in an append-only ledger and reconciled against the derived balance; mismatches are flagged.
14. Bill generation is automatic and rolling (lazy), not manual.
15. There are no arbitrary per-room bill amount overrides.
16. Rate changes adjust only unsettled current-month bills; settled bills and past months are never adjusted.
17. Rate-change adjustments carry an auto-generated public note and show the admin's identity.
18. Move-in partial months are not billed by default; move-out partial months are billed in full by default.
19. Foregone debt is written off via an audited action; records are never hard-deleted.