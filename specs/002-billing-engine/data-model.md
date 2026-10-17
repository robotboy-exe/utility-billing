# Data Model: Tenant Billing Engine

**Feature**: `002-billing-engine` | **Date**: 2026-10-16 | **Authoritative sources**: `docs/05-billing-engine.md` (behaviour) and `docs/04-database.md` (tables, columns, derived rules).

This document maps the engine's **domain types** to the existing tables and records the cross-cutting rules. It does **not** restate columns — those are `docs/04` §6 and are referenced by section. No table, column, constraint or index is added, renamed or dropped by this feature (`docs/04` is unchanged).

## 1. Domain type → table map

Each domain type is a pure value object built by the persistence adapter (`repository.py`) from one or more rows; the engine never passes rows around (`research.md` R-1).

| Domain type | Built from table(s) | `docs/04` | Used by (stories) |
|---|---|---|---|
| `OrganizationContext` (`organization_id`, `timezone`) | `organization` | §6.2 | US1–US6 |
| `Tenancy` (`id`, `organization_id`, `room_id`, `status`, `start_date`, `end_date`) | `tenancy` | §6.3 | US1, US5 |
| `BillingConfig` (`standard_amount_minor`, `currency`) | `billing_config` | §6.4 | US1, US3 |
| `BillingOverride` (`tenancy_id`, `billing_month`, `decision`) | `billing_override` | §6.4 | US1 |
| `StandardAmountChange` (`previous_amount_minor`, `new_amount_minor`, `effective_at`) | `standard_amount_change` | §6.4 | US1 |
| `MonthlyBill` (`id`, `organization_id`, `tenancy_id`, `billing_month`, `standard_amount_minor`, `final_amount_minor`, `currency`, `is_adjusted`) | `monthly_bill` | §6.5 | US1, US2, US3, US4, US5 |
| `Payment` (`id`, `organization_id`, `source`, `transaction_date`, `transaction_time`, `amount_minor`, `currency`, `direction`, `record_category`) | `transaction` | §6.5 | US2, US4, US6 |
| `Match` (`id`, `transaction_id`, `tenancy_id`, `match_type`, `reverses_match_id`, `created_at`) | `transaction_match` | §6.5 | US2, US4, US6 |
| `Allocation` (`id`, `transaction_id`, `monthly_bill_id`, `amount_minor`, `currency`, `allocation_type`, `reverses_allocation_id`, `created_at`) | `payment_allocation` | §6.5 | US2, US3, US4 |
| `AdvanceMovement` (`id`, `organization_id`, `tenancy_id`, `transaction_id`, `movement_type`, `amount_minor`, `currency`, `monthly_bill_id`, `allocation_id`, `occurred_at`) | `advance_movement` | §6.5 | US2, US3, US4 |
| `BillAdjustment` (`id`, `monthly_bill_id`, `adjustment_type`, `previous_amount_minor`, `new_amount_minor`, `currency`, `public_note`, `custom_note`, `internal_reason`, `admin_id`, `created_at`) | `bill_adjustment` | §6.5 | US3 |
| `ImportBatchSummary` (`status`, `statement_end_date`) | `import_batch` | §6.7 | US5 |
| `AuditEntry` (`organization_id`, `actor_type`, `actor_id`, `action`, `entity_type`, `entity_id`, `metadata`, `created_at`) | `audit_log` | §6.9 | US3, US4, US6 |

No new persisted type is introduced. `AuditEntry` is written through the existing append-only `audit_log`; adjustment, match, reversal and manual-match actions record one.

## 2. Module boundaries

- `backend/src/billing/domain.py` — pure value objects and enums above; no SQLAlchemy.
- `backend/src/billing/clock.py` — business-timezone month helpers (pure).
- `backend/src/billing/engine.py` — generation, allocation, advance, adjustments, corrections (pure).
- `backend/src/billing/status.py` — derived bill status, `was_written_off`, tenancy billing state (pure).
- `backend/src/billing/reconciliation.py` — the advance reconciliation invariant (pure).
- `backend/src/billing/repository.py` — the only ORM-dependent **write** path; loads domain state, calls the pure functions, writes results, owns the transaction and the `docs/05` §6.9 lock order.
- `backend/src/billing/views.py` — read-only reporting queries returning DTOs.

