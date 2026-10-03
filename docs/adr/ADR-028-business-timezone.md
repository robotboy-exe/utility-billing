# ADR-028 — Business Timezone

**Status:** Accepted

## Context

Billing months, "current month", lazy generation and utility spend all depend on
calendar-month boundaries, statement timestamps carry no offset, the server runs in UTC
and the users are in Nigeria.

## Decision

Each organization has one IANA timezone, default `Africa/Lagos`. All calendar-month
boundaries (`billing_month`, current month, the month passed to `ensure_bills_through`,
utility spend grouping) are computed in that timezone. Instants are stored as UTC.
Statement timestamps are interpreted in the organization timezone. One timezone per
organization in the MVP, not per property.

## Consequences

- `organization.timezone` exists (04).
- Tests cover month boundaries around 23:59 and 00:00.
- Africa/Lagos has no daylight saving, so another timezone needs that tested.
