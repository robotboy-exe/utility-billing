# Deployment

Document: `docs/10-deployment.md`
Version: `0.1.1`
Status: Draft — design phase
Last Updated: 2026-10-10
Related documents: `03-mvp-architecture.md`, `04-database.md`, `06-transaction-ingestion.md`

Changes in this version: Backups are encrypted; static host must serve the app and API from one origin; security open items added. Portability rules match the one-origin setup.

---

## 1. Scope

This document records the outcome of the hosting selection. The selection criteria live in 03 §6.4. Business logic stays independent of the host (ADR-003). The MVP uses free providers only.

## 2. MVP choice

| Layer | Choice |
|---|---|
| Frontend | Static site (host to be chosen; no server-side requirements) |
| Backend | Render free web service (FastAPI) |
| Database | Neon Free (PostgreSQL) |

Fallback: move the backend to an Oracle Cloud VM, with Neon staying as the database. The VM must be a dedicated one with more resources than the existing 1 GB VM, which is reserved for other uses and is not used by this app. The Oracle account would be on Pay As You Go with a budget alert, so idle reclamation does not stop the VM (see §3).

## 3. Provider terms relied on

Checked 2026-10-10. Re-verify before deployment.

- Render free web service: spins down after 15 minutes without inbound traffic; waking takes about a minute; 750 free instance hours per workspace per month, shared by all free services in the workspace; ephemeral filesystem; Render may restart a free service at any time.
- Neon Free: 0.5 GB storage per project (an increase to 1 GB was reported but not confirmed); 100 CU-hours per project per month; compute suspends after 5 minutes idle and this cannot be disabled; 6-hour restore history window; 5 GB public network transfer per month.
- Oracle Always Free (fallback): an instance may be reclaimed if idle over a 7-day period (CPU and network below roughly 15%); converting to Pay As You Go is reported to prevent stopping, and Always Free resources stay uncharged after upgrading. Confirm both on Oracle's current documentation.

## 4. Known limitations (accepted for the MVP)

1. The first request after 15 idle minutes may take about a minute, plus a Neon wake-up after 5 idle minutes.
2. Free Render hours are shared. Do not run keep-alive pings: a service kept awake uses nearly the whole monthly pool.
3. The Neon Free restore window is 6 hours and is not a backup (§6).
4. Free tiers carry no uptime guarantee.

Frontend handling (implementation note): on page load, send one request to a lightweight health endpoint that runs `SELECT 1`; show a "waking up the server" message after about 3 seconds without a response; use a first-call timeout of 90 seconds or more and retry on timeouts and gateway errors; submit buttons show a connecting state. No timer-based pings. A proxy in front of a sleeping backend may return a gateway timeout for the first request; the retry rule above covers this.

## 5. Exit triggers

Move to a paid option when users or the admin complain about the wake-up delay, or when the app is used regularly. In-place options: a paid Render instance (no spin-down) or Neon's paid plan (scale-to-zero can be disabled). Other option: the Oracle fallback in §2. Re-check prices and terms at that time.

## 6. Backups and restore

- An automated, scheduled `pg_dump` is required. Frequency and retention are set when the mechanism is chosen.
- Backups are stored outside Neon and outside the backend host.
- The scheduler runs outside the application, because the MVP runs no background workers or scheduled jobs (ADR-012).
- Use a direct (non-pooled) connection for `pg_dump` and migrations (verify against Neon's documentation).
- A restore into a fresh PostgreSQL, followed by the app's tests, is rehearsed before launch and after any provider change.
- This is separate from the admin full export (03), which stays an application feature.
- PDFs are never retained (constitution 1.2.1), so no file backup is needed.
- Backups are encrypted before they leave the host; encryption keys are stored separately from the backup files; restore tests use an isolated database (09 §13).

## 7. Portability rules

1. Standard PostgreSQL only: no provider-specific features (branching, platform APIs, persistent disks).
2. Provider-specific values come from settings and environment (`DATABASE_URL`, the static host's API proxy target, secrets), never from code.
3. Schema changes go through Alembic migrations only.
4. Moving provider means: restore the latest dump into the new PostgreSQL, set the environment values, update the static host's `/api/*` proxy target (and the allowed origins if CORS is ever enabled). Rehearse once before launch.
5. The browser sees one origin: the static host proxies `/api/*` to the backend, so session cookies are same-origin (09 §5). Fallback if no free static host can do this: the backend serves the built frontend, and the page then also waits for a cold start.

## 8. Open items before deployment

- Backup scheduler, storage location, frequency and retention.
- Region for backend and database (same region; measure latency from Nigeria).
- Time the first request after 10 idle minutes on the deployed setup and record it here.
- A dedicated Oracle VM for the fallback is not yet available.
- Re-verify the provider terms in §3.
- Admin 'last exported' warning threshold (03 §18 item 4).
- Static frontend host.
- Static host must proxy `/api/*` and pass Set-Cookie; compare its proxy timeout with the Render wake-up time.
- Application database role, owner role and grants (09 §11).
- Admin session and login-attempt storage (04, via 09 §5 and §6).
