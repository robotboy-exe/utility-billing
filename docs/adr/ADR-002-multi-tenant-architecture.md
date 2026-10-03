# ADR-002 — Multi-Tenant Architecture (revised)

**Status:** Accepted (revised)

## Context

The earlier product direction assumed a commercially viable centralized multi-tenant
SaaS offering with dedicated and self-hosted deployments. The MVP is instead a
single-organization product.

## Decision

The MVP is single-organization and org-scoped by design: every record carries
`organization_id` and every query path filters by it. A dedicated deployment for one
customer is possible because the application is config-driven. Self-hosting is not a
goal. Multi-organization SaaS is deferred.

## Consequences

- A test must fail if any data-access path lacks an `organization_id` filter.
- SaaS later would additionally need self-serve onboarding, multi-user roles,
  subscription billing, isolation tests or Postgres row-level security, and no
  single-organization assumptions in code (for example, nothing may rely on tenant
  access codes being unique across organizations; see ADR-009).
- The commitment to dedicated and self-hosted deployments as first-class models is removed.
