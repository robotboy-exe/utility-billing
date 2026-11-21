# ADR-024 — Partial-Month Billing Asymmetry (revised)

**Status:** Accepted (revised)

## Context

A tenant's first and last months are usually partial.

## Decision

A move-in partial month and a move-out partial month are both billed in full by default. The admin can forego the move-in month by writing off that bill, and a closed tenancy's debt, including its move-out month, with the whole-tenancy write-off. There is no skip decision and no billing override.

## Consequences

- Billing reflects what the system knows at generation time.
- Write-offs handle real-world exceptions.
