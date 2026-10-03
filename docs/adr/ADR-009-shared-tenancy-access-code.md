# ADR-009 — Shared Tenancy Access Code (revised)

**Status:** Accepted (revised)

## Context

Tenants need secure read-only access without full user management.

## Decision

Each tenancy uses a shared access code.

Roommates in the same tenancy may use the same code.

Multiple concurrent sessions are allowed.

Sessions are issued per device/browser.

Resetting the access code invalidates existing sessions.

For the MVP:

- The server generates the code, with at least 40 bits of entropy, hashed at rest with
  the same function as admin passwords. The admin cannot choose it.
- Login is scoped: the tenant selects a room and the code is verified only against that
  room's active tenancy. Codes are never assumed unique and never looked up globally.
  Failures return one generic error.
- Rate limiting is stored in the database, counted per tenancy and per source IP, with
  a lockout (initial defaults: 5 failures per 15 minutes, 15-minute lockout; confirmed
  later in the security doc).
- Sessions use a random token of at least 128 bits, hashed at rest, with a fixed absolute
  expiry (initial default 30 days, never extended on use).

## Consequences

- The system cannot identify individual tenants by session.
- Tenant portal actions are limited to read-only operations.
- Access code reset is the primary revocation mechanism.
- Individual tenant credentials may be added later if required.
- Login attempts need persistent storage (`tenant_login_attempt` in 04).
- Closing a tenancy deactivates the credential (ADR-026).