# Security

Document: `docs/09-security.md`
Version: `0.1.1`
Status: Draft — design phase
Last Updated: 2026-10-10
Related documents: `03-mvp-architecture.md`, `04-database.md`, `06-transaction-ingestion.md`, `10-deployment.md`

Changes in this version: Admin attempt storage resolved: `admin_login_attempt` (04); §18 open item removed.

---

## 1. Scope and authority

This document fixes the MVP security rules. It confirms 03 §8 and ADR-008, ADR-009, ADR-013 and ADR-026, and settles the defaults those documents left open. Where this document is stricter than 03 §8.2, this document governs. Values marked "initial default" are tuned by testing and kept in settings, not in code.

## 2. Threats this design addresses

1. Remote guessing of tenant access codes.
2. Theft of a session token through cross-site scripting.
3. Takeover of the admin account.
4. A malicious or oversized PDF exhausting the free instance.
5. A leaked database dump or backup.
6. One tenancy reading another tenancy's or property's data.
7. Locking tenants out on purpose.

## 3. Admin authentication

- Admin logs in with email and password (03 §8.1). One admin per organization.
- Password hashing: Argon2id through argon2-cffi. Start from the library defaults (3 iterations, 64 MiB, parallelism 4). Parameters live in settings. Benchmark on the deployed instance. Limit concurrent hashing (initial default: 2) so the free instance's memory is not exhausted. Rehash on successful login when the stored parameters are outdated.
- Minimum password length 15 characters, long passphrases allowed (at least 64 characters), no composition rules. Reject passwords found in a bundled common-password list.
- No MFA in the MVP (§17).
- No self-service reset (no email, ADR-012). The operator resets the password with a command run against the database. The reset revokes all admin sessions.
- All admin authentication goes through one server function (`get_current_admin`); no route reads the session itself.

## 4. Tenant authentication

Confirms 03 §8.2 and ADR-009:

- Server-generated shared code per tenancy, at least 40 bits, hashed with the same Argon2id configuration, never chosen by the admin, never looked up globally.
- Login is scoped: the tenant selects a room and the code is verified only against that room's active tenancy.
- Failures return one generic error. When the room has no active credential, perform a dummy hash verification so response time does not reveal that.
- The pre-login room list exposes room labels only: no tenant names, balances or statuses.
- Reset: the admin dashboard shows the new code once; it cannot be retrieved afterwards. Reset revokes all sessions of that tenancy. There is no rotation schedule; reset on tenant turnover or at the admin's choice. Closing a tenancy permanently deactivates its credential (ADR-026).

## 5. Sessions and transport

- Both session types are server-side. The token is random, at least 128 bits as required by ADR-009 (implementation: 32 random bytes), shown once, and stored only as a SHA-256 hash.
- Tenant: `tenant_session`, fixed absolute expiry (initial default 30 days), never extended (ADR-009).
- Admin: `admin_session` (shape defined in 04), same mechanics as `tenant_session`. Fixed absolute expiry (initial default 24 hours), never extended. Revoked on logout, password change or reset, and admin deactivation. `is_active` is also checked on every admin request.
- Transport is an HttpOnly cookie: `__Host-` prefix, Secure, HttpOnly, SameSite=Lax, Path=/, no Domain attribute. Tokens are never stored in localStorage or sessionStorage and are never readable by JavaScript.
- The browser sees one origin: the static host proxies `/api/*` to the backend (10 §7). No cross-origin cookies and no CORS credentials.
- CSRF: reject any state-changing request (not GET or HEAD) whose Origin or Sec-Fetch-Site is not the app's own origin, and require a custom request header on state-changing admin calls. The tenant portal is read-only, so login and logout are its only state-changing calls.
- Session transport is isolated in one module so it can be replaced without touching business logic.

## 6. Rate limiting and lockout

Database-backed (not in process memory), counted by subject:

- Tenant, per tenancy: 5 failures per 15 minutes, then a 15-minute lockout (ADR-009; initial default confirmed).
- Tenant, per source IP: 20 failures per 15 minutes, then a 15-minute lockout (initial default). Deliberately looser than the per-tenancy limit because mobile networks may put many users behind one IP.
- Organization-wide: if tenant login failures exceed 100 per 15 minutes, add a 2-second delay to every tenant login. This slows an attack and never blocks legitimate logins (initial default).
- Admin, per source IP: 10 failures per 15 minutes, then a 15-minute lockout; the organization-wide delay rule also applies to admin logins (initial defaults). Admin attempts are stored in `admin_login_attempt` (04).
- A lockout returns a generic "try again later" response. The admin can see lockouts and reset a tenancy's code at any time (03 §8.2), which bounds a deliberate-lockout attack.
- IPv6 addresses are counted per /64.
- The limiter is generic over its subject, so new limits are configuration.

## 7. Client IP behind proxies

