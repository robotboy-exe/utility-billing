Verify that the ADR library is complete and perfectly aligned with the active architecture document.

Source of Truth (Manifest): Section 16 "Architectural Decision Records (ADR Index)" in
`docs/03-mvp-architecture.md`. This table is the authoritative list of all 27 ADRs,
their exact Titles, and their current Statuses.

Target Files: `docs/adr/ADR-001-*.md` through `docs/adr/ADR-027-*.md`.

For EACH of the 27 ADRs listed in the Section 16 index, verify:
1. File Presence: A corresponding file exists in `docs/adr/`.
2. Title Match: The file's H1 heading (`# ADR-XXX — Title`) exactly matches the 
   "Title" column in the Section 16 index table.
3. Status Match: The file's `**Status:**` line exactly matches the "Status" column 
   in the Section 16 index table (e.g., ADR-005 should match the index's "Superseded" status).
4. Structural Completeness: The file contains the three required H2 sections: 
   `## Context`, `## Decision`, and `## Consequences`.
5. No Truncation: None of the three H2 sections are empty or cut off mid-sentence.

Produce a verification report as a table:

| ADR | File Exists | Title Match | Status Match | Structure Valid | Not Truncated | Verdict |

Mark each cell PASS or FAIL. The final Verdict is PASS only if every column for that 
ADR is PASS.

At the end, give an overall result:
- "ALL 27 ADRs VERIFIED AND ALIGNED" if every row is PASS, or
- a list of exactly which ADRs failed and the specific mismatch or truncation.

Do NOT modify any files during this verification. Read-only.