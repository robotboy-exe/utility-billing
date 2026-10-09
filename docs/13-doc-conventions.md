# Documentation Versioning Policy

Document: `docs/13-doc-conventions.md`
Version: `0.3.0`
Status: Consolidated source of truth
Last Updated: 2026-10-09
Related documents: `03-mvp-architecture.md`, `04-database.md`, `05-billing-engine.md`, `06-transaction-ingestion.md`, `changelog-03.md`
Audience: human editors and AI agents (opencode / spec-kit).

Changes in this version: ADR policy now allows in-place revision — superseded ADRs stay frozen (only the status line may change) while every other ADR may be edited, marking the H1 with ` (revised)`, setting Status to `Accepted (revised)`, and stating the reason in the commit; whitespace-only fixes are not revisions. The retire form is plain `Status: Retired`, with the pointer living in `Supersedes:` and the changelog. Invariant 4 is reworded to scope exactly one `Changes in this version:` line to each detail-doc header.

---

## 1. Scope and identifiers
- Numbered design docs (`docs/00-…` … `docs/13-…`) are versioned **independently**.
  There is no repo-wide or suite-wide version.
- ADR files (`docs/adr/ADR-NNN-slug.md`) are **unversioned** records (§6).
- Retired/absorbed documents carry `Status: Retired` and are named in the absorbing
  document's `Supersedes:` line and in the changelog. They are never bumped again.

## 2. Version format
`MAJOR.MINOR.PATCH`, plain integers, no suffixes.
- All documents sit at `0.x.y` while `Status: Draft` (design phase).
- **MAJOR** is reserved: bump to `1.0.0` only when a document is re-baselined against
  an implemented system (implementation freeze / first release) or after a breaking
  rewrite that invalidates prior external references.
- **MINOR** = a new or changed design decision (§3).
- **PATCH** = expression-level change only (§4).

## 3. MINOR bump — new or changed decision
Bump the middle digit when the change alters what the system must do, store, or guarantee:
- New feature, mechanism, table, column, enum value, or invariant adopted as a decision.
- A decision that **extends or creates** a convention (e.g. deciding `import_batch`
  control totals are money-bearing and therefore carry `currency`).
- Absorbing, retiring, or superseding another document.
- Structural refactor (section reorg, extracting content to new files, role change).
- Resolving an open question in a way that locks a **new** decision.
- Reopening or amending a locked rule (also subject to §6).

## 4. PATCH bump — expression only
Bump the last digit when no decision changes:
- Consistency reconciliation (making prose match an already-locked rule or ADR).
- **Enforcing an already-stated convention** somewhere it was missing (e.g. adding
  `currency` columns that §3.5 already mandated; filling timestamp gaps §3.2 required).
- Clarifications, terminology scoping, grammar/typo fixes, stray-marker removal.
- Cross-reference, index, ER-diagram, or metadata repairs.
- Recording a resolution that was already decided elsewhere (e.g. in an ADR).

## 5. The boundary test
Ask: *"Does this change what the system must do, or only how an already-locked
decision is expressed?"*  Must-do → MINOR. Expression → PATCH. Re-baseline → MAJOR.
Worked boundary case: adding `currency CHAR(3) NOT NULL` to the five money tables was
**PATCH** (04 0.3.2) because §3.5 already required it — the change enforced a stated
convention. Adding `currency` to `import_batch` was **MINOR** (04 0.4.0) because it
answered a new question and extended the convention. Same column, different bump:
the difference is whether a decision was made.

## 6. ADR policy (unversioned)
- ADR files carry **no `Version:` field, ever**. Identity = number + slug; authority = Status.
- Superseded ADRs are frozen; only the status line `Superseded by ADR-N` may change.
- A wholly replaced decision gets a new ADR, and the old ADR's Status becomes `Superseded by ADR-N` (e.g. ADR-014 supersedes ADR-005).
- Superseded ADRs keep their file and number; they are never deleted or renumbered.
- Every other ADR may be edited in place. Any content edit (including retitles and wording
  fixes) adds ` (revised)` to the H1, sets Status to exactly `Accepted (revised)`, and states
  the reason in the commit message.
- Whitespace-only fixes (e.g. EOF newline) are not revisions.
- The ADR index table in `03-mvp-architecture.md` §16 is the manifest: Title and Status
  cells must match each ADR file's H1 and Status exactly. Summary cells may be
  abbreviated paraphrases (accepted, intentional drift).

## 7. Header metadata (required on every numbered doc)
```
Document: `docs/NN-name.md`
Version: `X.Y.Z`
Status: <Draft — design phase | Consolidated source of truth | Retired>
Last Updated: YYYY-MM-DD
Related documents: <list>
Supersedes: <predecessors>        ← only where applicable
```
- `Version` and `Last Updated` are refreshed **together** on every bump; never one alone.
- Untouched documents keep their version and date untouched. Do not bump a doc you did not change.
- `Supersedes:` is a plain comma-separated list of filenames of documents that still exist in
  the repo as `Status: Retired`. Omit the line when there are none. The provenance narrative
  lives in the changelog, never in the header.

## 8. Change records — two flavours by document role
- **Detail docs (04, 05, 06, future 07–12):** a single `Changes in this version:` line in
  the header, **overwritten** each bump to describe only the current delta. May say
  "Carried forward from X.Y.Z: …". Older deltas live in git, not in the file.
