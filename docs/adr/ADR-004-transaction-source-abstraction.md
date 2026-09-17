# ADR-004 — Transaction Source Abstraction

**Status:** Accepted

## Context

The application needs to ingest financial transactions from a variety of external sources. These sources have different formats, data structures, and delivery mechanisms (e.g., CSV, XLSX, PDF statements, payment gateways, bank APIs, manual entry). The core business logic (billing, matching, allocation) must not be tightly coupled to the specifics of any single ingestion source.

## Decision

All transaction sources must normalize into a common transaction representation before entering the core business logic.

The system uses an abstraction layer (Import Profiles / Source Parsers) that takes raw source data and outputs a standardized `Transaction` domain object.

## Consequences

- Adding a new transaction source (e.g., a new bank's PDF format or a new payment gateway) does not require modifications to the billing engine or matching logic.
- Sources are pluggable behind a standard transaction model.
- Validation, duplicate detection, and normalization happen at the ingestion boundary.
