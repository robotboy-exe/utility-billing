# Utility Billing MVP Architecture

Document: `docs/03-mvp-architecture.md`
Version: `0.10.2`
Status: Consolidated source of truth
Last Updated: 2026-10-10
Related documents: `04-database.md`, `05-billing-engine.md`, `06-transaction-ingestion.md`, `changelog-03.md`

---

## 1. Purpose

This document defines the MVP architecture for a tenancy-based utility billing and payment ledger application.

The application allows a landlord or property manager to:

- Maintain properties, rooms, tenancies, and tenants.
- Record incoming tenant payments.
- Record outgoing utility bill payments to providers.
- Import statement transactions, primarily from the Payvice Avantus PDF export.
- Match incoming tenant payments to the correct tenancy.
- Allocate tenant payments against monthly utility bills.
- Track outstanding balances, current payments, and advance payments.
- Preserve historical financial records.
- Provide secure read-only access for tenants to view billing information.

This document adds the MVP's free-hosting constraints and product decisions:

- Free-hosting constraints.
- A two-ledger financial model.
- Simplified authentication and authorization.
- Tenant portal visibility rules.
- Shared tenancy access rules.
- Bill adjustment transparency rules.
- Payvice Avantus PDF ingestion as the primary transaction source.
- MVP-specific scope limitations.

This document is the consolidated source of truth for the system architecture. It combines the foundational architectural goals, principles, and module structure with the MVP's free-hosting constraints and product decisions.

---

## 2. Architectural Foundations

### 2.1 Architectural Goals

The system should be:

**Correct**

Financial calculations and payment allocations must be deterministic, auditable, and reproducible.

**Modular**

Business domains should be separated so that changes to one subsystem do not unnecessarily affect others.

**Source-Agnostic**

The billing system must not depend on where a transaction originated (PDF statement, manual entry, or a future integration). See ADR-004.

**Hosting-Independent**

Business logic must not depend on the chosen host or runtime (§14.3). Scope of the MVP versus a future multi-organization SaaS is in §14.4.

**Extensible**

The architecture should allow future features such as:

- Multiple properties.
- Multiple utility categories.
- Additional payment providers.
- Direct bank integrations.
- Notifications.
- Mobile applications.
- Additional reporting and export formats.

**Maintainable**

The system should be structured so that both human developers and AI coding assistants can understand and modify individual modules without needing to reason about the entire application simultaneously.

### 2.2 Guiding Principles

#### 2.2.1 Business Logic First

Financial and tenancy rules take precedence over UI considerations.

#### 2.2.2 Separation of Concerns

The following concerns should remain separate:

- Presentation.
- API.
- Business logic.
- Data access.
- External integrations.
- Persistence.

#### 2.2.3 Domain Isolation

Major business domains should have clear boundaries.

For example, the billing engine should not contain bank statement parsing logic.

#### 2.2.4 Immutable Financial History

Transactions and historical payment allocations must be preserved.

Corrections should be represented through controlled correction/reversal mechanisms rather than silently rewriting historical financial data.

#### 2.2.5 Single Source of Truth

Each important piece of information should have one authoritative representation.

For example, a transaction should be stored once and referenced by payment allocations rather than duplicated into every monthly bill.

#### 2.2.6 Hosting Independence

Business logic must not depend on the hosting provider or runtime. Hosting differences live in configuration, not in domain code.

### 2.3 MVP Scope Simplifications

The MVP intentionally simplifies the scope:

- One administrator and one organization are assumed. Organization-level scoping is kept in the data model (§14.4).
- Payvice Avantus PDF statement import and manual entry are the only transaction sources (ADR-014).
- Payment-provider, webhook and bank integrations are deferred (§14.6).
- OCR / scanned-image PDF parsing is deferred.
- Full tenant user management is deferred (ADR-013).
- Background jobs and scheduled tasks are avoided due to free-hosting constraints (ADR-012).

---

## 3. Two-Ledger Model

The system maintains two separate financial ledgers. This is a foundational decision that shapes the domain model, ingestion, billing, reporting, and visibility.

### 3.1 Tenant Payment Ledger

Purpose:

- Record incoming tenant payments.
- Match payments to tenancies.
- Allocate payments to monthly tenant utility bills.
- Track outstanding balances and advance credits.

Source in MVP:

- `FUNDING` credit rows from Payvice Avantus statements.

Rules:

- Payment date does not determine billing month.
- The billing engine's reconciliation is final.
- Payments fill outstanding bills chronologically.
- Overpayments become advance credit.

### 3.2 Utility Bill Payment Ledger

Purpose:

- Record payments made to utility providers.
- Provide month-bounded utility spend reporting.
- Serve as proof-of-payment records.

Source in MVP:

- `BEDC` debit rows from Payvice Avantus statements.

Rules:

- Utility payments do not settle tenant bills.
- Utility payments do not enter tenancy matching.
- Reporting is bounded by the payment's calendar month in the business timezone (section 10.4).
- Future utility providers are registry-driven.

### 3.3 Ledger separation

The two ledgers never settle each other:

