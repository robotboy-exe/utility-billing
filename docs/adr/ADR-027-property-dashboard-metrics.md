# ADR-027 — Property Dashboard Metrics (revised)

**Status:** Accepted (revised)

## Context

Tenants need a transparent property-level view of billing and utility spend.

## Decision

The property view shows total outstanding debt of active tenancies as two separate amounts (from earlier months and this month, with no due-date wording), total room count, fully-paid room count, a clearly labeled ratio of fully-paid rooms to rooms with an active tenancy (the fully-paid room count and the ratio are replaced by "No charge this month" in a month whose standard amount is 0), current-month utility spend (BEDC outflow), and historical utility spend (BEDC outflow) as the only historical data.

## Consequences

- Historical figures come from the Utility Bill Payment Ledger, not tenant payments.
- Historical months expose totals only, no room counts.
