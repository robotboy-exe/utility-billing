# ADR-012 — Free-Hosting Synchronous MVP

**Status:** Accepted

## Context

The MVP is expected to run on free-tier hosting.

Free hosting may not support background jobs, cron jobs, persistent local files, or reliable email delivery.

## Decision

The MVP avoids:

- Background workers.
- Scheduled tasks.
- Webhooks.
- Email dependencies.
- Persistent uploaded file storage.

Admin-triggered synchronous operations are used for:

- Statement import.
- Transaction matching.
- Bill generation (lazy/rolling, triggered by real usage rather than a scheduler).
- Payment allocation.

## Consequences

- The system must tolerate cold starts.
- Imports must be small enough to process synchronously.
- Original statement files are not retained by default.
- Export functionality is used as a backup strategy.