- BEDC payments never reduce tenant balances.
- Tenant payments never count as provider payments.

This keeps tenant billing state clean and makes provider payments a pure spend / proof-of-payment record.

---

## 4. MVP Product Scope

### 4.1 In scope for MVP

The MVP includes:

- Admin authentication.
- Admin management of:
  - Properties.
  - Rooms.
  - Tenancies.
  - Tenants.
  - Sender aliases.
  - Monthly utility bills.
  - Statement imports.
  - Transaction matching.
  - Payment allocation.
  - Reports.
- Tenant portal access using a shared tenancy access code.
- Tenant read-only access to:
  - Property-level billing information.
  - Full details of the tenant's own tenancy/room.
  - Property-level utility spend records.
- Automatic rolling monthly bill generation using a standard monthly amount.
- Rate-change-driven bill adjustments and debt write-offs.
- Public visibility of bill adjustments.
- PDF statement import from the Payvice Avantus billing software (primary transaction source).
- Manual transaction entry (also the fallback for failed or blocked imports).
- Utility provider registry with BEDC as the first provider.
- Utility bill payment recording and month-bounded spend reporting.
- Basic audit logging.
- Admin full-data export with a "last exported" indicator (§5.3).
- Free-hosting-friendly deployment.

### 4.2 Out of scope for MVP

The following are deferred:

- CSV, XLSX and Google Sheets statement import.
- Payment-provider and bank integrations, including webhooks (§14.6, ADR-006).
- OCR / scanned-image PDF parsing.
- Background workers.
- Scheduled billing jobs.
- Email notifications.
- SMS notifications.
- Mobile application.
- Multiple utility categories beyond the provider registry abstraction.
- Subscription billing.
- Advanced role-based access control.
- Full tenant account management.
- Tenant self-registration.
- Tenant password management.
- Individual tenant credentials, unless added later by a future ADR.
- Automated bank reconciliation.

### 4.3 Future Architectural Considerations

The architecture should leave room for:

- Multiple utility categories.
- Property-specific utility pricing.
- Multiple properties.
- Multiple buildings.
- More payment providers.
- Direct bank integrations.
- Automated bank reconciliation.
- Notifications.
- Mobile clients.
- Advanced reporting.
- Subscription billing.
- Role-based access control.
- Dedicated customer environments (§14.4).

These features should not be implemented merely because the architecture allows them.

The current implementation should remain focused on the MVP.

---

## 5. Free-Hosting Constraints

The MVP is expected to be hosted using free-tier infrastructure. These constraints must shape the architecture before implementation begins.

### 5.1 Hosting assumptions

Free hosting commonly imposes limits such as:

- Application sleep after inactivity.
- Cold starts.
- Limited CPU and memory.
- Limited persistent disk storage.
- Limited database storage.
- Limited database connections.
- Limited request timeout.
- Limited or no background workers.
- Limited or no scheduled jobs.
- Limited email-sending capability.

### 5.2 Architectural consequences

The MVP must therefore be designed as follows:

| Constraint | MVP design response |
|---|---|
| No reliable background jobs | Imports and matching are manually triggered by the admin. Bill generation is lazy/rolling and happens synchronously in response to real usage, so no background worker is needed. |
| No reliable scheduled tasks | Monthly bills are generated lazily/on-demand the first time the system needs them (admin dashboard load, payment allocation, import batch confirm, admin report requests), not by a scheduled task. |
| Ephemeral filesystem | Do not rely on uploaded files remaining on the server. Store normalized transaction records in the database. |
| Limited database storage | Keep financial records normalized and compact. Avoid storing original statement files unless explicitly required. |
| Limited request timeout | Imports must be small enough to process synchronously. PDF parsing is bounded by file size and page limits. |
| CPU/memory limits | Use lightweight text-extraction for PDF only. Reject scanned PDFs. Stage imports before commit. |
| Cold starts | The system should tolerate slow first requests. |
| Limited email capability | Do not require email for tenant access in MVP. |
| No webhook reliability | Webhooks are deferred (§14.6). |

### 5.2.1 Bill generation contract

Lazy generation (ADR-022) is one function with one contract. Detailed bill rules are in `05-billing-engine.md`.

- **Single entry point.** `ensure_bills_through(organization_id, month)` creates any missing bill for every active tenancy for each month up to and including `month`. `month` is computed in the business timezone (§10.4). It consults `billing_override` (bill/skip decisions, ADR-024) before creating a bill.
- **Idempotent by construction.** Creation is `INSERT ... ON CONFLICT (tenancy_id, billing_month) DO NOTHING`, backed by the unique constraint in `04-database.md`. Calling it twice, or concurrently, yields the same bills.
- **Explicit callers.** Admin dashboard load, payment allocation, import batch confirm, and admin report requests. Nothing else calls it.
- **Not callers.** The tenant portal and any request authenticated only by a tenant session (read-only, ADR-009). The portal reads existing bills and shows an "as of" date, so its figures can lag a month rollover until the next admin action.
- **Transactions and locking.** Allocation and batch confirm each run in one database transaction. Inside it: call `ensure_bills_through`; for batch confirm, lock the `import_batch` row first and re-check its status so a double-click cannot confirm twice; lock affected tenancies in ascending id order, then each tenancy's open bills `FOR UPDATE` ordered by `billing_month`; write allocations and advance movements in the same transaction. Any failure rolls the whole unit back.

