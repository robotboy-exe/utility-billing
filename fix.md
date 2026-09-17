# Fix — Section 11 Subsection Numbering

**Target file:** `docs/03-mvp-architecture.md`

**Issue:** Section 11 "Reporting" has leftover subsection numbers from the pre-refactor document (where Reporting was Section 23). The parent section was renumbered to 11 during the v0.8.0 refactor, but the three child headings were not updated.

---

### Edit 52 — Section 11 "Reporting" subsection numbering

**Type:** Replace (3 heading lines)

Find and replace these three exact lines inside Section 11:

| Find | Replace with |
|---|---|
| `23.1 Admin reports` | `11.1 Admin reports` |
| `23.2 Tenant portal reports` | `11.2 Tenant portal reports` |
| `23.3 Utility spend report` | `11.3 Utility spend report` |

**Do not change any content within those subsections.** Only the three heading numbers.

---

### Verification

After applying, confirm:
1. Section 11 contains exactly three subsections: 11.1, 11.2, 11.3.
2. No other section in the document references "23.1", "23.2", or "23.3".
3. All 19 top-level sections are numbered sequentially 1–19 with no gaps or duplicates.