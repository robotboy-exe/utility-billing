# ADR-001 — Organization as Root Entity (revised)

**Status:** Accepted (revised)

## Context

The application serves landlords and property managers. A top-level boundary is needed to
isolate each customer's data and keep the codebase organization-scoped by design (see
ADR-002).

## Decision

Organizations provide the top-level boundary for customer data.

```text
Organization
    → Property
        → Room
            → Tenancy
                → Tenant
```

## Consequences

All major records are organization-scoped.
Application queries must operate within the authenticated user's organization context.
The Organization abstraction enables the same codebase to support multiple customers.
