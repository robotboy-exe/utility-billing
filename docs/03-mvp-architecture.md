# Utility Billing MVP Architecture

Document: `docs/03-mvp-architecture.md`
Version: `0.8.0`
Status: Draft — consolidated source of truth for accepted MVP design decisions
Last Updated: 2026-09-16
Supersedes: `03-mvp-architecture.md` v0.2.0, the PDF scope-promotion amendment, and `03-mvp-architecture-amendment-002.md`, and absorbs utility-billing-arch.md (architecture.md v0.1.0)

## Document Lineage

This document is the single consolidated source of truth for the MVP architecture. It folds in:

- The original MVP architecture (v0.2.0).
- The PDF scope-promotion amendment, which made Payvice Avantus PDF import the primary ingestion source.
- Amendment 002, which established the two-ledger model, the Payvice Avantus ingestion rules, and the final billing-engine decisions.

Those amendment files are now retired. Any future change should be made here directly or through a new ADR.

Version 0.5.0 adds the advance movement ledger with its reconciliation invariant for fraud auditability, and clarifies that utility providers and import profiles are registered globally (system-wide).

Version 0.6.0 resolves the billing and tenancy product decisions: automatic rolling bill generation, removal of per-room bill overrides in favor of rate-change-driven adjustments and debt write-offs, the move-in/move-out partial-month asymmetry, closed-tenancy portal access, and the property dashboard metrics.

Version 0.7.0 absorbs the base architecture document (`utility-billing-arch.md`), folding in the architectural goals, guiding principles, core modules, transaction flow and source abstraction, deployment models, scalability strategy, and ADR-001 through ADR-007. The base document is retired; this file is now the single architecture source of truth.

> Version 0.8.0 refactors the document for leanness: extracts ADRs to `docs/adr/`, collapses domain model and visibility sprawl, replaces detailed billing/ingestion rules with pointers to `05` and `06`, and transforms the locked rules summary into a compact checklist.

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

The billing system must not depend on whether a transaction originated from a PDF statement, CSV file, Excel statement, Paystack webhook, Monnify webhook, bank API, or another source.

**Deployment-Agnostic**

The application should support:

- Centralized multi-tenant SaaS.
- Dedicated deployments.
- Single-tenant/self-hosted deployments.

The business logic must remain identical across these deployment models.

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

#### 2.2.6 Deployment Independence

No core business rule should behave differently depending on whether the application is running as SaaS, a dedicated installation, or a standalone installation.

### 2.3 MVP Scope Simplifications

However, the MVP intentionally simplifies the scope:

- One administrator is assumed initially.
- One organization is assumed initially, but organization-level isolation is preserved in the data model.
- Payvice Avantus PDF statement import is the primary transaction source.
- CSV and XLSX imports are demoted to secondary sources.
- Webhooks, payment provider integrations, and automated bank integrations are deferred.
- OCR / scanned-image PDF parsing is deferred.
- Full tenant user management is deferred.
- Background jobs and scheduled tasks are avoided where possible due to free-hosting constraints.

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
- Reporting is bounded by the payment's calendar month.
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
- CSV statement import (secondary).
- XLSX statement import (secondary, if practical).
- Manual transaction entry (also the fallback for failed parses).
- Utility provider registry with BEDC as the first provider.
- Utility bill payment recording and month-bounded spend reporting.
- Basic audit logging.
- Free-hosting-friendly deployment.

### 4.2 Out of scope for MVP

The following are deferred:

- Paystack integration.
- Monnify integration.
- Direct bank API integration.
- Google Sheets ingestion.
- OCR / scanned-image PDF parsing.
- Automated webhook processing.
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
- Dedicated customer environments.
- Offline/self-hosted deployments.

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
| No reliable background jobs | Billing generation, imports, and matching are manually triggered by the admin. |
| No reliable scheduled tasks | Monthly bills are generated manually, not automatically. |
| Ephemeral filesystem | Do not rely on uploaded files remaining on the server. Store normalized transaction records in the database. |
| Limited database storage | Keep financial records normalized and compact. Avoid storing original statement files unless explicitly required. |
| Limited request timeout | Imports must be small enough to process synchronously. PDF parsing is bounded by file size and page limits. |
| CPU/memory limits | Use lightweight text-extraction for PDF only. Reject scanned PDFs. Stage imports before commit. |
| Cold starts | The system should tolerate slow first requests. |
| Limited email capability | Do not require email for tenant access in MVP. |
| No webhook reliability | Defer payment provider webhooks. |

### 5.3 Backup strategy

Because free database tiers may have limited backup guarantees, the MVP should include export functionality.

Admin should be able to export key data, such as:

- Properties.
- Rooms.
- Tenancies.
- Tenants.
- Transactions.
- Monthly bills.
- Payment allocations.
- Utility bill payments.
- Adjustments.
- Audit logs, if practical.