- The client IP is taken only from the proxy header set by the platform, trusting a configured number of proxy hops and no other source. The static-host proxy adds a hop.
- Test with spoofed `X-Forwarded-For` headers.
- If the real client IP cannot be derived reliably, per-IP limits are disabled and the per-tenancy and organization-wide limits still apply.
- Verify the forwarding behavior of Render and of the chosen static host before launch (not yet verified).

## 8. Authorization and tenant isolation

- All access and visibility rules are enforced server-side (constitution). Every scoped query filters by `organization_id`, plus `property_id` and `tenancy_id` where relevant.
- ADR-008 defines tenant visibility; per-room amounts of other rooms are hidden unless the admin enables them through `portal_setting`.
- Automated tests are required: a tenant session cannot read another tenancy's data, another property's data, or another organization's data; a closed tenancy's session is rejected; a revoked or expired session is rejected.
- Security-relevant admin actions are written to `audit_log`: login, logout, password change or reset, tenant code reset, tenancy closure, data export, and portal setting changes. Secrets are never written to it.

## 9. Browser hardening

- A strict Content-Security-Policy on the frontend document, allowing only the app's own origin and no third-party scripts. Start in report-only mode, then enforce after testing.
- Also: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `frame-ancestors 'none'`, and HSTS.
- Frontend headers are set at the static host; API headers are set in the backend.
- With one origin, CORS is not needed in production. If it is ever enabled, allow only the exact frontend origin and never a wildcard. CORS is not an authorization control.

## 10. PDF upload handling

Applies to the synchronous statement import (ADR-012, 06):

- Enforce a maximum upload size before the whole body is buffered, a maximum page count, and a processing time limit. Initial defaults: 10 MB, 100 pages, 30 seconds. Tune against real statements.
- Validate the PDF signature and structure; never trust the file extension or the declared content type. Reject encrypted and malformed PDFs with a clear error.
- Never execute embedded content. Run the parser with a memory cap below the instance limit, in a separate process if the chosen library supports it.
- PDFs are never retained (constitution 1.2.1); only the hash and metadata are stored.
- Benchmark with real statements once the parsing library is chosen.

## 11. Database security

- TLS required on every connection; verify the server certificate if the provider supports it (verify on Neon).
- The application uses a dedicated role with only the privileges it needs. A separate owner role runs migrations. In production, privileges mirror 04 §11: for tables listed as immutable there, the application role has INSERT and SELECT only. Grants are applied by the migrations.
- Small connection pool with `pool_pre_ping`. Use the direct connection for migrations and `pg_dump` (10 §6).

## 12. Secrets, logging and errors

- Secrets come from environment variables and never from the repository (03 §12, 10 §7).
- Never log passwords, access codes, tokens, hashes, commission data, or personal data such as tenant names and phone numbers. Log identifiers instead.
- Production returns generic error messages. No stack traces; debug mode off.

## 13. Backups

Specified in 10 §6. Backups are encrypted before leaving the host, and the keys are stored separately from the backup files.

## 14. Retention and pruning

04 §11.4 and §11.6 allow pruning. The MVP has no scheduled jobs, so pruning runs opportunistically during login requests or manually.

- Delete only sessions that are expired or revoked past a grace period (initial default 7 days), and login attempts older than 24 hours.
- Prune with a single bounded statement. Never delete a row that is still counted by a limiter or is still valid.

## 15. Dependencies

Pin and lock Python and JavaScript dependencies and commit the lockfiles. Run `pip-audit` before releases. Enable Dependabot security updates if the repository is hosted on GitHub. Review updates before merging.

## 16. Data protection (legal, open)

Names, rooms and payment records are personal data. Before launch, with Nigerian counsel: confirm whether the landlord or property manager is a data controller, whether NDPC registration applies, whether a data-protection impact assessment is needed, and the breach-notification deadlines under the Nigeria Data Protection Act 2023. Document the purpose, lawful basis, retention periods, access and correction procedure, and breach response. This is not legal advice.

## 17. Deferred and upgrade paths

| Item | Why deferred | Trigger | Cost to add |
|---|---|---|---|
| Admin MFA (TOTP) | One admin, no email; compensated by a 15-character minimum, a password blocklist, throttling and revocable sessions | Multiple admins, or any real-money risk beyond statement tracking | New columns on `admin_user`, one login step |
| Multiple admins | Single-organization MVP | A second operator | `admin_user` already supports it; add roles |
| Self-service admin reset | Needs email | An email provider is introduced | New flow reusing the session and limiter modules |
| Progressive challenges (CAPTCHA) | Delays are enough for the MVP | Sustained login abuse | One extra step in the login flow |

## 18. Open items before deployment

- Benchmark Argon2id on the deployed instance and set the hashing concurrency.
- Verify forwarding headers and trusted hop count on Render and the static host (§7).
- Verify that the static host's proxy forwards cookies, and compare its timeout with Render's wake-up time.
- Neon TLS verification and role setup (§11).
- Choose the PDF parsing library and tune the §10 limits.
- The data-protection questions in §16.
