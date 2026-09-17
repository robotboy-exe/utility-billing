# ADR-001 — Organization as Root Entity

**Status:** Accepted

## Context

The application serves landlords and property managers and must support multiple
customers. A top-level boundary is needed to isolate each customer's data, enabling
the same codebase to serve multiple customers (multi-tenant SaaS) as well as
dedicated and standalone deployments.

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
