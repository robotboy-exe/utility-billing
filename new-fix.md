# Fix ADR Index Table Drift

**Target file:** `docs/03-mvp-architecture.md` (Section 16)
**Source files:** `docs/adr/ADR-001-*.md` through `docs/adr/ADR-027-*.md`

**The Problem:** The ADR index table in Section 16 contains abbreviated/summarized titles that do not exactly match the authoritative H1 headings inside the individual ADR files. 

**The Fix:**
1. Read every file in `docs/adr/` from ADR-001 to ADR-027.
2. Extract the exact H1 heading from each file (e.g., `# ADR-013 — No Full Tenant User Management in MVP`). **This H1 heading is the absolute source of truth for the title.**
3. Extract the Status (Accepted, Superseded, etc.) from each file.
4. Overwrite the Markdown table in Section 16 of `03-mvp-architecture.md`.
5. The new table must have these columns: `| ADR | Title | Status | Summary |`
6. **Crucial Rule:** The "Title" column must be an **exact, 1:1 copy** of the H1 heading from the file (stripped of the `# ADR-XXX — ` prefix). Do NOT abbreviate, summarize, or shorten the titles for the table. 
7. The "Summary" column can remain a concise 1-sentence summary of the decision.

Execute this programmatically to guarantee 100% alignment between the index and the source files. Do not manually type the titles.