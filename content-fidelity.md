Verify that the ADR extraction preserved all content completely.

Source of truth: Section 32 "Architectural Decision Records" in
docs/03-mvp-architecture-bloated-archive.md. This contains the full
Context, Decision, and Consequences for ADR-001 through ADR-027.

Cross-reference: Section 16 "ADR Index" in docs/03-mvp-architecture.md
(the v0.8.0 lean doc). This table lists all 27 ADRs with Title, Status,
and a one-line Summary.

Extracted files: docs/adr/ADR-001-*.md through docs/adr/ADR-027-*.md.

For EACH of the 27 ADRs, verify:
1. A file exists in docs/adr/ whose name starts with that ADR number.
2. The file's title matches the title in the Section 16 index table.
3. The file's Status matches the Status in the Section 16 index table
   (note: ADR-005 should read "Superseded by ADR-014").
4. The file contains a complete Context, Decision, and Consequences
   section that matches the wording in Section 32 of the bloated archive.
5. No section is truncated, empty, or cut off mid-sentence.

Produce a verification report as a table:

| ADR | File exists | Title match | Status match | Context complete | Decision complete | Consequences complete | Verdict |

Mark each cell PASS or FAIL. The final Verdict is PASS only if every
column for that ADR is PASS.

At the end, give an overall result:
- "ALL 27 ADRs VERIFIED" if every row is PASS, or
- a list of exactly which ADRs failed and what is missing/truncated.

Do NOT modify any files during this verification. Read-only.