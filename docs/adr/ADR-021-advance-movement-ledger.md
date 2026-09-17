### ADR-021 — Advance Movement Ledger and Reconciliation

Status: Accepted.

Context:

Advance credit is derived from payments and allocations. To make it auditable and tamper-evident for fraud detection, an independent append-only record is needed.

Decision:

The advance balance remains derived and is never stored as a mutable value. Every advance event (created, applied, reversed) is written to an append-only advance movement ledger in the same transaction as the corresponding allocation. The system reconciles the derived balance against the movement ledger, and any mismatch is flagged as an integrity error.

Consequences:

- Advance credit is auditable and tamper-evident.
- No second mutable source of truth is introduced.
- Reconciliation provides fraud detection.
