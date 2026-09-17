# ADR-006 — Future Event-Driven Integrations

**Status:** Accepted

## Context
Real-time payment notifications and bank transaction alerts are highly desirable for a production billing system. However, building secure, reliable webhook receivers and managing retries is out of scope for the synchronous, free-tier hosted MVP.

## Decision
Paystack and Monnify webhooks are planned future transaction sources. Serverless functions may be used for webhook ingestion where appropriate to handle spikes in traffic and ensure reliable delivery to the core database.

## Consequences
- Webhook handling is deferred from the MVP but remains architecturally accommodated via the Transaction Source Abstraction (ADR-004).
- Future webhook processing must be safe to retry, idempotent, and securely validate incoming signatures.
- The MVP relies on manual/batch statement imports (ADR-005, ADR-014) until event-driven integrations are built.