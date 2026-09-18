# AGENTS.md

## What this repo is
Design-phase (pre-implementation) spec for a tenancy-based utility billing app. There is **no application code** — `docs/` is the source of truth. Do not write app code or scaffolding unless explicitly asked.

## Docs workflow (highest priority)
Every edit to a numbered doc in `docs/` must follow `docs/13-doc-conventions.md`:
- Read the doc's header first; classify the change MAJOR/MINOR/PATCH (13 §5: does it change what the system must do, or only how a locked decision is expressed?).
- Bump `Version`, refresh `Last Updated` (ISO date of the bump), and write the change record **in the same commit**. Never edit a doc without bumping; never bump an untouched doc.
- Flavor by role (13 §8): `03` keeps an append-only `Document Lineage` (never a `Changes in this version:` line); other numbered docs keep exactly one overwritten `Changes in this version:` line.
- Frozen tables: 13 §12 and the ADR index (03 §16) are never amended; register new docs via PATCH to the referencing doc's index.
- One commit per pass with bump-list in the message: `docs: summary (03→0.8.2, 04→0.3.2)` (13 §9).
- After any pass run the 13 §10 consistency/residue check and honor the §11 machine-checkable invariants.

## ADRs (`docs/adr/`)
Unversioned and immutable. Never add a `Version:` field; never change an Accepted decision's meaning — supersede with a new ADR instead (13 §6). Index table Title/Status cells must match each file's H1/Status exactly.

## Constitution & governance
- `.specify/memory/constitution.md` (v1.1.0) is the non-negotiable rule set: money stored as integer minor units (BIGINT + explicit `currency`, no floats), append-only financial records (reversals/corrections, no hard deletes), two strictly separate ledgers, billing engine independent of ingestion/UI/ORM, test-first financial logic, PostgreSQL prod / SQLite dev, UUID PKs, Alembic migrations, org-scoped queries.
- Amend via `/speckit.constitution`, not by hand; compliance must be reviewed before `/speckit.plan` on major features (Governance section).

## Spec workflow (speckit)
- Repo uses the speckit SDD cycle with opencode as integration: `/speckit.specify → plan → tasks → implement` with human review gates (`.specify/workflows/speckit/workflow.yml`).
- Read the relevant `/speckit.*` command body in `.opencode/commands/` before running — it contains the exact flow, scope guards, and hooks.
- Derive constitution principles from `docs/` only (per `.specify/memory/constitution-brief.md`); don't invent ungrounded rules.
- `.opencode/` and `.specify/` are generated/versioned infra (checksums in `.specify/integrations/opencode.manifest.json`); don't hand-edit generated templates or manifests.

## Stack & conventions
- Already decided (03 §6): React + TypeScript + Vite frontend (no authoritative financial logic), Python + FastAPI + SQLAlchemy backend, PostgreSQL prod / SQLite local, Alembic migrations. Commissions fully discarded; lazy/rolling bill generation; free-tier hosting (no workers/schedulers).
- Commits use conventional prefixes (`docs:`, `chore:`); work happens on `dev`.