# ADR-003 — Hosting Provider Independence (revised)

**Status:** Accepted (revised)

## Context

The earlier framing assumed three first-class deployment models — multi-tenant SaaS,
dedicated, and standalone — with a rule that core business rules behave identically
across them. The MVP is a single-organization product hosted on one provider
(see ADR-002).

## Decision

Business logic must not depend on the hosting provider or runtime. Hosting differences
are configuration (database URL, secrets, limits), not domain code. The earlier rule
that no behavior may differ by deployment mode is dropped.

## Consequences

- No core business rule may assume a particular host.
- No core business rule may assume a single property.
- Capabilities that exist only in a future multi-organization SaaS (onboarding,
  subscription billing) are outside billing logic and do not affect billing rules
  (see ADR-002).
