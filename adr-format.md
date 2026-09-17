# Blanket Formatting Prompt — All ADR Files (001–027)

**Target directory:** `docs/adr/`
**Applies to:** All 27 files, `ADR-001-organization-root.md` through `ADR-027-property-dashboard-metrics.md`

## Objective

Normalize every ADR file to the same structure. No exceptions, no special cases.

## Target Format

Every file must follow this exact structure:

```markdown
# ADR-XXX — Title

**Status:** [Status value]

## Context

[One or more paragraphs explaining why this decision was needed.]

## Decision

[One or more paragraphs stating what was decided.]

## Consequences

[One or more paragraphs or bullet points stating what follows from this decision.]
```

## Rules

1. **Title line** must start with `# ` (H1) followed by `ADR-XXX — Title`.
2. **Status** must be bold: `**Status:**` followed by the value (`Accepted`, `Superseded by ADR-XXX`, etc.).
3. There must be exactly three H2 sections: `## Context`, `## Decision`, `## Consequences`.
4. Preserve all existing content and meaning. Do not invent new information.
5. If a file currently lacks Context or Consequences, derive them from the existing prose and the surrounding architecture documentation (`03-mvp-architecture.md`). Do not fabricate.
6. If a file already has Context, Decision, and Consequences, only adjust the markdown structure to match the target format.
7. Do not change the ADR number or title.
8. Do not reorder or merge ADRs.

## Verification

After formatting all 27 files, confirm:

1. All 27 files exist in `docs/adr/`.
2. Every file starts with `# ADR-XXX — Title`.
3. Every file has `**Status:**` as the second non-blank line.
4. Every file has exactly three `##` headings: Context, Decision, Consequences.
5. No file uses the old plain-text labels (`Context:`, `Decision:`, `Consequences:` without `##`).
6. All original content is preserved.