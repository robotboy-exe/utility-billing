# ADR-011 — Configurable Tenant Portal Default View

**Status:** Accepted

## Context

The tenant portal should default to property-wide transparency now, but may later default to the room view.

## Decision

The tenant portal supports:

- Property view.
- My Room / My Tenancy view.

The default view is configurable.

MVP default is the property view.

## Consequences

- The frontend should not hardcode the default view.
- Changing the default later should be a configuration change.
- Authorization remains independent of the default view.