### 5.3 Backup strategy

Free database tiers can pause, expire or lose data, and ADR-012 retains no files. Export is therefore the backup, and it is an MVP requirement.

- **Full export.** Admin-triggered, produces one JSON file containing all organization-scoped records (properties, rooms, tenancies, tenants, sender aliases, transactions, monthly bills, allocations, advance movements, adjustments, utility bill payments, import batch metadata, audit log). Per-table CSV is an optional convenience, not a substitute.
- **Exclusions.** Credential material is never exported: admin password hashes, access code hashes, session token hashes. Commission data does not exist to export (ADR-019).
- **"Last exported" indicator.** The admin dashboard shows the time of the last successful full export and warns when none exists or it is older than a threshold set in `10-deployment.md`.
- **Restore.** A documented restore procedure belongs in `10-deployment.md`; an export that has never been test-restored is not a backup.
- **Source PDFs are not retained** (ADR-012, ADR-014, ADR-019: a retained PDF would hold commission rows). Each `import_batch` records the file's SHA-256, filename and page count instead, so the admin can show that a re-presented file is the same one that was imported, without keeping it. The batch fields are specified in `04-database.md`.

---

## 6. System Architecture

The MVP follows the high-level architecture below.

```text
Browser
  │
  │ HTTPS / REST API
  ▼
Backend
  │
  ├── API Layer
  ├── Authentication / Authorization
  ├── Application Services
  ├── Domain / Business Logic
  └── Data Access
  │
  ▼
PostgreSQL
```

### 6.1 Frontend

The frontend is a separate web application.

Recommended MVP stack:

- React.
- TypeScript.
- Vite.

Responsibilities:

- User interface.
- Forms.
- Tables.
- Dashboards.
- Reports.
- Tenant portal.
- API interaction.

The frontend must not contain authoritative financial business logic.

### 6.2 Backend

Recommended MVP stack:

- Python.
- FastAPI.

Responsibilities:

- API endpoints.
- Authentication.
- Authorization.
- Visibility policy enforcement.
- Transaction import processing.
- Transaction normalization.
- Duplicate detection.
- Matching.
- Billing operations.
- Payment allocation.
- Utility spend recording.
- Reporting queries.
- Audit logging.

### 6.3 Database

Production database target:

- PostgreSQL.

SQLite may be used for local development only.

The database is the authoritative persistence layer.

### 6.4 Candidate free-hosting shape

The exact provider is recorded below, but the MVP should fit this general shape:

| Component | Possible free hosting approach |
|---|---|
| Frontend | Static hosting, such as Cloudflare Pages, Vercel, or Netlify. |
| Backend | Free Python application host, such as Render, Koyeb, or similar. |
| Database | Free managed PostgreSQL, such as Neon, Supabase, or similar. |
| File storage | Avoided in MVP unless external object storage is added. |
| Email | Avoided in MVP. |
| Background jobs | Avoided in MVP. |

The business logic must remain independent of the selected hosting provider.

**Provider selection is resolved:** the MVP choice is Render + Neon with an Oracle VM fallback, recorded in `10-deployment.md` §2. It meets the selection criteria: the database must not pause, expire or be deleted for inactivity or after a trial period; the backend must tolerate cold starts; the database must support the partial unique indexes and row-level locking this design uses (`04-database.md` open question 4); and the admin must be able to export and restore data (§5.3).

### 6.5 System Context

At a high level:

```text
                   ┌─────────────────────┐
                   │      Landlord       │
                   │       / User        │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │   Web Application   │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │      Backend        │
                   │   Business Logic    │
                   └──────────┬──────────┘
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
         ┌───────────┐ ┌─────────────┐ ┌───────────┐
         │ Database  │ │ Transaction │ │ External  │
         │           │ │  Sources    │ │ Services  │
         └───────────┘ └─────────────┘ └───────────┘
```

Transaction sources in the MVP are PDF statements and manual entry. Everything else is deferred (§14.6).

### 6.6 ORM and Database Tooling

Initial recommendation:

- SQLAlchemy.
- Alembic.

SQLAlchemy will provide the application data-access/model layer.

Alembic will manage database schema migrations.

### 6.7 Core Modules

The application should be divided into domain-oriented modules.

#### 6.7.1 Organization Module

Responsible for:

- Organizations.
- Organization configuration.
- Organization-level isolation.

#### 6.7.2 Property Module

Responsible for:

- Properties.
- Rooms.
- Property configuration.

#### 6.7.3 Tenancy Module

Responsible for:

- Tenancies.
- Tenants.
- Tenant changes.
- Sender aliases.
- Tenancy lifecycle.

#### 6.7.4 Transaction Ingestion Module

Responsible for obtaining transactions from external sources.

MVP:

- PDF (Payvice Avantus), the primary source (ADR-014).
- Manual entry, always available as a fallback for failed or blocked imports.

