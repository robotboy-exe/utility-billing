# Billing Engine

Document: `docs/05-billing-engine.md`  
Version: `0.9.0`
Status: Draft — design phase
Last Updated: 2026-11-21  
Related documents: `03-mvp-architecture.md`, `04-database.md`, `06-transaction-ingestion.md`

Changes in this version: Removes the skip decision, the force-bill decision and the `billing_override` mechanism — there is no per-tenancy, per-month billing override; a move-in and a move-out month are both billed in full by default. Adds the write-off of the whole outstanding balance of a tenancy's move-in month bill, on an active or a closed tenancy, as one write-off adjustment on that bill with no chosen amount; the whole-tenancy write-off for a closed tenancy is unchanged. A bill that has a write-off adjustment is final, and a rate change never touches it.

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

### 3.6 Billing ground rules

1. Bills, payments and advance credit each belong to one tenancy and are reconciled against that tenancy only. A payment of one tenancy never affects a bill of another.
2. Advance credit exists to pay the bills of the tenancy that owns it, whether that tenancy is active or closed.
3. Every bill that has an amount due is to be paid and reconciled unless the admin explicitly writes it off.

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

Advance credit exists when a tenant payment exceeds all currently fillable monthly bills, or when a reversal returns part of a payment (for example after a rate drop, Section 5.3).

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

