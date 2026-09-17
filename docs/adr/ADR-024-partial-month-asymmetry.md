# ADR-024 — Partial-Month Billing Asymmetry

**Status:** Accepted

## Context

The system knows about move-in at creation time but only learns of move-out after the fact.

## Decision

A move-in partial month is not billed by default (admin can opt in). A move-out partial month is billed in full by default (admin can forego via write-off after closure, or exempt with foreknowledge). A per-tenancy, per-month billing override supports both.

## Consequences

- Billing reflects what the system knows at generation time.
- Admin overrides handle real-world exceptions.