Deferred sources are in §14.6.

All sources must be normalized into the application's standard transaction model.

Detailed ingestion architecture belongs in `06-transaction-ingestion.md`.

#### 6.7.5 Transaction Matching Module

Responsible for:

- Matching sender names to sender aliases.
- Identifying the associated tenancy.
- Handling unmatched transactions.
- Supporting manual matching.

Matching must not directly implement billing allocation rules.

#### 6.7.6 Billing Module

Responsible for:

- Monthly bills.
- Payment allocation.
- Outstanding debt.
- Current-month payments.
- Advance payments.
- Partial payments.
- Billing status.

This is the core financial business domain.

Detailed rules belong in `05-billing-engine.md`.

#### 6.7.7 Reporting Module

Responsible for presenting information such as:

- Rooms fully paid.
- Rooms owing.
- Amount owed.
- Current-month payment status.
- Advance payments.
- Payment history.
- Transaction history.

Reports should derive their data from authoritative records rather than maintain independent copies of financial state.

#### 6.7.8 Administration Module

Responsible for:

- Organization-wide standard utility bill amount (uniform across rooms; not system-wide).
- Application configuration.
- Import profiles.
- Administrative operations.

#### 6.7.9 Authentication and Authorization

Responsible for:

- User authentication.
- Sessions/tokens.
- Organization membership.
- Roles and permissions.

The MVP has one administrator. Admin users carry `organization_id`; multi-user roles are deferred (§14.4).

#### 6.7.10 Audit Module

Responsible for recording important actions affecting the system.

Audit records should be append-oriented and should not be casually editable.

### 6.8 Transaction Flow

The generalized transaction flow is:

```text
External Source
      │
      ▼
Transaction Ingestion
      │
      ▼
Normalization
      │
      ▼
Duplicate Detection
      │
      ▼
Transaction Stored
      │
      ▼
Transaction Matching
      │
      ▼
Matched Tenancy
      │
      ▼
Billing Engine
      │
      ▼
Payment Allocations
      │
      ▼
Monthly Billing State
      │
      ▼
Reports / Dashboard
```

The same flow should apply regardless of whether the source is a statement import or a future integration.

### 6.9 Transaction Source Abstraction

The system must separate transaction acquisition from transaction processing.

Conceptually:

```text
PDF ────────────┐
Manual ─────────┤
Future sources ─┘   (ADR-006, §14.6)
                │
                ▼
       Standard Transaction
                │
                ▼
        Matching + Billing
```

Adding a new transaction source should not require modifications to the billing engine.

### 6.10 Billing Independence

The Billing Engine must not depend on:

- React.
- FastAPI request handlers.
- PDF extraction or any other parser.
- Any payment provider or bank API.

The Billing Engine should operate on domain-level data.

This allows it to be tested independently from the user interface and external integrations.

---

## 7. Domain Model

The MVP retains the domain hierarchy described in this document.

```text
Organization ─── Property ─── Room ─── Tenancy ─── Tenant
                                      │
                                      └── Sender Alias
```
**Entity Summary**

| Entity | Purpose & Key Relationships |
|---|---|
| Organization | Root isolation boundary. Owns properties, users, and financial records. |
| Property | Physical building. Contains rooms. |
| Room | Physical space. Persists across tenancies. One active tenancy at a time. |
| Tenancy | Occupancy period. Privacy boundary for the tenant portal. Owns financial history. |
| Tenant | Individual occupant. Multiple tenants per tenancy. No individual logins in MVP. |
| Sender Alias | Accepted bank sender name for a tenancy. Primary matching key for `FUNDING` rows. |
| Transaction | Normalized source transaction. Categorized as `tenant_payment` or `utility_bill_payment`. |
| Monthly Bill | Billing state for a tenancy/month. One per tenancy/month. |
| Payment Allocation | Links a tenant payment to a monthly bill. |
| Advance Movement | Append-only advance-credit event (created/applied/reversed) linked to its originating payment and reconciled against the derived advance balance. |
| Bill Adjustment | Recorded change to a bill's final amount (rate-change or write-off only). |
| Utility Provider | Global registry of utility companies (e.g., BEDC). |
| Utility Bill Payment | Outgoing payment to a provider. Does not settle tenant bills. |
| Import Profile | Global parser configuration (e.g., PAYVICE_AVANTUS). |
| Import Batch | Staged/confirmed import operation metadata. |
| Audit Log | Append-only record of admin/system actions. |

*Detailed schema, constraints, indexes, and exact field definitions are specified in `04-database.md`.*

This table is an intentional conceptual subset of the domain. It shows the entities that carry business meaning, not every physical table. The following physical/operational tables are intentionally excluded here and are specified in `04-database.md`: `admin_user`, `tenant_access_credential`, `tenant_session`, `admin_session`, `tenant_login_attempt`, `admin_login_attempt`, `billing_config`, `billing_override`, `standard_amount_change`, `import_channel_category_mapping`, `staged_import_row`, and `portal_setting`.

---

