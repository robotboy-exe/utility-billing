# ADR-016 — Utility Provider Registry

**Status:** Accepted

## Context

BEDC is the first utility provider, but future bill types are expected.

## Decision

Utility bill payments are recorded through a provider registry.

BEDC is the first registered provider.

Future bill types and providers can be added without hardcoding.

## Consequences

- Provider data is registry-driven.
- Adding a provider does not require billing-engine changes.
