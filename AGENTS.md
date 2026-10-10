# AGENTS.md

## What this repo is
Design-phase (pre-implementation) spec for a tenancy-based utility billing app. There is **no application code** — `docs/` is the source of truth. Do not write app code or scaffolding unless explicitly asked.

## Docs workflow (highest priority)
Every edit to a numbered doc in `docs/` must follow `docs/13-doc-conventions.md`:
- Read the doc's header first; classify the change MAJOR/MINOR/PATCH (13 §5: does it change what the system must do, or only how a locked decision is expressed?).
- Bump `Version`, refresh `Last Updated` (ISO date of the bump), and write the change record **in the same commit**. Never edit a doc without bumping; never bump an untouched doc.
- Flavor by role (13 §8): `03`'s history lives in `docs/changelog-03.md`; other numbered docs keep exactly one overwritten `Changes in this version:` line.
- Frozen: 13 §12 (bump-history snapshot) is never amended. The ADR index (03 §16) is amended only to match each ADR file's H1/Status exactly (13 §6); register new docs via PATCH to the referencing doc's index.
- One commit per pass with bump-list in the message: `docs: summary (03→0.8.2, 04→0.3.2)` (13 §9).
- After any pass run the 13 §10 consistency/residue check and honor the §11 machine-checkable invariants.

## ADRs (`docs/adr/`)
ADRs are unversioned. Superseded ADRs are frozen; any other ADR may be revised in place per 13 §6 (H1 gets ` (revised)`, Status `Accepted (revised)`, reason in the commit message). Never change an Accepted ADR's Decision meaning on your own initiative; it needs owner approval. Index table Title/Status cells must match each file's H1/Status exactly.

## Constitution & governance
- `.specify/memory/constitution.md` (v1.2.1) is the non-negotiable rule set: money stored as integer minor units (BIGINT + explicit `currency`, no floats), append-only financial records (reversals/corrections, no hard deletes), two strictly separate ledgers, billing engine independent of ingestion/UI/ORM, test-first financial logic, PostgreSQL prod / SQLite dev, UUID PKs, Alembic migrations, org-scoped queries.
- Amend via `/speckit.constitution`, not by hand; compliance must be reviewed before `/speckit.plan` on major features (Governance section).

## Spec workflow (speckit)
- Repo uses the speckit SDD cycle with opencode as integration: `/speckit.specify → plan → tasks → implement` with human review gates (`.specify/workflows/speckit/workflow.yml`).
- Read the relevant `/speckit.*` command body in `.opencode/commands/` before running — it contains the exact flow, scope guards, and hooks.
- Derive constitution principles from `docs/` only (per `.specify/memory/constitution-brief.md`); don't invent ungrounded rules.
- `.opencode/` and `.specify/` are generated/versioned infra (checksums in `.specify/integrations/opencode.manifest.json`); don't hand-edit generated templates or manifests.

## Stack & conventions
- Already decided (03 §6): React + TypeScript + Vite frontend (no authoritative financial logic), Python + FastAPI + SQLAlchemy backend, PostgreSQL prod / SQLite local, Alembic migrations. Commissions fully discarded; lazy/rolling bill generation; free-tier hosting (no workers/schedulers).
- Commits use conventional prefixes (`docs:`, `feat:`, `fix:`, `test:`, `chore:`); work happens on `dev`.

End every completed task with a plain-language summary of what changed and what is still open.

## Running tests
- Run tests from the repository root with the project virtual environment: `.venv/bin/python -m pytest tests -q`. Use the default in-memory SQLite database; never point tests at `utility_billing_dev.db`.
- While working on a task, run only that task's tests (`.venv/bin/python -m pytest tests/<file>::<test> -q`). Run the full suite only at a story checkpoint.
- Before marking a task `[x]` in tasks.md, run its tests and show the command and its result. If any test fails, stop and report it: do not mark the task done and do not edit unrelated code.
- Never delete or weaken a test to make it pass.
