<!--
SYNC IMPACT REPORT (temporary scratch — remove before committing)
Version change: 0.0.0 (unversioned template) → 1.0.0
Modified principles: (none — initial adoption)
Added sections: Core Principles; Database & Schema Discipline; Tech Stack &
  Deployment Constraints; Governance
Removed sections: (none)
Deferred TODOs:
  - OPEN QUESTION: no explicit constitution versioning policy or compliance
    review cadence is decided in the docs — fill in governance once decided.
-->
# Utility Billing Constitution

## Core Principles

### I. Financial Correctness and Immutable History (NON-NEGOTIABLE)
All monetary amounts MUST be stored as integer minor units (BIGINT) with an
explicit currency column. Floating-point arithmetic MUST NOT be used for money.
Financial records — transactions, payment allocations, advance movements, bill
adjustments, standard-amount changes, utility bill payments, and audit logs — MUST
be append-only. Corrections MUST be represented through recorded reversals or
correction entries, never silent rewrites or hard deletes. The billing engine MUST
be the final authority on derived financial state (which bill a payment settles,
balances, advance credit); no other module overrides it except through controlled
corrections.
Rationale: Money handling is the highest-risk module. Deterministic, auditable,
tamper-evident history is required for correctness and fraud detection (ADR-017,
ADR-021, ADR-025).

### II. Billing Engine Independence
The billing engine MUST operate on domain-level data only and MUST NOT depend on
transaction source (PDF/CSV/XLSX), the frontend, the API, the ORM, or external
integrations. Every transaction source MUST be normalized into a common transaction
model at the ingestion boundary before entering billing logic. Adding a transaction
source, utility provider, or category mapping MUST NOT require changes to the
billing engine.
Rationale: Isolating financial logic keeps it testable in isolation and prevents
ingestion or UI churn from introducing bugs into allocation (ADR-004, ADR-007).

### III. Ingestion Reliability and Integrity
Imports MUST be staged and admin-confirmed before any financial records are
committed; no record is written without review. Duplicate detection MUST prevent
re-importing the same statement and the same transaction row. Control totals MUST
be validated, and a mismatch MUST NOT be silently ignored. Commission rows MUST be
fully discarded — never stored, displayed, counted, logged, or reported. Category
mapping and utility providers MUST be configuration- and registry-driven, not
hardcoded in the parser or billing engine.
Rationale: Ingestion is the trust boundary; validated, idempotent, staged intake
prevents corrupt or duplicated financial data (ADR-014, ADR-015, ADR-016, ADR-019).

### IV. Two-Ledger Separation
The Tenant Payment Ledger and the Utility Bill Payment Ledger MUST remain strictly
separate and MUST never settle each other. Utility bill payments MUST NOT enter
tenancy matching and MUST NOT reduce tenant balances; tenant payments MUST NOT count
as provider payments. Only matched tenant payments MUST enter billing allocation.
Rationale: Keeps tenant billing state clean and makes provider payments a pure
spend / proof-of-payment record (ADR-017).

### V. Test-First Financial Logic
Financial allocation, advance-ledger reconciliation, and ingestion parsing edge
cases MUST have extensive automated test coverage. Any change to billing,
allocation, or ingestion logic MUST ship with tests. The advance reconciliation
invariant (derived balance vs. movement ledger) MUST be covered by tests.
Rationale: The engine is deterministic and testable in isolation; regressions in
money handling are unacceptable (ADR-014; testing focus in 03 §15, 05 §16, 06 §26).

## Database & Schema Discipline

- PostgreSQL for production; SQLite for local development only.
- Primary keys MUST be UUIDs. All scoped queries MUST filter by `organization_id`
  (and `property_id` / `tenancy_id` where relevant). Access and visibility
  enforcement MUST happen server-side.
- Every schema change MUST ship as an Alembic migration, reversible where practical.
- Derived state (bill status, advance balance, outstanding balance) MUST be computed
  from authoritative records; derived values MUST NOT be stored as independently
  mutable fields (04 §7).
- The immutable (append-only) vs. mutable table classification in 04 §11 MUST be
  respected: corrections on financial tables use reversal/correction records.
- Bill amount changes MUST be audited: any change to `monthly_bill.final_amount_minor`
  MUST have a corresponding `bill_adjustment` row.

## Tech Stack & Deployment Constraints

- Frontend: React + TypeScript + Vite. The frontend MUST NOT contain authoritative
  financial business logic.
- Backend: Python + FastAPI, with SQLAlchemy for the data layer. Money is handled
  and validated in the backend.
- Deployment matches free-tier hosting: no background workers, no scheduled jobs,
  no persistent local file storage, and no email or webhook dependency. Imports and
  matching are admin-triggered and synchronous; bill generation is lazy/rolling.
- Business logic MUST NOT depend on the chosen hosting provider
  (deployment-model independence — SaaS, dedicated, or standalone).
- Original statement PDF binaries MUST NOT be retained by default; export
  functionality is the backup strategy.

## Governance

This constitution supersedes informal practice and states the non-negotiable rules
for the Utility Billing MVP. Amendments are enacted through the Architecture
Decision Record (ADR) process (03 §16); each accepted ADR that constrains how code
is written SHOULD be reflected here as a rule. Pull requests that touch billing,
ingestion, or database code MUST demonstrate compliance with the relevant
principles above.

- **Version bumps:** Constitution versions follow the MAJOR/MINOR/PATCH boundary
  test in `docs/13-doc-conventions.md` §5, applied to principles and governance
  rules: removing or redefining a principle = MAJOR, adding a principle = MINOR,
  wording-only clarification = PATCH.
- **Compliance review:** Compliance with this constitution MUST be reviewed before
  `/speckit.plan` on any major new feature and whenever the constitution is amended.
  There is no fixed calendar schedule.
- **Amendment authority:** Amendment approval authority rests solely with the
  project owner. This is a solo project; there is no approval body distinct from
  ADR acceptance authority.

**Version**: 1.1.0 | **Ratified**: 2026-09-16 | **Last Amended**: 2026-09-18
