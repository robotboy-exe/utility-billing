# ADR-006 — Future Event-Driven Integrations (revised)

**Status:** Accepted (revised)

## Context

Real-time payment notifications and bank transaction alerts are highly desirable for a production billing system. However, building secure, reliable webhook receivers and managing retries is out of scope for the synchronous, free-tier hosted MVP.

## Decision

Paystack and Monnify webhooks are planned future transaction sources and are deferred. Where and how they are hosted is a future deployment decision.

## Consequences

- Webhook handling is deferred from the MVP but remains architecturally accommodated via the Transaction Source Abstraction (ADR-004).
- Future webhook processing must be safe to retry, idempotent, and securely validate incoming signatures.
- The MVP relies on PDF statement import and manual entry (ADR-014) until event-driven integrations are built.
- Future ingestion should reuse the duplicate-detection model in `06-transaction-ingestion.md` §18, and billing logic stays independent of where ingestion runs (ADR-007).
