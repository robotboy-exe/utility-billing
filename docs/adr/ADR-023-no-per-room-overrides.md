# ADR-023 — No Per-Room Overrides; Rate-Change-Driven Adjustments (revised)

**Status:** Accepted (revised)

## Context

Per-room amount overrides are fraud-prone. Only the organization-wide standard amount should be adjustable.

## Decision

The standard monthly amount is the only adjustable billing parameter. When it changes, every current-month bill of an active tenancy, paid or not, is set to the new amount by a recorded adjustment; if a bill ends up below what is paid, the difference becomes advance. Past months and closed tenancies are never adjusted by a rate change. The new amount applies to all following months; a bill generated late for an ended month takes the amount that was in force at the end of that month.

## Consequences

- Adjustments are uniform, systematic, and transparent.
- Arbitrary per-room overrides are not possible.
