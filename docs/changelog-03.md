# 03-mvp-architecture Changelog

Document: companion to `docs/03-mvp-architecture.md` (not a numbered document)

Append-only: add one entry per version bump at the end; never edit or remove earlier entries.
Entry format: `Version X.Y.Z <decision-level summary>.`

## Header provenance as of 0.8.4 (moved verbatim from the 03 header)

Supersedes: `03-mvp-architecture.md` v0.2.0, the PDF scope-promotion amendment, and `03-mvp-architecture-amendment-002.md` (retired; not in repo); absorbs `utility-billing-arch.md` (architecture.md v0.1.0)

## Lineage

This document is the single consolidated source of truth for the MVP architecture. It folds in:

- The original MVP architecture (v0.2.0).
- The PDF scope-promotion amendment, which made Payvice Avantus PDF import the primary ingestion source.
- Amendment 002, which established the two-ledger model, the Payvice Avantus ingestion rules, and the final billing-engine decisions.

Those amendment files are now retired. Any future change should be made here directly or through a new ADR.

Version 0.5.0 adds the advance movement ledger with its reconciliation invariant for fraud auditability, and clarifies that utility providers and import profiles are registered globally (system-wide).

Version 0.6.0 resolves the billing and tenancy product decisions: automatic rolling bill generation, removal of per-room bill overrides in favor of rate-change-driven adjustments and debt write-offs, the move-in/move-out partial-month asymmetry, closed-tenancy portal access, and the property dashboard metrics.

Version 0.7.0 absorbs the base architecture document (`utility-billing-arch.md`), folding in the architectural goals, guiding principles, core modules, transaction flow and source abstraction, deployment models, scalability strategy, and ADR-001 through ADR-007. The base document is retired; this file is now the single architecture source of truth.

Version 0.8.0 refactors the document for leanness: extracts ADRs to `docs/adr/`, collapses domain model and visibility sprawl, replaces detailed billing/ingestion rules with pointers to `05` and `06`, and transforms the locked rules summary into a compact checklist.

Version 0.8.1 reconciles the locked rules with the ADR library: bills are generated lazily only (no manual or scheduled generation), the standard amount has no per-tenancy override, and the visibility matrix is labelled as the configurable default policy.

Version 0.8.2 clarifies that the standard amount is organization-wide (not system-wide), adds the move-out foreknowledge exemption to the partial-month summary, and removes a stray blockquote marker.

Version 0.8.3 corrects a comma splice in the Supersedes line and softens the visibility-matrix config claim to match the example `portal_setting` keys in `04-database.md` §6.8.

Version 0.8.4 registers the doc-conventions policy as numbered document `13-doc-conventions.md` (0.1.0) in the planned document set index and the Written list.

Version 0.9.0 resolves the cross-document review: other rooms see property aggregates by default with per-room detail an admin opt-in; tenant access codes are generated, room-scoped and rate-limited with fixed-expiry sessions; a control-total mismatch or missing footer blocks batch confirmation; lazy bill generation becomes one idempotent function with a fixed caller list and locking rules; one business timezone governs month boundaries (ADR-028); full-data export with a last-exported indicator is an MVP requirement and a file hash replaces PDF retention; CSV and XLSX import leave the MVP; the SaaS, dedicated, self-hosted and webhook sections collapse into one single-organization paragraph and one deferred-integrations section (ADR-002, ADR-003, ADR-006); and the version history moves out of this document into `changelog-03.md`.

Version 0.9.1 registers ADR-028 in the document-set index, mirrors the ADR-022 caller list in the scheduled-tasks response, adds `tenant_login_attempt` to the intentionally-excluded table list, and replaces §12's enumerated immutability list with a pointer to `04-database.md` §11.1; removes the version-history stub.

Version 0.9.2 retitles ADR-002 to Single-Organization MVP Scope and ADR-003 to Hosting Provider Independence, and marks ADR-001 and ADR-007 revised to realign stale Context/Consequences wording with the single-organization, no-background-jobs MVP.

Version 0.10.0 records the MVP hosting choice (Render + Neon, Oracle VM fallback) and registers 10-deployment.md; selection criteria unchanged.