Export formats may include CSV or JSON.

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

The exact provider should be chosen before implementation, but the MVP should fit this general shape:

| Component | Possible free hosting approach |
|---|---|
| Frontend | Static hosting, such as Cloudflare Pages, Vercel, or Netlify. |
| Backend | Free Python application host, such as Render, Koyeb, or similar. |
| Database | Free managed PostgreSQL, such as Neon, Supabase, or similar. |
| File storage | Avoided in MVP unless external object storage is added. |
| Email | Avoided in MVP. |
| Background jobs | Avoided in MVP. |

The business logic must remain independent of the selected hosting provider.

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

External transaction sources may include:

- CSV statements.
- XLSX statements.
- PDF statements.
- Google Sheets.
- Paystack.
- Monnify.
- Direct bank APIs.
- Manual entry.

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

- PDF (Payvice Avantus) — primary.
- CSV — secondary.
- XLSX — secondary, if practical.
- Manual entry — always available as a fallback for parse failures.

Planned:

- Google Sheets.
- Paystack webhooks.
- Monnify webhooks.
- Direct bank APIs.

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

- Global utility bill amount.
- Application configuration.
- Import profiles.
- Administrative operations.

#### 6.7.9 Authentication and Authorization

Responsible for:

- User authentication.
- Sessions/tokens.
- Organization membership.
- Roles and permissions.

The architecture should support multiple users per organization even if the first release has only one administrator.

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
CSV ───────────┐
XLSX ──────────┤
PDF ────────────┤
Google Sheets ──┤
Paystack ───────┤
Monnify ────────┤
Bank API ───────┤
Manual ─────────┘
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
- CSV parsing.
- XLSX parsing.
- PDF extraction.
- Paystack.
- Monnify.
- Bank APIs.

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
| Bill Adjustment | Recorded change to a bill's final amount (rate-change or write-off only). |
| Utility Provider | Global registry of utility companies (e.g., BEDC). |
| Utility Bill Payment | Outgoing payment to a provider. Does not settle tenant bills. |
| Import Profile | Global parser configuration (e.g., PAYVICE_AVANTUS). |
| Import Batch | Staged/confirmed import operation metadata. |
| Audit Log | Append-only record of admin/system actions. |

*Detailed schema, constraints, indexes, and exact field definitions are specified in `04-database.md`.*

---

## 8. Authentication & Authorization
The MVP uses a simplified auth model. Detailed session and credential schemas are in `04-database.md`.

**8.1 Roles**
- **Admin:** Full access. Email/password login (hashed). Server-side authorization.
- **Tenant Portal Session:** Read-only access to permitted tenant-facing information.

**8.2 Tenant Portal Access**
- **No full user management:** Tenants do not have passwords, profiles, or individual logins.
- **Shared access code:** Each tenancy gets a short, human-readable, hashed access code.
- **Concurrency:** Multiple roommates can use the same code simultaneously (sessions are per-device).
- **Delivery:** Admin generates and shares the code out-of-band (e.g., WhatsApp, SMS).
- **Revocation:** Resetting the code invalidates all existing tenant sessions.
- **Closure:** When a tenancy closes, its portal credential becomes permanently inactive. No historical access restoration.

---

## 9. Tenant Portal Visibility
Visibility is a policy concern enforced server-side. The frontend must not be trusted to hide data. Configuration is stored in the `portal_setting` table (see `04-database.md`).

**9.1 Privacy Boundary**
The privacy boundary is the **tenancy**. Members of the same tenancy see full details. Members of other tenancies see limited property-level billing info. Tenants cannot see other properties. Admin sees everything.

**9.2 Visibility Matrix**
| Information | Same tenancy | Other rooms (same property) | Other properties | Admin |
|---|---|---|---|---|
| Property/Room list & names | Visible | Visible | Hidden | Visible |
| Room billing amount/status | Visible | Visible | Hidden | Visible |
| Room bill adjustment notice | Visible | Visible | Hidden | Visible |
| Property utility spend | Visible | Visible | Hidden | Visible |
| Tenants & contact details | Visible | Hidden | Hidden | Visible |
| Tenancy bills/payments/transactions | Full | Hidden | Hidden | Visible |
| Audit log | Hidden | Hidden | Hidden | Visible |

**9.3 Default View & Flexibility**
- The default tenant view is the **Property view** (configurable to "Room view" later).
- Utility bill payment records and spend reports are property-level records visible to all tenants in that property.

---

## 10. Billing, Ingestion, and Matching
The system maintains two strictly separated ledgers: the **Tenant Payment Ledger** and the **Utility Bill Payment Ledger**. They never settle each other.

