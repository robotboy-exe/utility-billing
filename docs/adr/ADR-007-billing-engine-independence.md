# ADR-007 — Billing Engine Independence (revised)

**Status:** Accepted (revised)

## Context

The billing engine is the core financial business domain of the application. It handles bill generation, payment allocation, advance credit tracking, and balance reconciliation. Because financial correctness is paramount, this logic must be highly testable and isolated from external concerns.

## Decision

The billing engine must remain independent of transaction source, frontend, and API implementation details. It operates strictly on domain-level data (Tenancies, Monthly Bills, Transactions, Allocations).

## Consequences

- The billing engine can be tested independently of the user interface, database ORM, and external integrations.
- API endpoints act as thin adapters that invoke the billing engine; the MVP runs no background workers or scheduled jobs.
- Changes to how transactions are ingested (e.g., adding a new PDF parser) do not risk introducing bugs into the financial allocation logic.
