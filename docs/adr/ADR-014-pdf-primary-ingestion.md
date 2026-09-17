# ADR-014 — PDF Statement Import as Primary MVP Ingestion Source

**Status:** Accepted

## Context

The billing software that settles the utility bills exports statements only as PDF. PDF is therefore more important than CSV, XLSX, or Google Sheets. The original architecture and MVP v0.2.0 deferred PDF parsing.

## Decision

PDF import is a must-have MVP feature and the primary transaction source. It is implemented as a PDF import profile for the Payvice Avantus export format. MVP supports text-based PDFs only (no OCR). Imports are staged with admin preview and confirmation before transactions are committed. File size and page limits apply to fit free-tier hosting.

## Consequences

- The Transaction Ingestion module carries real parser complexity and needs strong test coverage.
- Sample PDFs from the billing software are on the critical path for design and testing.
- Free-tier CPU/memory limits shape parser library choice and upload limits.
- Extracted rows are retained per import batch for audit and re-parse; PDF binaries are not retained by default.
- Scanned PDFs require manual entry or a future OCR decision.
