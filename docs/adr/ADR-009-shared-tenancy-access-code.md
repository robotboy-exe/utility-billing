# ADR-009 — Shared Tenancy Access Code

**Status:** Accepted

## Context

Tenants need secure read-only access without full user management.

## Decision

Each tenancy uses a shared access code.

Roommates in the same tenancy may use the same code.

Multiple concurrent sessions are allowed.

Sessions are issued per device/browser.

Resetting the access code invalidates existing sessions.

## Consequences

- The system cannot identify individual tenants by session.
- Tenant portal actions are limited to read-only operations.
- Access code reset is the primary revocation mechanism.
- Individual tenant credentials may be added later if required.