**10.1 Transaction Ingestion (Summary)**
- **Primary Source:** Payvice Avantus PDF (text-based only, no OCR).
- **Flow:** Two-phase (Upload/Parse -> Staged Batch -> Admin Preview -> Confirm).
- **Category Mapping:** Configuration-driven. `FUNDING` = tenant payment; `BEDC` = utility payment; `COMMISSION` = fully discarded (never stored/logged).
- *Detailed parser grammar, validation, and duplicate detection rules belong in `06-transaction-ingestion.md`.*

**10.2 Matching**
- Only `tenant_payment` rows enter matching (primarily via normalized sender aliases).
- `utility_bill_payment` rows bypass matching and go straight to provider spend reporting.

**10.3 Billing & Allocation (Summary)**
- **Generation:** Automatic and rolling (lazy generation triggered by dashboard/report usage).
- **Standard Amount:** Uniform across all rooms. No arbitrary per-room overrides.
- **Adjustments:** Only occur via global rate-changes (adjusting unsettled current-month bills by the delta) or debt write-offs. Fully audited and visible to tenants.
- **Partial Months:** Move-in partial months are unbilled by default (admin can opt-in). Move-out partial months are billed in full by default (admin can write-off post-closure).
- **Allocation:** Chronological, oldest-outstanding-first. Overpayments become advance credit.
- **Advance Ledger:** Advance balance is derived. Movements are recorded in an append-only ledger and reconciled for fraud detection.
- *Detailed allocation algorithms, edge cases, and correction workflows belong in `05-billing-engine.md`.*

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
- **Scoping:** Queries strictly scoped by `organization_id`, `property_id`, and `tenancy_id`.
- **Money Handling:** Single currency. All amounts stored as `BIGINT` minor units (e.g., ₦1,000 = 100000). No floating-point math.
- **Immutability:** Financial records (transactions, allocations, advance movements, audit logs) are append-only. Corrections use reversal/correction records, never silent rewrites.
- **Auditability:** Lightweight, append-only audit log for admin/system actions. Commission data is never logged. Tenants do not see the audit log.
- *Detailed security implementations belong in `09-security.md`.*

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
- Webhook endpoints.

### 14.3 Deployment independence

Business logic must not depend on the chosen free host.

The application should remain portable to:

- Paid hosting.
- A VPS.
- A managed platform.
- A dedicated deployment.

### 14.4 Deployment Models

The application should support three deployment models.

#### 14.4.1 Centralized SaaS

Multiple organizations use the same application infrastructure.

```text
                     Application
                          │
                   ┌──────┴──────┐
                   │              │
               Organization A  Organization B
                   │              │
                   └──────┬───────┘
                          │
                      Database
```

Data must be strictly isolated by organization.

This is the primary scalable commercial model.

#### 14.4.2 Dedicated Deployment

A customer receives an isolated deployment.

```text
Customer A
Application + Database

Customer B
Application + Database
```

The same application codebase can be deployed independently for each customer.

#### 14.4.3 Standalone / Self-Hosted

The application may eventually be packaged for customers who want to run it themselves.

The application architecture should not require this mode, but it should remain technically possible.

### 14.5 Scalability Strategy

The initial workload is expected to be relatively light.

The application primarily processes:

- Financial transaction records.
- Monthly billing records.
- Tenant information.
- Reports.

It does not require significant computational resources under normal usage.

The architecture should therefore prioritize simplicity and correctness rather than premature distributed infrastructure.

Initial scaling strategy:

```text
Reverse Proxy
      │
Application Server
      │
PostgreSQL
```

Scale horizontally only when actual usage requires it.

Potential future additions include:

- Multiple application instances.
- Managed PostgreSQL.
- Background job workers.
- Queue infrastructure.
- Object storage.
- Dedicated webhook processing.

### 14.6 Serverless Integrations (future / deferred)

Paystack and Monnify webhook endpoints may eventually be deployed as serverless functions. These integrations are outside the MVP scope.

These functions should:

1. Receive the webhook.
2. Verify its authenticity.
3. Validate the event.
4. Ensure idempotency.
5. Normalize the transaction.
6. Store or forward the transaction.
7. Trigger downstream processing.
8. Return an appropriate acknowledgement.

Webhook processing must be safe to retry.

The core billing logic should remain independent of whether webhook handling occurs in the main backend or a serverless function.

---

## 15. Testing Focus
Financial allocation scenarios, advance ledger reconciliation, and PDF parsing edge cases require extensive automated test coverage.
*Specific test scenarios and edge cases are defined in the Testing sections of `05-billing-engine.md` and `06-transaction-ingestion.md`.*

---

## 16. Architectural Decision Records (ADR Index)
The full Context, Decision, and Consequences for each ADR are stored in individual files in the `docs/adr/` directory.

