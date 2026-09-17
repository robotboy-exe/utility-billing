### ADR-023 — No Per-Room Overrides; Rate-Change-Driven Adjustments

Status: Accepted.

Context: Per-room amount overrides are fraud-prone. Only the global standard amount should be adjustable.

Decision: The standard monthly amount is the only adjustable billing parameter. When it changes, unsettled current-month bills are adjusted by the delta via recorded adjustments. Settled bills and past months are never adjusted.

Consequences: Adjustments are uniform, systematic, and transparent. Arbitrary per-room overrides are not possible.
