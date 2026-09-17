# ADR-022 — Automatic Rolling Bill Generation (Lazy)

**Status:** Accepted

## Context

Free hosting cannot run scheduled jobs, but billing should feel automatic and rolling.

## Decision

Bills are generated lazily/on-demand the first time the system needs them (dashboard load, payment processing, report request). Generation is idempotent and synchronous, requiring no background scheduler.

## Consequences

- No manual monthly action is needed.
- The "manual generation" point in ADR-012 is revised.
- Reports trigger generation to stay accurate.
