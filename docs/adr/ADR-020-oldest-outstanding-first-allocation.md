# ADR-020 — Chronological Oldest-Outstanding-First Allocation

**Status:** Accepted

## Context

Tenant payments must populate billing records deterministically.

## Decision

Tenant payments are processed chronologically.

Payments fill outstanding bills from oldest billing month to newest.

Remaining payment amount becomes advance credit.

## Consequences

- Allocation is deterministic and reproducible.
- Advance credit remains linked to the original payment.
- Detailed behavior is specified in `05-billing-engine.md`.