## 8. Authentication & Authorization
The MVP uses a simplified auth model. Detailed session and credential schemas are in `04-database.md`.

**8.1 Roles**
- **Admin:** Full access. Email/password login (hashed). Server-side authorization.
- **Tenant Portal Session:** Read-only access to permitted tenant-facing information.

**8.2 Tenant Portal Access (MVP requirements, ADR-009, ADR-026)**
- **No full user management:** Tenants have no passwords, profiles or individual logins.
- **Shared tenancy code:** Each tenancy has one shared access code. Roommates may use it concurrently; sessions are per device.
- **Generation:** The server generates the code. The admin cannot choose it. Minimum 40 bits of entropy (for example 8 characters from a 32-character alphabet without look-alike characters). Stored hashed with the same password-hashing function as admin passwords.
- **Login is scoped:** The tenant selects their room, then enters the code. The server resolves the room's active tenancy and verifies the code against that tenancy only. Codes are never assumed unique and never looked up globally. Failures return one generic error.
- **Rate limiting:** Stored in the database (not in process memory), because free hosts restart, sleep and may run more than one instance. Counted per tenancy and per source IP. Initial defaults: 5 failed attempts per tenancy per 15 minutes then a 15-minute lockout; per-IP limit counted separately so one IP cannot lock out every tenancy. Admin can see lockouts and reset the code. Thresholds are set in `09-security.md`.
- **Sessions:** Random token of at least 128 bits, hashed at rest, fixed absolute expiry (initial default 30 days, no sliding extension). After expiry the tenant re-enters the code. Set in `09-security.md`.
- **Delivery:** Admin shares the code out-of-band (for example WhatsApp or SMS).
- **Revocation:** Resetting the code invalidates all existing sessions. Closing a tenancy permanently deactivates its credential, with no historical access restoration.

---

## 9. Tenant Portal Visibility
Visibility is a policy concern enforced server-side. The frontend must not be trusted to hide data. Configuration is stored in the `portal_setting` table (see `04-database.md`).

**9.1 Privacy Boundary**
The privacy boundary is the **tenancy**. Members of the same tenancy see full details. Members of other tenancies see property-level aggregates only by default (ADR-008). Tenants cannot see other properties. Admin sees everything.

**9.2 Visibility Matrix**
The values below are the MVP **default policy**. The policy is configurable at organization or property scope through `portal_setting` (see `04-database.md` §6.8, ADR-008, ADR-011); the keys listed there are examples, not an exhaustive mapping of every cell. Enforcement is always server-side.

Default rationale: in a small property a room label identifies a person, so per-room arrears are personal data. Aggregates give tenants the transparency intended by ADR-027 without exposing individuals. An admin who wants the earlier behavior opts in per organization or property (`allow_other_room_amount_due`). Check applicability of Nigerian data-protection rules (the Nigeria Data Protection Act 2023) with qualified counsel before enabling it.

| Information | Same tenancy | Other rooms (same property) | Other properties | Admin |
|---|---|---|---|---|
| Property/Room list & names | Visible | Visible | Hidden | Visible |
| Property aggregates (total outstanding debt, fully-paid room count and ratio; ADR-027) | Visible | Visible | Hidden | Visible |
| Room billing amount/status | Visible | Hidden by default; opt-in | Hidden | Visible |
| Room bill adjustment notice | Visible | Org-wide rate-change notices visible; room-specific adjustments and write-offs hidden | Hidden | Visible |
| Property utility spend | Visible | Visible | Hidden | Visible |
| Tenants & contact details | Visible | Hidden | Hidden | Visible |
| Tenancy bills/payments/transactions | Full | Hidden | Hidden | Visible |
| Audit log | Hidden | Hidden | Hidden | Visible |

**9.3 Default View & Flexibility**
- The default tenant view is the **Property view** (configurable to "Room view" later).
- Utility bill payment records and spend reports are property-level records visible to all tenants in that property.

---

## 10. Billing, Ingestion, and Matching
Two-ledger rules: §3 (ADR-017).

**10.1 Transaction Ingestion (Summary)**
- **Sources:** Payvice Avantus PDF, text-based only, no OCR (ADR-014), plus manual entry. No other sources in the MVP.
- **Flow:** Upload/Parse -> Staged Batch -> Admin Preview -> Confirm.
- **Category mapping:** Configuration-driven (ADR-015). `FUNDING` = tenant payment; `BEDC` = utility payment; `COMMISSION` = discarded.
- **Commission rows:** Never persisted, displayed, counted or logged (ADR-019). The parser may recognize them transiently, in memory, only to validate the statement's control totals.
- **Control totals fail closed:** The parser recomputes totals from parsed rows and compares them with the statement footer. A mismatch, or a missing footer, blocks confirmation of the batch; the admin re-uploads or falls back to manual entry. Only `totals_status` is persisted. Footer totals include commissions and are not stored.
- **Duplicates and idempotency:** Row-level duplicate keys and the statement fingerprint make re-importing the same or an overlapping statement safe (`06-transaction-ingestion.md` §18). The file's SHA-256 is recorded; the file is not retained (§5.3).
- *Parser grammar, validation and duplicate rules are in `06-transaction-ingestion.md`.*

