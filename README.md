# Utility Billing

Tenancy-based utility billing and payment ledger application. Pre-implementation design phase.

## Documentation

The `docs/` set is the source of truth for the MVP design:

- `docs/03-mvp-architecture.md` — consolidated architecture, MVP scope, and locked rules.
- `docs/04-database.md` — schema, constraints, indexes, derived state, and invariants.
- `docs/05-billing-engine.md` — allocation, advance credit, adjustments, and corrections.
- `docs/06-transaction-ingestion.md` — Payvice Avantus PDF import, category mapping, and matching handoff.
- `docs/adr/` — Architectural Decision Records ADR-001 through ADR-027 (index in `docs/03-mvp-architecture.md` §16).

Deferred documents (planned, not yet written): `00-project-overview.md`, `01-ai-development-guide.md`, `02-requirements.md`, and `07`–`12`.

Document conventions (numbering, versioning, bump policy): `docs/13-doc-conventions.md`.

## Status

No application code yet. Free-tier hosting constraints and the target deployment shape are described in `docs/03-mvp-architecture.md` §5 and §14.
