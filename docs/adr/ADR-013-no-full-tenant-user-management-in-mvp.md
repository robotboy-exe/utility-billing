# ADR-013 — No Full Tenant User Management in MVP

**Status:** Accepted

## Context

The product should remain simple.

Full tenant user management is not required initially.

## Decision

Tenants access the portal through tenancy access codes.

The MVP does not implement:

- Tenant passwords.
- Tenant profiles.
- Tenant password resets.
- Tenant self-registration.
- Individual tenant credentials.

## Consequences

- Simpler implementation.
- Lower friction for tenants.
- Less administrative overhead.
- Limited individual accountability.
- Future individual tenant access may require a new ADR.