## 3. Cross-cutting rules (referenced, not restated)

Each rule is enforced by the cited section.

- **Money**: integer `BIGINT` minor units, explicit `currency`; no floats anywhere in the domain (`docs/04` §3.4–3.5; constitution Principle I).
- **Immutability**: `transaction`, `transaction_match`, `payment_allocation`, `advance_movement`, `bill_adjustment`, `standard_amount_change` are append-only (`docs/04` §11.1); the engine never updates or deletes a `transaction` (spec FR-059). `monthly_bill.final_amount_minor` and `is_adjusted` change only alongside an appended `bill_adjustment` (`docs/04` §8.7).
- **Derived state not stored**: bill status, remaining, outstanding, advance balance, net position and spend are computed (`docs/04` §7; spec FR-055).
- **Aggregation rules**: bill status and tenancy state per `docs/05` §8.1–8.4 and §9; signed net allocation per `docs/04` §7.1; remaining per `docs/04` §7.2; outstanding and the two-amount split per `docs/04` §7.3; advance per `docs/04` §7.4; net position per `docs/04` §7.6.
- **Organization scoping**: every read/write filters `organization_id` (`docs/04` §8.9; spec FR-057).
- **Month boundaries**: computed in `organization.timezone` (`docs/04` §6.2; ADR-028).
- **Generation contract**: lazy, idempotent, caller-restricted (`docs/05` §5.1, §6.9; `docs/03` §5.2.1; ADR-022).
- **Allocation gating**: only matched tenant payments; allocations attach to the active-match tenancy (`docs/05` §13; `docs/04` §8.12).
- **Advance ledger**: movements written atomically with allocations; `reversed` only offsets `created`; restoring an applied allocation is a new `created` (`docs/05` §7.4; `docs/04` §7.5, §8.8).
- **One match per transaction**: append-only match history; a match reversed at most once (`docs/04` §8.11).

## 4. Invariant → enforcement map

| Invariant | Where enforced in this feature |
|---|---|
| Allocation cap (`docs/04` §8.1) | `engine.py` allocation never writes more than the payment remainder; tested US2 |
| Advance reconciliation (`docs/04` §8.2, §7.5) | `reconciliation.py` computed and compared to the ledger; mismatch flagged; tested US2 |
| Ledger separation (`docs/04` §8.3) | Allocations only to the active-match tenancy's bills; provider payments bypass; tested US2/US6 |
| One bill per tenancy per month (`docs/04` §8.6) | Generation relies on the existing unique constraint; tested US1 |
| Bill amount changes audited (`docs/04` §8.7) | Adjustments written with `final_amount_minor`; tested US3 |
| Advance movement atomic with allocation (`docs/04` §8.8) | Adapter writes both in one transaction; tested US2 |
| Organization scoping (`docs/04` §8.9) | Adapter and views filter `organization_id`; tested US6 |
| One active match per transaction (`docs/04` §8.11) | Match append/correction rules; tested US4/US6 |
| Allocations follow the match (`docs/04` §8.12) | Unmatch only when net allocations are 0; correction reverses then re-matches; tested US4 |
| M1 bill range (`docs/05` §5.4) | Generation set derived from `[start_date, end_date]`; tested US1 |
| R1 reversal-to-advance (Samuel's ruling R1) | Single primitive in `engine.py`; tested US2/US3/US4 |
| R2 atomic match correction (Samuel's ruling R2) | One transaction under the §6.9 lock order; tested US4 |
| M3 write-off arithmetic (Samuel's ruling M3) | `previous_amount_minor` = before, `new_amount_minor` = net allocated; tested US3 |