**10.2 Matching**
- Only `tenant_payment` rows enter matching (primarily via normalized sender aliases).
- `utility_bill_payment` rows bypass matching and go to provider spend reporting.

**10.3 Billing & Allocation (Summary)**
- **Generation:** Lazy and rolling through `ensure_bills_through` (§5.2.1, ADR-022).
- **Standard amount:** Organization-wide and uniform (ADR-023). No per-room amount overrides.
- **Adjustments:** Only an org-wide rate change (delta on unsettled current-month bills) or a debt write-off (ADR-010, ADR-025). Audited.
- **Bill/skip decisions:** `billing_override` is a per-tenancy, per-month decision to force-bill or force-skip (ADR-024). It never changes an amount.
- **Partial months:** Move-in unbilled by default (admin may opt in); move-out billed in full by default (admin may exempt with foreknowledge or write off after closure) (ADR-024).
- **Allocation:** Oldest-outstanding-first (ADR-020); overpayment becomes advance credit; advance balance is derived and every movement is logged and reconciled (ADR-021).
- *Algorithms, edge cases and corrections are in `05-billing-engine.md`.*

**10.4 Business timezone (ADR-028)**
- Each organization has one IANA timezone, default `Africa/Lagos` (UTC+1, no daylight saving).
- All calendar-month boundaries use it: `billing_month`, "current month", the month `ensure_bills_through` generates through, and the grouping of utility spend.
- Instants are stored as `timestamptz` (UTC). Statement timestamps carry no offset and are interpreted in the organization timezone.
- One timezone per organization in the MVP, not per property.

---

## 11. Reporting

Reports derive from authoritative records.

They must not maintain independent copies of financial truth.

### 11.1 Admin reports

Admin reporting should include:

- Rooms fully paid.
- Rooms owing.
- Rooms with advance payments.
- Amount owed per room.
- Current-month payment status.
- Unmatched transactions.
- Transaction history.
- Bill adjustment history.
- Utility spend by provider and month.
- Import history.

### 11.2 Tenant portal reports

Tenant portal reporting should include:

Property view (tenant-facing dashboard):
- Total outstanding tenant debt across all rooms.
- Total room count.
- Fully paid room count (count only, no amount).
- Progress ratio of fully-paid rooms to total rooms, clearly labeled, e.g. "15 of 22 rooms fully paid".
- Current-month utility spend (amount paid to the utility provider / BEDC outflow for the current month).
- Historical lookup: for any past month, the total utility spend (BEDC outflow) for that month. This is the **only** historical data exposed; historical months show the total amount only, with no room counts.

The historical figure is the amount paid **to the utility provider** (Utility Bill Payment Ledger), not tenant bill payments.

My Room / My Tenancy view:

- Tenancy details.
- Tenant details within the same tenancy.
- Bill history.
- Payment history.
- Transaction history for the tenancy.
- Advance or outstanding balance.
- Bill adjustment details.

### 11.3 Utility spend report

A separate report derived from the Utility Bill Payment Ledger.

Groups utility bill payments by provider and calendar month.

Does not reconcile tenant balances.

---

## 12. Data, Security, and Audit Principles
- **Transport & Secrets:** HTTPS in production. Secrets in environment variables, never in source control.
- **Server-Side Authorization:** All access and visibility rules enforced server-side.
- **Scoping:** Queries strictly scoped by `organization_id`, `property_id`, and `tenancy_id`. An automated test must fail if any data-access path lacks an `organization_id` filter (§15).
- **Money Handling:** Single currency. All amounts stored as `BIGINT` minor units (e.g., ₦1,000 = 100000). No floating-point math.
- **Immutability:** Financial records are append-only; the authoritative table list is `04-database.md` §11.1. Corrections use reversal/correction records, never silent rewrites.
- **Auditability:** Lightweight, append-only audit log for admin/system actions. Commission data is never logged. Tenants do not see the audit log.
- *Detailed security implementations are in `09-security.md` (see Section 17).*

---

## 13. API & Frontend Architecture
- **API:** RESTful. Handles validation, auth, visibility enforcement, and serialization. No heavy business logic. Endpoints grouped by Admin and Tenant Portal.
- **Frontend:** React + TypeScript + Vite. Organized by user-facing domains (Dashboard, Properties, Tenancies, Imports, Tenant Portal). Must not contain authoritative financial logic.

---

## 14. Deployment Architecture

The MVP should support simple deployment.

### 14.1 MVP deployment target

A likely MVP deployment shape is:

```text
Static Frontend Host
  │
  ▼
HTTPS REST API Host
  │
  ▼
Managed PostgreSQL
```

### 14.2 Deployment constraints

The deployment must support:

- HTTPS.
- Environment variables.
- Database migrations.
- API/backend connectivity.
- Reasonable upload limits.
- Session/token handling.

The deployment should avoid requiring:

- Background workers.
- Scheduled jobs.
- Local persistent file storage.
- Email delivery.
- Webhook endpoints (§14.6).

### 14.3 Hosting independence

