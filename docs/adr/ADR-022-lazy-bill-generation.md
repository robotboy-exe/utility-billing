# ADR-022 — Automatic Rolling Bill Generation (Lazy) (revised)

**Status:** Accepted (revised)

## Context

Free hosting cannot run scheduled jobs, but billing should feel automatic and rolling.

## Decision

Bills are generated lazily and synchronously by one function,
`ensure_bills_through(organization_id, month)`, with no background scheduler.

- It creates any missing bill for each active tenancy for each month up to and including
  `month`, consulting `billing_override` (ADR-024). Creation is
  `INSERT ... ON CONFLICT (tenancy_id, billing_month) DO NOTHING`, so it is idempotent
  and safe under concurrency.
- Callers: admin dashboard load, payment allocation, import batch confirm, admin report
  requests. Tenant-session requests, including the tenant portal, are not callers.
- Allocation and batch confirm run in one database transaction. Within it: call the
  function; for confirm, lock the `import_batch` row and re-check its status; lock
  tenancies in ascending id order; lock open bills `FOR UPDATE` ordered by month; write
  allocations and advance movements before commit.
- `month` is computed in the organization timezone (ADR-028).

## Consequences

- No manual monthly action is needed.
- Manual monthly generation is removed; generation is lazy only.
- Reports trigger generation to stay accurate.
- Tenant-facing figures can lag a month rollover until the next admin action, so the
  portal shows an "as of" date.
