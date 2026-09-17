# ADR-019 — Commission Rows Fully Excluded

**Status:** Accepted

## Context

Commission rows are agent income and must never enter the system.

## Decision

Commission rows are discarded during parsing.

They are not stored, counted, displayed, logged, or reported.

## Consequences

- The parser recognizes commission rows only to discard them.
- No commission data persists anywhere.
- Control-total validation may transiently account for commissions without retaining them.