| ADR | Title | Status | Summary |
|---|---|---|---|
| 001 | Organization as Root Entity | Accepted | Top-level boundary for customer data. |
| 002 | Multi-Tenant Architecture | Accepted | Supports SaaS, dedicated, and standalone. |
| 003 | Deployment-Model Independence | Accepted | Logic doesn't depend on hosting model. |
| 004 | Transaction Source Abstraction | Accepted | Normalizes all sources before billing. |
| 005 | Statement Imports as MVP | Superseded by ADR-014 | Superseded by ADR-014 (PDF primary). |
| 006 | Future Event-Driven Integrations | Accepted | Webhooks planned for future. |
| 007 | Billing Engine Independence | Accepted | Billing logic isolated from sources/UI. |
| 008 | Tenant Portal Visibility Boundary | Accepted | Privacy boundary is the tenancy. |
| 009 | Shared Tenancy Access Code | Accepted | Roommates share one code; no individual logins. |
| 010 | Rate-Change Adjustments and Write-Offs (revised) | Accepted (replaces the earlier per-bill-adjustment form) | No per-room overrides; systematic adjustments only. |
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
| 022 | Automatic Rolling Bill Generation (Lazy) | Accepted | Generated on-demand, not via scheduler. |
| 023 | No Per-Room Overrides; Rate-Change-Driven Adjustments | Accepted | Only global standard amount is adjustable. |
| 024 | Partial-Month Billing Asymmetry | Accepted | Move-in skipped by default; move-out billed. |
| 025 | Debt Write-Offs, No Hard Deletes | Accepted | Audited zeroing of debt; no hard deletes. |
| 026 | Closed Tenancies Lose Portal Access | Accepted | Portal credentials permanently deactivated. |
| 027 | Property Dashboard Metrics | Accepted | Outstanding debt, room ratios, BEDC outflow. |
---

## 17. Remaining Detailed Design Documents

The following detailed documents should be created before or during implementation:

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
└── 12-roadmap.md
```

The most important next documents are:

`04-database.md`
Detailed schema, constraints, indexes, relationships, staged import storage, allocation history, utility provider records, visibility settings, and tenant access credentials.

`05-billing-engine.md`
Billing state machine, allocation algorithm, adjustments, corrections, and edge cases.

`06-transaction-ingestion.md`
Payvice Avantus PDF import profile, category mapping, normalization, duplicate detection, and matching behavior.

`09-security.md`
Authentication, authorization, session handling, tenant visibility policy, and access code rules.

`10-deployment.md`
Free-hosting provider selection, environment configuration, migrations, and backup/export strategy.

---

## 18. Open Questions

The following items should be resolved before implementation of the relevant modules:

1. Which free hosting providers will be used?
2. What session lifetime should tenant sessions have?
3. What rate-limiting rules should apply to tenant access attempts?
4. Is the Payvice Avantus export format stable across billing-software versions?
5. Should original PDFs eventually be retained in object storage for dispute resolution?
6. What export formats are required for backup?

Resolved or relocated items:

- The first statement format is the Payvice Avantus PDF, not CSV. Detailed in `06-transaction-ingestion.md`.
- Payment allocation edge-case behavior is specified in `05-billing-engine.md`.
- Correction behavior after allocations is specified in `05-billing-engine.md`.
- XLSX is demoted to a secondary/future source.
- The PDF is confirmed text-based with a control-total row. A sample has been provided.
- Should property view show total outstanding balances, or only current-month amount due? → Resolved: both, with specific metrics (ADR-027).
- Should admin be required to provide a public note when adjusting a bill? → Resolved: auto-generated note with optional custom note.
- Should admin identity be visible to tenants for bill adjustments? → Resolved: yes.
- Should closed tenancies be allowed historical portal access? → Resolved: no (ADR-026).

---

## 19. Summary of Locked MVP Rules

**Architecture & Ledgers**
- [ ] Two strictly separated ledgers (Tenant Payment vs. Utility Bill Payment).
- [ ] Utility providers and Import profiles are global/system-wide registries.

**Ingestion**
- [ ] Payvice Avantus PDF is the primary source (text-based, staged, admin-confirmed).
- [ ] `FUNDING` = tenant payment; `BEDC` = utility payment; `COMMISSION` = discarded.

**Billing & Allocation**
- [ ] Lazy/rolling bill generation (no background schedulers).
- [ ] Uniform standard amount (no arbitrary per-room overrides).
- [ ] Adjustments limited to rate-changes and write-offs (fully audited/visible).
- [ ] Chronological, oldest-outstanding-first allocation.
- [ ] Advance credit is derived; movements logged in an append-only ledger.
- [ ] Move-in partial months unbilled by default; move-out billed in full by default.

**Visibility & Access**
- [ ] Privacy boundary is the tenancy.
- [ ] Shared access codes (no individual tenant logins).
- [ ] Closed tenancies permanently lose portal access.
- [ ] Visibility rules enforced server-side and configurable.

**Hosting**
- [ ] Free-tier compatible (no cron, no background workers, no persistent local files).
