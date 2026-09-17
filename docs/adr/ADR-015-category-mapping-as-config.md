### ADR-015 — Category Mapping as Configuration

Status: Accepted.

Context:

Statement rows must be routed to the correct ledger or discarded, and these rules may change.

Decision:

Statement channel rows are mapped to system categories through configuration.

This allows future changes to ignored, recorded, or excluded categories without rebuilding the parser or billing engine.

Consequences:

- Category behavior is data-driven, not hardcoded.
- Future sources and categories can be added through configuration.
