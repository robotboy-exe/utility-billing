### ADR-017 — Separate Tenant Payment and Utility Bill Payment Ledgers

Status: Accepted.

Context:

Tenant payments and provider payments serve different purposes and must not be conflated.

Decision:

Tenant payments populate tenant billing records.

Utility bill payments populate separate provider spend reporting.

The two ledgers do not settle each other.

Consequences:

- Tenant billing state stays clean.
- Provider payments serve as proof-of-payment / spend records.
- Reporting is split into tenant billing and utility spend.