In normal operation, the engine should apply advance credit to existing outstanding bills (Section 7.2; advance left on a closed tenancy pays only that tenancy's own later bills, Section 7.5), so a tenancy should usually be either owing or in advance, not both.

---

## 5. Monthly Bill Rules

### 5.1 Bill generation

Bills are generated **automatically and rolling** (lazy generation) by one function, `ensure_bills_through(organization_id, month)`, with no background scheduler. Callers: admin dashboard load, payment allocation, import batch confirm, admin report requests. Tenant-session requests, including the tenant portal, are not callers.

The month is computed in the organization's business timezone (ADR-028).

For that month:
- Each active or closed tenancy is billed for every month from its move-in month through the month of its move-out date (end date), both included, and for no month after the move-out month; a tenancy with no move-out date is billed through the target month. This holds even when generation runs months after the move-out. A draft tenancy is never billed.
- Vacant rooms do not receive bills.
- Generation is idempotent.
- Generation is synchronous and triggered by real usage, not a background scheduler.
- Generation is automatic and rolling. There is no manual generation or scheduled job.

---

### 5.2 Standard amount

The standard monthly amount applies uniformly to all active tenancies. There is no per-tenancy or per-room amount override.

Rules:

- The standard amount is the same for all rooms unless admin changes it.
- A change of the standard amount takes effect when the admin saves it. Each bill takes the standard amount in force at the end of its month or, for the running month, the amount currently in force. A bill generated late for an ended month therefore takes the amount that was in force at the end of that month, not the current one. The new amount applies to all following months and, through recorded adjustments, to the existing bills of the current month of active tenancies (Section 5.3).
- Already generated bills are not silently rewritten when the standard amount changes.

---

### 5.3 Rate-change adjustments and write-offs (no per-room overrides)

There are no arbitrary per-room bill amount adjustments. The only adjustable parameter is the standard monthly amount.

**Rate change:** when the standard amount changes mid-month, every bill of the current month that already exists for an active tenancy is set to the new amount by a recorded adjustment (the difference between the new and the old amount), whether the bill is unpaid, part paid or fully paid, so that a rate change applies to the running month. Bills of past months are never adjusted, a bill that has a write-off adjustment is final and is never touched by a rate change, and the bills of closed tenancies keep their amounts and are never touched by a rate change; payments matched to a closed tenancy and write-offs are still recorded against its bills. A rate change takes effect at the moment the admin saves it, and the current month is the business-timezone month of that moment. A bill generated later for the running month uses the new standard amount; a bill generated later for an ended month uses the amount in force at the end of that month (Section 5.2). Each adjustment is append-only, audited, carries an auto-generated public note with an optional custom note, and shows the admin's identity.

- **Rate rises:** a bill that was fully paid becomes part paid, and the difference is still owed. If the tenancy holds advance, normal advance application (Section 7.2) pays the difference from it. Example: July bill ₦4,000, fully paid; the rate rises to ₦5,000; the bill is now billed ₦5,000, paid ₦4,000, ₦1,000 still to pay.
- **Rate drops:** if the new amount is lower than what is already paid on a bill, the difference is not ignored. It is taken off the bill by a reversal allocation and becomes advance credit linked to the payment it came from (one `created` advance movement for each reversal allocation, Section 7.4), following Section 11.2. If the bill was paid by more than one payment, the difference is taken from the payments in the exact reverse of the order in Section 6.2 (latest payment date/time first, then larger amount, then higher internal identifier), whatever the order in which the allocations were made. Normal advance application (Section 7.2) then applies the advance at once: to the tenancy's oldest outstanding bill first, otherwise it waits for the next bill generated.

**Write-off:** when the admin foregoes a closed tenancy's debt, one write-off action zeroes the tenancy's whole outstanding balance by recording one write-off adjustment for every bill that still has a balance. Writing off a chosen amount or a chosen selection of bills is not supported in the MVP. The whole-tenancy write-off is possible only for a closed tenancy, and a rate change never touches a closed tenancy. The admin can also write off the whole outstanding balance of one bill, the tenancy's move-in month bill, on an active or a closed tenancy; this is one write-off adjustment on that bill, with no chosen amount, and no other bill can be written off this way. Records are never hard-deleted.

---

### 5.4 Mid-month occupancy

Partial-month billing:
- **Move-in partial month:** billed in full by default; the admin can forego it by writing off the whole outstanding balance of the move-in month bill (Section 5.3).
- **Move-out partial month:** billed in full by default; the admin can forego it after closure with the whole-tenancy write-off (Section 5.3).
- There is no per-tenancy, per-month billing override and no skip decision. A month in which nobody is charged is a no-charge month (Section 9).
- Proration is not automatic and not the default.

---

### 5.5 Roommate changes

Bills belong to the tenancy, not to a tenant. Adding, removing or replacing a roommate within the same tenancy does not change any bill, payment, allocation or advance credit.

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
2. If date/time is identical, amount ascending (smaller amount first).
3. If still identical, internal transaction identifier.

No stored row order or import sequence is used. A payment with no time of day counts as the start of its date (00:00 in the business timezone).

The statement source may list rows newest-first. The engine must reorder them oldest-first.

A payment matched after other payments of the tenancy were allocated is processed when it is matched: it fills only what is still open, and existing allocations are not re-ordered (Section 3.4).

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

Allocation and batch confirm run in one database transaction. Within it: call `ensure_bills_through(organization_id, month)`; on confirm, lock the `import_batch` row and re-check its status; lock tenancies in ascending id order; lock open bills `FOR UPDATE` ordered by month; write allocations and advance movements before commit (ADR-022). A rate change and a payment reversal or match correction (Section 12) also run in one database transaction with the same lock order; they do not call `ensure_bills_through`.

---

## 7. Advance Credit Handling

### 7.1 Advance creation

Advance credit is created when a matched tenant payment has an unallocated remainder after all existing fillable bills have been filled. It is also created when an allocation is reversed (Sections 5.3 and 12).

The remainder remains linked to the original payment.

When advance credit is created, an append-only advance movement of type `created` is recorded, linked to the original payment.

---

### 7.2 Advance application

Existing advance credit is applied automatically when a new monthly bill is generated, and also after a rate change in the running month: a rate rise lets advance pay the new difference, and a rate drop returns money to the payment as advance, which is applied the same way (Section 5.3). Advance restored during a match correction or a payment reversal (Section 12) is not re-applied, because that payment is being unmatched; but advance held by the tenancy on its other payments is applied to any bill that owes again after the reversal.

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

The engine checks this identity for every payment whose allocations or movements a write touches, before the transaction commits; on a mismatch the transaction is rolled back and an integrity error is raised. A check over all payments is not part of the MVP.

This makes advance credit auditable and tamper-evident without introducing a second mutable source of truth.

---

### 7.5 Tenancy closed while holding advance credit

When a tenancy is closed and still holds advance credit, the advance stays recorded and visible on its original payment. It is not refunded, written off or moved automatically, and no bill of any other tenancy, including a later tenancy in the same room, takes it. A bill generated for that tenancy after closure is paid from its advance by Section 7.2; what remains stays recorded. It stays linked to its payment and still reconciles under Section 7.4. How the admin is alerted and how the money is returned are not decided in this document.

---

## 8. Bill Status Rules

Bill status is derived. "Allocated amount" below is the signed net defined in `04-database.md` Section 7.1: allocation amounts are added for `automatic`/`manual`/`correction` and subtracted for `reversal`.

The rules in 8.1 to 8.3 apply to a bill whose final amount due is above 0. A bill whose final amount due is 0 is checked first (Section 8.4).

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

### 8.4 Written off

A bill whose final amount due is 0 and that has a write-off adjustment is **Written off**. This is checked before 8.1 to 8.3, because a bill with a final amount of 0 and nothing allocated would otherwise read as unpaid. A bill whose final amount due is 0 and that has no write-off adjustment (for example, the standard amount is 0) is **No charge**: nothing is owed on it.

When only the unpaid part of a part-paid bill is written off, the final amount due becomes the amount already paid and the bill reads **Paid** under 8.3. The engine also supplies a yes/no flag, "was written off", which is true for every bill that has a write-off adjustment, so that screens can mark such a bill (for example with an icon). The engine supplies only the flag; the icon and its design belong to the interface.

A write-off sets the bill's adjusted indicator like any other adjustment, carries the public note and shows the admin's identity (Section 11.1). If a payment on a bill that was part written off is later reversed (Section 12.1), the status is derived again from the formulas above and the written-off flag stays true.

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

The running month's bill counts in the outstanding balance from the day it is generated. No screen or report shows a "not yet due" label or a due date for it. For rate changes the rule is: a rate change never touches past months or closed tenancies, and can adjust only the running month's bills of active tenancies that have no write-off adjustment (Section 5.3).

For summaries, the outstanding balance is also reported as two separate amounts: **from earlier months** (bills of months that have ended) and **this month** (the running month's bills). Their total is the outstanding balance. A room counts as fully paid when its active tenancy's outstanding balance is 0 in every month, earlier and current; a No charge bill owes nothing and does not stop a room counting as fully paid. The denominator of the fully-paid ratio is the number of rooms that have an active tenancy; vacant rooms are not counted in it. Example: 22 rooms at ₦4,000; on 1 August the summary shows from earlier months ₦8,000 and this month ₦88,000.

A month is a no-charge month when the standard amount for it is 0, judged from the standard amount and not from the bills (Section 5.2: for the running month, the amount currently in force; for an ended month, the amount in force at its end). In a no-charge month every bill of an active tenancy is No charge (Section 8.4); bills of closed tenancies keep their amounts (their amounts are frozen; payments and write-offs are still recorded against them). Summaries and reports show "No charge this month" instead of the fully-paid-rooms count and ratio. Money already allocated to that month's bills becomes advance (Section 5.3).

---

## 10. Interaction with Bill Generation

When bills are generated (lazily):
- Create missing monthly bills for tenancies within their billing range (Section 5.1).
- Do not duplicate existing bills.
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
- If the adjusted amount is lower than the allocated amount, the excess is handled through controlled correction: a reversal allocation for the excess and one `created` advance movement for each reversal allocation (Section 7.4). For a rate drop this is the rule in Section 5.3. A write-off does not cause it, because a write-off removes only what is still owed.
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
- Record match corrections by appending a reversal match row and then a new match row; never edit a match. A match is reversed only after the wrong tenancy holds no allocations from the payment; the reversal also clears the payment's advance in the same database transaction (04 §8, item 12).

The workflow for a reversed payment or confirmed duplicate is in Section 12.1; other detailed correction workflows belong in the database and billing implementation documents.

### 12.1 Reversed payment or confirmed duplicate

When the admin records that the bank reversed a payment, or confirms that a committed payment is a duplicate, the engine undoes it completely, in this order and in one database transaction:

1. The payment's allocations are reversed (reversal allocations). Each reversal returns its amount to the payment as advance with one `created` advance movement (Section 7.4), so every bill the payment had paid owes that amount again.
2. The payment's whole remaining advance is cleared by `reversed` advance movements and the payment is unmatched (the last correction principle above; `04-database.md` Section 8, item 12).

After this the payment has no active match, no net allocations and no advance, and each affected bill owes what it owed before the payment, as changed by any adjustment recorded since. The payment stays in the unmatched queue as a record. How a bank-reversed payment or a confirmed duplicate is marked once it is unmatched, so that it cannot be matched again by mistake, is not yet decided. Billing only carries out the confirmed reversal; spotting a duplicate before commit is the job of the duplicate key at import (`04-database.md` Section 10), and how the admin records a bank reversal or a confirmed duplicate after commit is not defined in this document.

---

## 13. Manual Matching and Allocation

Only matched tenant payments enter the billing engine.

Unmatched payments:

- Do not affect tenancy billing records.
- Remain in the unmatched queue.
- Can be manually matched by admin.

Matching, automatic or manual, appends a `transaction_match` row (04); a payment is matched once. A wrong match is corrected by reversing its allocations and advance, appending a reversal match row, then appending a new match; a match is never re-pointed. After a match:

- The billing engine processes the payment according to the normal chronological allocation rules.
- The action is audited.

A payment may be matched, manually, to a closed tenancy, for example when a former tenant pays part of a debt. It fills that tenancy's outstanding bills by the normal allocation rules, oldest first; any remainder is advance credit that stays recorded on the closed tenancy (Section 7.5).

Manual reallocation may be supported later, but automatic allocation is the default.

---

## 14. Reporting Requirements

The billing engine must support the following reporting views.

### 14.1 Tenant billing summary

For a tenancy:

- Current outstanding balance, as two amounts: from earlier months and this month (Section 9).
- Current advance credit.
- Net position.
- Current month bill status.
- List of monthly bills.
- List of payments with allocated months.

---

### 14.2 Property billing summary

For a property:

- Room list.
- Amount due per room, as two amounts: from earlier months and this month (Section 9).
- Billing status per room.
- Bill adjustment notices.
- Outstanding as two amounts, from earlier months and this month, with no due-date wording (Section 9).
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

### 14.4 Admin report freshness note

Payments enter the engine when a statement is imported or when the admin enters one manually. Admin reports therefore state "payments recorded up to <date>", where the date is the latest `statement_end_date` among import batches with status `confirmed` or `completed` (`import_batch`, `04-database.md` Section 6.7), and they flag months that ended after that date (the running month is not flagged), so that a missing payment reads as "statement not imported yet" and not as non-payment. Manual entries are recorded as they are made and are not covered by this date. Admin report requests also generate any missing bills (Section 5.1).

---

### 14.5 Closed tenancies with an outstanding balance (admin only)

The admin dashboard shows the outstanding balance of closed tenancies that has not been written off as its own total, separate from the outstanding balance of active tenancies and never added into it. Below that total, each closed tenancy with an outstanding balance is listed with its room, its tenants' names and contact details, its outstanding balance and the months it covers, so the admin can see exactly who owes what. This view is for the admin only. Tenant views and the property totals shown to tenants count active tenancies only (Section 9; `03-mvp-architecture.md` Section 9.2).

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
15. Move-in partial month billed in full by default, with an admin write-off of that bill.
16. Move-out partial month billed, then written off after closure.
17. Standard amount raised or lowered mid-month, with some current-month bills fully paid, some part paid and some unpaid.
18. Write-off of a closed tenancy's outstanding balance.
19. Write-off of a tenancy's move-in month bill.

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
| Bill adjusted downward after payment | Excess is reversed from the payment(s) and becomes advance |
| Bill adjusted upward after payment | Bill becomes part paid (unpaid only if nothing was paid) |
| Duplicate payment imported | Duplicate detection prevents double allocation |
| Payment reversed or confirmed duplicate | Complete reversal: allocations undone, advance cleared, payment unmatched, bills owe again |
| Advance movement ledger vs derived balance | Ledger reconciles; any mismatch flagged as integrity error |
| Standard amount raised mid-month | Every current-month bill of an active tenancy is adjusted, including fully paid ones (they become part paid); past months untouched |
| Standard amount lowered mid-month | Every current-month bill of an active tenancy is lowered; the difference on bills paid above the new amount becomes advance; past months untouched |
| Standard amount changed mid-month, closed tenancy | Its bills keep their amounts and are not touched |
| Move-in partial month | Billed in full by default; the admin can write off its whole outstanding balance |
| Move-out partial month | Billed in full; write-off zeroes balance after closure |
| Debt written off | Balance zeroed via audited adjustment; records preserved |
| Closed tenancy holding advance, bill generated after closure | Paid from that tenancy's advance; any remainder stays recorded |

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
9. Advance credit is applied automatically to existing or newly generated bills of the same tenancy, except advance restored during a match correction or payment reversal (Section 7.2). A closed tenancy's advance pays only that tenancy's own bills generated after closure (Section 7.5).
10. Payments and allocations are immutable historical records; a bill changes only through audited `bill_adjustment` rows.
11. Corrections use controlled reversal/adjustment mechanisms.
12. Utility provider payments do not settle tenant bills.
13. Advance credit movements are recorded in an append-only ledger and reconciled against the derived balance; mismatches are flagged.
14. Bill generation is automatic and rolling (lazy), not manual.
15. There are no arbitrary per-room bill amount overrides.
16. A mid-month rate change sets every current-month bill of an active tenancy to the new amount, paid or not, except a bill that has a write-off adjustment; past months and closed tenancies are never touched. If the new amount falls below what is paid on a bill, the difference becomes advance credit. The new amount applies to all following months.
17. Rate-change adjustments carry an auto-generated public note and show the admin's identity.
18. Move-in and move-out partial months are billed in full by default; the admin can write off the whole outstanding balance of the move-in month bill, and a closed tenancy's whole outstanding balance, including its move-out month, with the whole-tenancy write-off.
19. Foregone debt is written off via an audited action; records are never hard-deleted.
20. A bill whose whole amount is written off reads "Written off"; a part-paid bill whose rest is written off reads "Paid" and is flagged as written off; a bill whose final amount is 0 without a write-off (for example, the standard amount is set to 0) reads "No charge".
21. A reversed payment or confirmed duplicate is undone completely: allocations reversed, advance cleared, payment unmatched.
22. Advance on a closed tenancy stays recorded and visible; it is not refunded, written off or moved automatically. A bill generated for that tenancy after closure is paid from its advance (Section 7.2).
23. A roommate change does not affect bills, payments, allocations or advance.
24. The running month's bill counts as outstanding from the day it is generated; there is no "not yet due" label or due date.
