# Research: Tenant Billing Engine (Phase 0)

**Feature**: `002-billing-engine` | **Date**: 2026-10-16 | **Spec**: [spec.md](spec.md)

This document resolves the Technical Context unknowns for implementing `docs/05-billing-engine.md` on the existing schema (`docs/04-database.md`). It records *how* the engine is structured, not *what* the engine must do (that is `docs/05`, cited by section). The engine adds **no schema change**.

**Scope guard**: no utility spend, parsing, portal visibility, auth, or API/UI ships here (`docs/05` §1–§2; spec Out of Scope).

## Required decisions

### R-1 — Pure domain core split from a single persistence adapter

- **Decision**: the billing algorithms live in a pure package (`domain.py`, `clock.py`, `engine.py`, `status.py`, `reconciliation.py`) that imports no SQLAlchemy, ingestion, UI or API code; a single adapter (`repository.py`) owns all reads/writes, the database transaction, and the `docs/05` §6.9 lock order. Reporting joins through a read-only `views.py`.
- **Rationale**: the constitution (Principle II) requires the billing engine to be independent of the ORM and transaction source; making that a module boundary keeps it testable in isolation and prevents ingestion/UI churn from leaking into allocation.
- **Cost of changing later**: moving logic across the boundary after the fact means re-writing tests that assumed the split; the boundary is cheap now and expensive later.
- **Alternatives considered**: ORM-coupled service functions (violates Principle II, hard to unit-test); a separate service process (over-kill for free hosting).

### R-2 — Business timezone via stdlib `zoneinfo`

- **Decision**: month boundaries are computed by a pure `clock.py` helper using `zoneinfo.ZoneInfo(organization.timezone)`; no new dependency (`tzdata` already provides IANA data on the existing dependency set).
- **Rationale**: `docs/03` §10.4 and ADR-028 require all month boundaries in the organization timezone, default `Africa/Lagos`; a pure helper makes boundary behaviour (23:59/00:00, month of an instant, month enumeration) directly testable without a database.
- **Cost of changing later**: touches generation and every monthly grouping; a DB-side equivalent would break SQLite/PostgreSQL parity.
- **Alternatives considered**: computing months in SQL (`date_trunc` with a timezone) — engine-locked and not portable to SQLite; storing a precomputed month on rows — stored derived state.

### R-3 — Deterministic ordering is a pure function

- **Decision**: payment ordering (date/time asc, amount asc, internal id; null time = 00:00 business timezone) and bill ordering (billing month asc) are pure functions over domain objects. No input order is trusted.
- **Rationale**: `docs/05` §6.2 forbids relying on stored row order or import sequence; a pure sort is the smallest unit that proves the rule and is trivially testable.
- **Cost of changing later**: any change alters allocation results and needs re-proving of the §16 scenarios.
- **Alternatives considered**: ordering in SQL with `ORDER BY` per query (duplicated, easy to drift from the business rule).

### R-4 — Idempotent generation against the existing unique constraint

- **Decision**: generation builds the target (tenancy, month) set in memory and inserts bills with conflict-ignore semantics, relying on `UNIQUE (tenancy_id, billing_month)` (`docs/04` §6.5) for idempotence.
- **Rationale**: `docs/05` §5.1 and ADR-022 require idempotent lazy generation; the existing unique constraint already guarantees it, so the engine needs no lock or check-then-insert race handling.
- **Cost of changing later**: a new uniqueness rule would require a migration and re-verification.
- **Alternatives considered**: read-then-insert with an application guard (races); a dedicated generation table (needless).

### R-5 — Advance movements atomic with their allocations

- **Decision**: every allocation the engine writes is accompanied, in the same transaction, by its advance movement (`created` when a remainder forms, `applied` when advance fills a bill, `reversed` only when clearing advance during unmatch); the derived balance is recomputed by a pure `reconciliation.py` and compared with the logged ledger.
- **Rationale**: `docs/05` §7.4 and `docs/04` §7.5/§8.8 require the two to be written atomically and to reconcile; keeping the invariant a pure function makes the mismatch test trivial.
- **Cost of changing later**: the ledger schema and every write path; the identity is load-bearing for fraud detection.
- **Alternatives considered**: a stored mutable advance balance (forbidden by the constitution); best-effort logging (breaks the invariant).

### R-6 — One reversal-to-advance primitive (Samuel's ruling R1)

- **Decision**: a single helper reverses one allocation and appends exactly one `created` advance movement for the reversed amount. Rate drops, reduced-bill corrections, complete reversal and wrong-match correction all call it; nothing appends a `reversed` movement to undo an applied allocation.
- **Rationale**: R1 makes the reconciliation identity hold; a single primitive prevents one code path from drifting to `reversed` and double-subtracting.
- **Cost of changing later**: every correction path changes together; the invariant must be re-proven.
- **Alternatives considered**: per-path inverse logic (the exact drift R1 forbids).

### R-7 — Atomic corrections under the documented lock order

