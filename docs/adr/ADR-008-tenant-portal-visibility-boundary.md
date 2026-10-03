# ADR-008 — Tenant Portal Visibility Boundary (revised)

**Status:** Accepted (revised)

## Context

Tenants need secure access to billing information without exposing other tenants' personal or transaction details.

In a small property a room label identifies a person, so per-room arrears are personal data.

## Decision

The privacy boundary is the tenancy.

- Members of the same tenancy see full tenancy details.
- Tenants in other rooms of the same property see property-level aggregates by default
  (total outstanding debt, fully-paid room count and ratio, per ADR-027) and org-wide
  rate-change notices.
- Per-room amount due and billing status of other rooms are hidden by default. The
  admin may enable them per organization or property through `portal_setting`
  (`allow_other_room_amount_due`). Tenants cannot opt themselves or others in or out.
- Room-specific adjustments, including write-offs, are never shown to other rooms.
- Tenants cannot see information from other properties.
- Admin can see everything.

## Consequences

- The backend must enforce tenancy and property scopes.
- The visibility policy must be server-side.
- Future visibility changes can be introduced through policy configuration.
- Before enabling per-room detail, check Nigerian data-protection requirements with
  qualified counsel.