Business logic must not depend on the chosen free host. The application should remain portable to paid hosting, a VPS or a managed platform.

### 14.4 Single-organization MVP, SaaS later

The MVP serves one organization and is org-scoped by design: every record carries `organization_id` and every query path filters by it. A dedicated deployment for one customer is possible because the application is config-driven; self-hosting is not a goal. Multi-organization SaaS is deferred and would additionally need self-serve onboarding, multi-user roles, subscription billing, isolation tests or Postgres row-level security, and no single-organization assumptions in code (for example, nothing may rely on tenant access codes being unique across organizations; login is room-scoped, §8.2). See ADR-002 and ADR-003.

### 14.5 Scalability Strategy

The initial workload is light: financial transaction records, monthly bills, tenant information and reports. Prioritize simplicity and correctness over distributed infrastructure.

Initial scaling strategy:

```text
Reverse Proxy
      │
Application Server
      │
PostgreSQL
```

Scale horizontally only when actual usage requires it. Potential future additions: multiple application instances, managed PostgreSQL, background job workers, queue infrastructure, object storage.

### 14.6 Deferred integrations

Paystack and Monnify webhooks and direct bank APIs are deferred (ADR-006). They need no design in the MVP, and the MVP deployment must not require webhook endpoints. Any future integration must keep these invariants:

- Verified: the sender is authenticated (for example, signature check) before anything is stored.
- Idempotent and retry-safe: reuse the duplicate-detection model of `06-transaction-ingestion.md` §18 (row-level duplicate key and statement fingerprint) so a redelivered event cannot create a second transaction.
- Normalized through the Transaction Source Abstraction (ADR-004) like any other source.
- Billing logic stays independent of where ingestion runs (ADR-007).

---

## 15. Testing Focus
Financial allocation scenarios, advance ledger reconciliation, and PDF parsing edge cases require extensive automated test coverage.
*Specific test scenarios and edge cases are defined in the Testing sections of `05-billing-engine.md` and `06-transaction-ingestion.md`.*

Tests required by this document:

- **Organization scoping:** enumerate every data-access path and fail if one lacks an `organization_id` filter (§12, §14.4).
- **Bill generation:** `ensure_bills_through` called twice and concurrently creates one bill per tenancy-month; the tenant portal never triggers it (§5.2.1).
- **Locking:** concurrent allocations and a double-submitted batch confirm leave consistent bills and a single confirmed batch.
- **Control totals:** a mismatch or missing footer blocks confirmation; no commission data appears in the database, logs or error output (§10.1, ADR-019).
- **Timezone:** bill and spend month boundaries around 23:59 and 00:00 on the last and first days of a month in the organization timezone (§10.4).
- **Tenant access:** rate limiting persists across an application restart; the lockout does not leak whether a room exists; sessions expire; code reset and tenancy closure revoke sessions (§8.2).
- **Visibility:** with default settings, a tenant session cannot retrieve another room's amount, status or adjustment (§9.2).
- **Export:** the export contains all organization records and no credential hashes (§5.3).

---

## 16. Architectural Decision Records (ADR Index)
The full Context, Decision, and Consequences for each ADR are stored in individual files in the `docs/adr/` directory.

| ADR | Title | Status | Summary |
|---|---|---|---|
| 001 | Organization as Root Entity (revised) | Accepted (revised) | Top-level boundary for customer data. |
| 002 | Single-Organization MVP Scope (revised) | Accepted (revised) | Single-organization MVP, org-scoped; SaaS deferred; self-hosting not a goal. |
| 003 | Hosting Provider Independence (revised) | Accepted (revised) | Logic doesn't depend on the host or runtime. |
| 004 | Transaction Source Abstraction | Accepted | Normalizes all sources before billing. |
| 005 | Statement Imports as MVP | Superseded by ADR-014 | Superseded by ADR-014 (PDF primary). |
| 006 | Future Event-Driven Integrations (revised) | Accepted (revised) | Deferred; invariants in section 14.6. |
| 007 | Billing Engine Independence (revised) | Accepted (revised) | Billing logic isolated from sources/UI. |
| 008 | Tenant Portal Visibility Boundary (revised) | Accepted (revised) | Tenancy boundary; other rooms see aggregates by default. |
| 009 | Shared Tenancy Access Code (revised) | Accepted (revised) | Shared code; generated, room-scoped, rate-limited, expiring sessions. |
| 010 | Rate-Change Adjustments and Write-Offs (revised) | Accepted (revised) | No per-room overrides; systematic adjustments only. |
| 011 | Configurable Tenant Portal Default View | Accepted | Property view default, configurable to Room. |
| 012 | Free-Hosting Synchronous MVP | Accepted | No background jobs/cron; lazy generation. |
| 013 | No Full Tenant User Management in MVP | Accepted | Shared codes instead of full user accounts. |
| 014 | PDF Statement Import as Primary MVP Ingestion Source | Accepted | Payvice Avantus PDF is mandatory/primary. |
| 015 | Category Mapping as Configuration | Accepted | Data-driven routing of statement rows. |
| 016 | Utility Provider Registry | Accepted | BEDC first; registry-driven, not hardcoded. |
| 017 | Separate Tenant Payment and Utility Bill Payment Ledgers | Accepted | Tenant payments and utility spend never mix. |
| 018 | Payment Date Does Not Determine Billing Month | Accepted | Allocation determines billing month. |
| 019 | Commission Rows Fully Excluded | Accepted | Commissions are fully discarded/ignored. |
| 020 | Chronological Oldest-Outstanding-First Allocation | Accepted | Chronological filling of bills. |
| 021 | Advance Movement Ledger and Reconciliation | Accepted | Append-only log for advance credit auditability. |
| 022 | Automatic Rolling Bill Generation (Lazy) (revised) | Accepted (revised) | One idempotent function, fixed callers, locking rules. |
| 023 | No Per-Room Overrides; Rate-Change-Driven Adjustments | Accepted | Only the org-wide standard amount is adjustable. |
| 024 | Partial-Month Billing Asymmetry | Accepted | Move-in skipped by default; move-out billed. |
| 025 | Debt Write-Offs, No Hard Deletes | Accepted | Audited zeroing of debt; no hard deletes. |
| 026 | Closed Tenancies Lose Portal Access | Accepted | Portal credentials permanently deactivated. |
| 027 | Property Dashboard Metrics | Accepted | Outstanding debt, room ratios, BEDC outflow. |
| 028 | Business Timezone | Accepted | One organization timezone for all month boundaries. |
---