- **Decision**: complete reversal and wrong-match correction run as one transaction in `repository.py`; the adapter locks tenancies ascending by id and open bills `FOR UPDATE` by month before writing, per `docs/05` §6.9. `transaction` rows are never updated.
- **Rationale**: `docs/05` §12.1, §6.9, `docs/04` §8.12 and Samuel's ruling R2 require all-or-nothing writes in that order so no partial correction is observable.
- **Cost of changing later**: the lock order is a cross-module contract with ingestion confirm; changing it risks deadlocks.
- **Alternatives considered**: separate transactions per step (observably partial; forbidden); optimistic retry (no partial-write guarantee).

### R-8 — Derived status and tenancy state are pure functions

- **Decision**: `status.py` computes bill status (with the `final amount = 0` checks first), `was_written_off`, and the tenancy aggregates (two-amount outstanding, advance, net position, overall status) from in-memory domain objects.
- **Rationale**: `docs/05` §8.1–8.4 and §9 define ordinal checks that are cheap and exhaustive to test without a database; `docs/04` §7 forbids storing them.
- **Cost of changing later**: status is consumed by every view; a change needs view re-verification.
- **Alternatives considered**: SQL expression per view (duplicated and engine-locked); a stored status column (forbidden).

### R-9 — Read-only view layer

- **Decision**: `views.py` exposes query functions returning DTOs; it performs no INSERT/UPDATE/DELETE.
- **Rationale**: spec FR-054 / F-03 require that requesting a summary or list cannot change a payment or allocation.
- **Cost of changing later**: low, but any write accidentally added here would violate the read-only rule.
- **Alternatives considered**: reusing write paths for reads (invites accidental mutation).

### R-10 — Freshness date and closed-tenancy views are org-scoped queries

- **Decision**: the freshness data takes the latest `statement_end_date` among `confirmed`/`completed` `import_batch` rows and computes which months ended after it; the closed-tenancy outstanding view returns its own total and a per-tenancy list, org-scoped.
- **Rationale**: `docs/05` §14.4 and §14.5 define precisely what must be shown and that the closed-tenancy total is admin-only and never merged with active outstanding; the engine supplies data, the portal enforces presentation.
- **Cost of changing later**: report formatting is cheap to change; the data contract is the stable part.
- **Alternatives considered**: building the note string inside the engine (delegated to the plan/reporting layer by the runbook).

### R-11 — Testing and database isolation

- **Decision**: pytest with a fresh in-memory SQLite database per test by default, never the development database file; the same suite runs against PostgreSQL when `TEST_DATABASE_URL` is set. Pure-domain algorithms are additionally tested with no database.
- **Rationale**: AGENTS.md and spec `001`'s precedent; runs the whole suite locally with no server.
- **Alternatives considered**: PostgreSQL-only testing (not dev-friendly, violates the local-first convention).

### R-12 — Concurrency tests gated on PostgreSQL

- **Decision**: tests that assert serialized locking under the §6.9 order name `TEST_DATABASE_URL` and skip when it is unset; they run where a PostgreSQL URL exists (CI/deploy).
- **Rationale**: SQLite (via `StaticPool`) serializes writes and cannot demonstrate row-level lock ordering; the runbook requires naming the PostgreSQL condition rather than faking it.
- **Alternatives considered**: asserting lock behaviour on SQLite (meaningless); omitting the test (leaves the contract unproven where it can be).

## Supporting decisions

### R-13 — Domain value objects carry integer minor units

- **Decision**: domain objects expose amounts as `int` minor units and a `currency` string; no `Decimal` or `float`.
- **Rationale**: keeps Principle I structural across the boundary; matches the existing `money()` columns (`docs/04` §3.4).
- **Alternatives considered**: `Decimal` in the domain (adds conversion at the boundary for no benefit at whole-minor-unit granularity).

### R-14 — M1 backfill set is date-derived, not status-derived

- **Decision**: the months a tenancy must be billed for are derived from `[start_date month, end_date month]` inclusive; every month in that range is billed in full by default, and a `skip` override recorded before generation suppresses a month (`docs/05` §5.4). The tenancy's current `status` only decides the running month's eligibility; a `draft` tenancy is never billed (`docs/05` §5.1).
- **Rationale**: Samuel's ruling M1 requires bills through the move-out month even when the tenancy closed and nobody opened the app for months; a status-only rule would miss them.
- **Alternatives considered**: billing only `active` tenancies (rejected by `docs/05` §5.1, which now bills active or closed tenancies through the move-out month).

## Libraries

No library is added. `zoneinfo` and `datetime` are standard library; SQLAlchemy, Alembic, psycopg, `tzdata` and pytest are already in `backend/pyproject.toml`.

## Open questions

No specification question is open. Samuel's ruling S3 fixes the timing: the advance reconciliation runs before commit on every write path that changes a payment's allocations or advance movements, and there is no all-payments check in the MVP; the operational cadence beyond that remains `docs/04` §13 item 6. No new open question is introduced.