- **03 (the project's architecture document):** carries **no** `Changes in this version:` line and **no**
  `Document Lineage` section. Its change record is the companion file `docs/changelog-03.md`:
  append-only, one entry per bump in the form `Version X.Y.Z <decision-level summary>.`
  Prior entries are never edited or removed; the file runs oldest first. The companion is not
  a numbered document, so §7 headers and invariants 1 and 2 do not apply to it.
- **13 (this document):** the detail-doc flavour — a single `Changes in this version:`
  line, overwritten each bump. Its §12 table is a frozen snapshot of 03–06's bump
  history at 13's creation and is never amended.
- Every bump ships a change record. A bump with no written record is a policy violation.
A document is **never** bumped to mirror another document's version change.
Version histories travel in each doc's own change record plus git history (§9),
never in another doc's body. Reference tables that mirror sibling numbers
(13 §12, ADR indexes) are frozen once their owning document is created. Registering
a newly-created document in a referencing doc's index (e.g. adding `13-doc-conventions`
to 03's tree) is a PATCH-level expression fix in that referencing doc — never
coordination through 13.

## 9. Multi-document passes and git
- A pass may touch several docs; bump each touched doc independently per §3–§5, each with
  its own change record and date.
- One commit per pass is fine. Commit message lists the bumps:
  `docs: <summary> (03→0.8.2, 04→0.3.2, 05→0.3.2)` plus bullets.
- Versions track **committed** state: reverting a commit reverts the numbers with it.
  Do not bump mid-pass; bump + record + commit as one unit.

## 10. Conflict arbitration
- On contradiction between documents, the ADR library and the locked-rules checklist
  (03 §19) win over prose; the losing prose is corrected and bumped (PATCH if it merely
  realigns with an existing decision).
- After any pass, run a residue/consistency check: grep for superseded terms, verify
  index-vs-ADR fidelity, verify cross-references resolve.

## 11. Machine-checkable invariants (for agents / CI)
1. Every numbered doc header matches §7; `Version` matches `^\d+\.\d+\.\d+$`.
2. `Last Updated` is a valid ISO date equal to the last bump commit touching that file.
3. `03` contains neither `Document Lineage` nor `Changes in this version`; `docs/changelog-03.md` exists, and
   across commits its earlier content is only ever extended at the end.
4. Exactly one `Changes in this version:` line in each detail-doc header.
5. No file under `docs/adr/` contains a `Version:` line.
6. ADR index Title/Status cells equal the ADR files' H1/Status.
7. Any commit changing a doc's body also changes its `Version` and change record in the
   same commit (no silent edits, no silent bumps).
8. Untouched docs are absent from the commit.
9. `13-doc-conventions.md` §12 is frozen: no commit adds to or edits it, and
   `13`'s bumps appear only in its overwritten `Changes in this version:` line.
10. A commit that bumps 03 appends exactly one new entry to `changelog-03.md` and changes
    nothing earlier in it.

## 12. Worked history (reference — frozen, do not amend)

Snapshot of other numbered documents' bump history (03–06) as it stood when this
document was created; it documents the numbered docs, not 13, and it is never
amended. Future bump history lives in git history (§8).
| Doc | Bump | Type | Reason |
|---|---|---|---|
| 03 | 0.4.0→0.5.0 | MINOR | advance movement ledger + reconciliation invariant added |
| 03 | 0.5.0→0.6.0 | MINOR | billing/tenancy product decisions locked |
| 03 | 0.6.0→0.7.0 | MINOR | absorbed `utility-billing-arch.md`; base doc retired |
| 03 | 0.7.0→0.8.0 | MINOR | leanness refactor; ADRs extracted to `docs/adr/` |
| 03 | 0.8.0→0.8.1 | PATCH | locked rules reconciled with ADR library |
| 03 | 0.8.1→0.8.2 | PATCH | org-wide standard amount; foreknowledge exemption; stray marker |
| 03 | 0.8.2→0.8.3 | PATCH | comma splice; softened visibility-config claim |
| 04 | 0.3.0→0.3.1 | PATCH | ER diagram + immutability lists + scope note |
| 04 | 0.3.1→0.3.2 | PATCH | currency on five tables, timestamp gaps, reversed semantics (enforcing stated conventions) |
| 04 | 0.3.2→0.4.0 | MINOR | import_batch currency = new decision; global/system-wide scoping |
| 05 | 0.1.0→0.2.0 | MINOR | advance movement ledger |
| 05 | 0.2.0→0.3.0 | MINOR | rolling generation; per-room override removal; partial-month asymmetry |
| 05 | 0.3.0→0.3.1→0.3.2 | PATCH | consistency passes |
| 06 | 0.2.0→0.2.1 | PATCH | consistency; unchanged while 03/04/05 moved |
| — | 0.8.4/0.4.1/0.3.3/0.2.2 | reverted | deleted commit; reset rolled numbers back (versions track committed state) |

## 13. New and retired documents
- A newly authored numbered doc starts at `0.1.0`.
- Retiring: set `Status: Retired`, stop bumping, and record the absorption in the
  absorbing doc's `Supersedes:` line (when the file exists) and the changelog. Never
  delete a retired doc silently in the same commit as a content change.

## 14. Agent operating instructions (spec-kit / opencode)
Before editing any numbered doc: read its header; classify your change via §5; after
editing, bump accordingly, refresh `Last Updated`, write the change record in the correct
flavour (§8), and leave every untouched doc's header alone. Never add a version to an ADR.
Never change an Accepted ADR's Decision meaning on your own initiative. It requires owner
approval and either a new superseding ADR or an in-place revision using the form in §6. If
a change would contradict a locked rule or an ADR, stop and raise a decision request rather
than editing prose around it.