## 17. Remaining Detailed Design Documents

The full planned document set is:

```text
docs/
│
├── 00-project-overview.md
├── 01-ai-development-guide.md
├── 02-requirements.md
├── 03-mvp-architecture.md
├── 04-database.md
├── 05-billing-engine.md
├── 06-transaction-ingestion.md
├── 07-api.md
├── 08-frontend.md
├── 09-security.md
├── 10-deployment.md
├── 11-testing.md
├── 12-roadmap.md
└── 13-doc-conventions.md
```

Document status:

- Written: `03-mvp-architecture.md`, `04-database.md`, `05-billing-engine.md`, `06-transaction-ingestion.md`, `09-security.md`, `10-deployment.md`, `13-doc-conventions.md`, and `docs/adr/` (ADR-001 through ADR-028).
- Not yet written: `00-project-overview.md`, `01-ai-development-guide.md`, `02-requirements.md`, `07`–`08`, and `11`–`12`.

---

## 18. Open Questions

The following items should be resolved before implementation of the relevant modules:

1. Which free hosting provider will be used? Resolved: the MVP choice is Render + Neon with an Oracle VM fallback (`10-deployment.md` §2).
2. Is the Payvice Avantus export format stable across billing-software versions?
3. Do the initial rate-limit and session-lifetime defaults in §8.2 hold up? Resolved: confirmed in `09-security.md` §5 and §6.
4. What "last exported" warning threshold applies? Set in `10-deployment.md`.

Resolved or relocated items:

- Statement formats: Payvice Avantus PDF plus manual entry only; CSV and XLSX are out of the MVP. Details in `06-transaction-ingestion.md`.
- Tenant session lifetime and access-attempt rate limiting: now MVP requirements (§8.2).
- Retaining original PDFs: no; a file hash is kept instead (§5.3, ADR-012).
- Backup export formats: full JSON export, optional per-table CSV (§5.3).
- Payment allocation and correction edge cases: `05-billing-engine.md`.
- The PDF is confirmed text-based with a control-total row. A sample has been provided.
- Property view totals: outstanding debt and fully-paid ratios (ADR-027).
- Bill adjustments: auto-generated public note with optional custom note; admin identity visible to tenants.
- Closed tenancies lose portal access (ADR-026).

---

## 19. Summary of Locked MVP Rules

A checklist of the rules above; each item is defined in the cited section.

- Two ledgers, never settling each other: §3 (ADR-017).
- Sources: Payvice Avantus PDF plus manual entry; staged and admin-confirmed: §10.1 (ADR-014).
- `COMMISSION` is never persisted or logged; control-total mismatch blocks confirm: §10.1 (ADR-019).
- Bills are generated lazily through one idempotent function, never by the tenant portal: §5.2.1 (ADR-022).
- Uniform standard amount; adjustments only by rate change or write-off: §10.3 (ADR-023, ADR-010, ADR-025).
- Allocation is oldest-outstanding-first; advance credit is derived and logged: §10.3 (ADR-020, ADR-021).
- Month boundaries use the organization timezone: §10.4 (ADR-028).
- Privacy boundary is the tenancy; other rooms see aggregates by default; enforced server-side: §9 (ADR-008, ADR-011).
- Shared, generated, room-scoped access codes with DB-backed rate limiting and expiring sessions; closed tenancies lose access: §8.2 (ADR-009, ADR-026).
- Utility providers and import profiles are global registries (ADR-016); the standard amount is organization-wide.
- Free-tier compatible: no cron, workers, webhooks or persistent local files; export is the backup: §5.3 (ADR-012).
- Every query path filters by `organization_id`: §12, §14.4.
