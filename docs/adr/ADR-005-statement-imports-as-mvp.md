# ADR-005 — Statement Imports as MVP

**Status:** Superseded by ADR-014

## Context

The MVP needs an initial transaction ingestion mechanism to get financial data into the system without building complex real-time integrations.

## Decision

CSV and XLSX statement imports were initially selected as the primary transaction ingestion mechanism for the MVP.

*(Note: This decision was later superseded by **ADR-014**, which established the Payvice Avantus PDF as the primary ingestion source due to the billing software's export limitations. CSV and XLSX remain available as secondary sources where practical).*

## Consequences

- The initial architecture focused on tabular data parsing.
- The system retains the Import Profile abstraction, allowing the pivot to PDF (ADR-014) without rewriting the core ingestion pipeline.
