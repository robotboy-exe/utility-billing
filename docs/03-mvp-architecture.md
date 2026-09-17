# Utility Billing MVP Architecture

Document: `docs/03-mvp-architecture.md`
Version: `0.7.0`
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
Organization
│
└── Property
      │
      └── Room
            │
            └── Tenancy
                  │
                  ├── Tenant
                  │
                  └── Sender Alias
```

Tenancy financial records attach to the appropriate tenancy. Utility provider records attach to the property/provider level.

### 7.1 Organization

Represents the landlord, property manager, or customer account.

For MVP:

- One default organization is assumed.
- The organization concept is still retained.
- All major records should be organization-scoped where appropriate.

This preserves future multi-tenant capability.

### 7.2 Property

Represents a physical property or building.

A property contains rooms.

The MVP should support multiple properties in the data model, even if only one property is used initially.

### 7.3 Room

Represents a physical room.

A room persists over time.

A room can have multiple historical tenancies but only one active tenancy at a time.

### 7.4 Tenancy

Represents a specific occupancy period for a room.

A tenancy:

- Belongs to one room.
- Has one or more tenants.
- Has a start date.
- May have an end date.
- Owns the financial history for that group of occupants.
- Is the privacy and access boundary for tenant portal access.

When all occupants leave, the tenancy is closed and a new tenancy is created for the next occupants.

Partial roommate changes do not automatically create a new tenancy when at least one existing occupant remains.

### 7.5 Tenant

Represents an individual occupant.

A tenancy can have multiple tenants.

For MVP:

- Tenant records are simple.
- Tenants do not have individual login accounts.
- Tenants access the portal through the shared tenancy access code.

### 7.6 Sender Alias

Represents an accepted sender name associated with a tenancy.

Sender aliases allow tenant payments to be recognized when they come from:

- A tenant's personal account.
- A parent.
- A spouse.
- A business account.
- Another authorized payer.

In the Payvice Avantus format, `FUNDING` rows carry only a sender name, so name-based sender aliases are the primary matching key.

### 7.7 Transaction

Represents a normalized source transaction.

Transactions are permanent financial records once committed.

Every persisted transaction carries a record category.

MVP persisted categories:

- `tenant_payment` — incoming tenant payments.
- `utility_bill_payment` — outgoing payments to utility providers.

Non-persisted categories:

- `ignored` — summarized but not stored as ledger entries.
- `excluded` — fully discarded (commissions).
- `unrecognized` — flagged for review.

The transaction source and category must not affect downstream billing behavior beyond routing to the correct ledger.

### 7.8 Monthly Bill

Represents the utility billing state for a tenancy and month.

A monthly bill:

- Belongs to one tenancy.
- Has a billing month.
- Has a standard amount.
- Has a final amount due.
- May be adjusted.
- Has payment allocations applied against it.

There must be only one monthly bill per tenancy per billing month.

### 7.9 Payment Allocation

Represents how a tenant payment transaction was distributed across monthly bills.

A single transaction may produce multiple allocations.

Example:

```text
₦6,000 tenant payment
→ May bill: ₦2,000
→ June bill: ₦2,000
→ July bill: ₦2,000
```

Payment allocations preserve the auditable connection between transactions and bills.

Allocations belong only to the Tenant Payment Ledger. Utility bill payments never produce tenant allocations.

### 7.10 Bill Adjustment

Represents a recorded change to a monthly bill's final amount. Bill adjustments are **not** arbitrary per-room overrides. In MVP an adjustment is created only in two situations: a standard-amount (rate) change, or a debt write-off.

A bill adjustment records:
- The affected bill.
- Adjustment type (`rate_change` or `write_off`).
- Previous amount.
- New amount.
- Public note (auto-generated, with optional custom note).
- Timestamp.
- Admin identifier, visible to tenants.

### 7.11 Utility Provider

Represents a utility company or bill recipient.

MVP provider:

- BEDC.

Future providers may include other electricity distributors, water providers, waste providers, or other utility categories.

Providers are registry-driven so new bill types can be added without hardcoding.

Providers are registered globally (system-wide). They are seeded once for the whole application rather than per organization, so future landlords automatically get registered providers. `organization_id` remains nullable, reserved for future per-org overrides.

### 7.12 Utility Bill Payment

Represents a payment made to a utility provider.

Conceptual fields:

- Source transaction.
- Provider.
- Customer/meter reference.
- Amount.
- Payment date/time.
- Spend month.
- Import batch.

### 7.13 Utility Spend Report

A derived report.

Groups utility bill payments by:

- Provider.
- Calendar month.

It does not reconcile tenant balances.

### 7.14 Import Profile

Represents a statement format parser and category mapping.

First profile:

- `PAYVICE_AVANTUS`.

Import profiles are configuration-driven where practical so new formats and category changes do not require rebuilding the parser or billing engine.

Import profiles are registered globally (system-wide). They are seeded once for the whole application rather than per organization, so future landlords automatically get the Payvice Avantus parser. `organization_id` remains nullable, reserved for future per-org overrides.

### 7.15 Import Batch

Represents one staged or confirmed import operation.

Stores:

- Statement metadata.
- Validation status.
- Persistable staged rows.
- Ignored-category summary.
- Duplicate-detection results.

Does not store commission data.

### 7.16 Audit Log

Records important administrative and system events.

Examples:

- Manual transaction matching.
- Manual transaction unmatching.
- Bill generation.
- Bill adjustment.
- Tenancy closure.
- Sender alias changes.
- Tenant access code reset.
- Configuration changes.

Audit records should be append-oriented.

---

## 8. Authentication and Authorization

The MVP requires authentication and authorization, but it does not require full user management.

### 8.1 Roles

The MVP defines two operational roles:

| Role | Purpose |
|---|---|
| Admin | Full access to manage the system. |
| Tenant Portal Session | Read-only access to permitted tenant-facing information. |

Anonymous users cannot view billing or tenant information.

---

## 9. Admin Authentication

Admin access requires secure authentication.

MVP assumptions:

- One admin user initially.
- Email and password login.
- Password must be hashed.
- Session or token must be securely handled.
- Admin actions must be authorized server-side.

The design should allow additional admin users later without rebuilding the authentication model.

---

## 10. Tenant Portal Authentication

The tenant portal uses a simplified access model.

### 10.1 No full tenant user management

Tenants do not have full user accounts.

The MVP does not provide:

- Tenant passwords.
- Tenant profile management.
- Tenant email verification.
- Tenant password reset.
- Individual tenant login, unless added later.

### 10.2 Shared tenancy access code

Each tenancy has a shared access code.

This is appropriate because roommates in the same tenancy are allowed to see the full tenancy details.

The access code authenticates access to the tenancy, not to an individual person.

### 10.3 Access code generation

When a tenancy is created or activated, the system should generate a tenancy access code.

The access code should be:

- Short.
- Human-readable.
- Free of confusing characters where practical.
- Stored hashed, not in plaintext.
- Resettable by admin.

### 10.4 Access code delivery

The system should minimize friction for giving tenants access.

The MVP flow is:

1. Admin creates or activates a tenancy.
2. System generates a tenancy access code.
3. System displays a shareable tenant access message.
4. Admin copies and sends it to tenants through an existing channel, such as:
   - WhatsApp.
   - SMS.
   - Printed notice.
   - Manual message.

The shareable message may include:

- Property name.
- Room reference.
- Portal URL.
- Access code.

Example conceptual message:

```text
Tenant Portal Access

Property: Sunshine Lodge
Room: Room 4
Portal: https://example.com/tenant?room=ROOM4
Access Code: 7K2M9Q
```

The portal URL may include a non-secret room reference to reduce typing.

The access code itself must not be included in a URL.

### 10.5 Concurrent tenant sessions

Multiple members of the same tenancy may use the same access code.

The system must allow multiple concurrent tenant sessions.

Sessions are per device/browser, not per individual tenant.

Because the access code is shared, the system cannot know which roommate is currently viewing.

This is acceptable for MVP because:

- Roommates are allowed to see the same tenancy information.
- The tenant portal is read-only.
- No sensitive tenant-initiated mutations are performed.

### 10.6 Session revocation

The system should allow tenant access to be revoked.

Recommended behavior:

- Resetting the tenancy access code invalidates existing tenant sessions.
- Deactivating the tenancy credential blocks new tenant sessions.
- Admin can reset the code if it is leaked or if occupants change.

This can be implemented using a credential version, session record, or equivalent revocation mechanism.

### 10.7 Tenancy closure and historical access

When a tenancy is closed, its portal credential becomes inactive **permanently**. Closed tenancies do **not** retain tenant portal access, and there is no historical-access restoration.

A tenancy closes in one of two ways:
- **Automatically:** when a new tenancy is created for the same room (only one active tenancy per room), the previous tenancy is closed.
- **Manually:** the admin closes the tenancy directly.

Closure sets the status to `closed`, records an end date, deactivates the portal credential, and **preserves all financial history**. Unpaid bills of closed tenancies remain visible to the admin, who may pursue the debt or write it off.

---

## 11. Tenant Portal Visibility Policy

The tenant portal visibility policy defines what a tenant may view.

This policy must be enforced server-side.

The frontend must not be relied upon to hide sensitive information.

---

## 12. Privacy Boundary

The privacy boundary is the tenancy.

Members of the same tenancy can see the full details of that tenancy.

Members of other tenancies can only see limited property-level billing information.

Tenants cannot see information from other properties.

Admin can see everything.

---

## 13. Visibility Rules

### 13.1 Same tenancy / roommates

Members of the same tenancy can see full tenancy details.

This includes:

- Room information.
- Tenancy dates.
- Tenancy status.
- Tenants in the same tenancy.
- Tenant contact details, if stored.
- Monthly bills.
- Payment history for that tenancy.
- Transactions belonging to that tenancy.
- Payment allocations.
- Sender aliases.
- Bill adjustments affecting that tenancy.

No tenancy detail is hidden from members of the same tenancy.

### 13.2 Other rooms in the same property

Tenants can see limited billing information for other rooms in the same property.

For now, this includes:

- Room identifier.
- Billing month.
- Amount due.
- Billing status.
- Whether the bill was adjusted.
- Final adjusted amount, if adjusted.

This supports property-level transparency.

Other tenants cannot see:

- Tenant names in other rooms.
- Tenant contact details in other rooms.
- Payment transaction details of other rooms.
- Sender aliases of other rooms.
- Payment references of other rooms.
- Admin notes.
- Audit logs.

### 13.3 Other properties

Tenants cannot see any information from properties they do not belong to.

### 13.4 Admin

Admin can see all information, including:

- All properties.
- All rooms.
- All tenancies.
- All tenants.
- All transactions.
- All bills.
- All allocations.
- All utility bill payments.
- All adjustments.
- Audit logs.
- Tenant access credential status, but not plaintext access codes.

---

## 14. Visibility Matrix

| Information | Same tenancy | Other rooms in same property | Other properties | Admin |
|---|---|---|---|---|
| Property name | Visible | Visible | Hidden | Visible |
| Room list in same property | Visible | Visible | Hidden | Visible |
| Room billing amount due | Visible | Visible | Hidden | Visible |
| Room billing status | Visible | Visible | Hidden | Visible |
| Room bill adjustment notice | Visible | Visible | Hidden | Visible |
| Property utility spend records | Visible | Visible | Hidden | Visible |
| Tenants in same tenancy | Visible | Hidden | Hidden | Visible |
| Tenant contact details in same tenancy | Visible | Hidden | Hidden | Visible |
| Tenancy bills | Full | Hidden | Hidden | Visible |
| Tenancy payments | Full | Hidden | Hidden | Visible |
| Tenancy transaction details | Full | Hidden | Hidden | Visible |
| Tenancy sender aliases | Full | Hidden | Hidden | Visible |
| Other tenancy tenant names | Hidden | Hidden | Hidden | Visible |
| Other tenancy payment details | Hidden | Hidden | Hidden | Visible |
| Audit log | Hidden | Hidden | Hidden | Visible |

---

## 15. Utility Record Visibility

Utility bill payment records and utility spend reporting are property-level records.

Default visibility:

- Admin can see all utility payment records.
- Tenants belonging to a property can see utility spend records for that property.
- Tenants cannot see utility records from other properties.

Future visibility changes are governed by the existing visibility policy mechanism.

---

## 16. Future Visibility Flexibility

The visibility rules must be configurable enough to support future changes.

Possible future changes include:

- Making room view the default instead of property view.
- Allowing tenants to verify transaction information.
- Allowing tenants to see anonymized property transactions.
- Allowing tenants to see payment references.
- Allowing tenants to see tenant names.
- Restricting property-level transparency.
- Adding individual tenant privacy controls.
- Adding fraud-transparency features.

To support this, the backend should treat visibility as a policy concern.

The system should not hardcode visibility rules only in the UI.

Recommended configuration concepts:

| Setting | MVP value |
|---|---|
| Tenant portal default view | Property |
| Allow tenant access to property billing summary | Yes |
| Allow tenant access to other rooms' amount due | Yes |
| Allow tenant access to other rooms' billing status | Yes |
| Allow tenant access to other rooms' adjustment notices | Yes |
| Allow tenant access to property utility spend records | Yes |
| Allow tenant access to other rooms' tenant names | No |
| Allow tenant access to other rooms' transactions | No |
| Allow tenant access to other rooms' payment references | No |

Future changes to visibility should be documented as an ADR or equivalent design decision.

---

## 17. Tenant Portal Default View

The tenant portal should support two primary views:

1. Property view.
2. My Room / My Tenancy view.

For MVP, the default view is:

```text
Property view
```

The tenant may also open:

```text
My Room / My Tenancy view
```

The default view must be configurable.

This allows the system to later change the default to the room view without rebuilding the portal.

Recommended setting:

| Setting | MVP default | Future possible value |
|---|---|---|
| Tenant portal default view | Property | Room |

The default view setting affects navigation only.

It does not replace server-side authorization.

---

## 18. Billing Model

The MVP uses a simple monthly billing model for the Tenant Payment Ledger.

Detailed allocation behavior belongs in `05-billing-engine.md`.

### 18.1 Standard monthly amount

There is a standard monthly utility amount.

For MVP:

- All active rooms are billed the same standard amount.
- The amount is the same every month unless changed by admin.
- The system should allow the standard amount to be changed.
- The data model should allow future property-specific amounts.

### 18.2 Bill generation

Bill generation is **automatic and rolling** (lazy generation).

The billing engine generates a month's bills automatically the first time they are needed — when the dashboard loads, when a payment is processed, or when a report is requested.

Rules:
- Bills are generated lazily/on-demand, not by a scheduled background job.
- Generation is idempotent: generating a bill that already exists does nothing.
- Generation happens synchronously in response to real usage, respecting the free-hosting constraint (no background scheduler).
- One bill per tenancy per month.
- Vacant rooms do not receive bills.
- Bills use the standard amount active at generation time.
- Manual generation remains available as an optional admin action for backfilling, but is not required for normal operation.

### 18.3 Rate-change adjustments (no per-room overrides)

There are **no arbitrary per-room bill amount adjustments.** The admin cannot pick a specific room and change just its amount.

The only adjustable billing parameter is the **standard monthly amount**, which applies uniformly to all active rooms.

When the admin changes the standard amount mid-month:
- The system calculates the delta between the old and new standard amounts.
- **Unsettled bills for the current month** are adjusted by the delta via recorded bill adjustments.
- **Future months** are generated at the new rate.
- **Fully-paid/settled bills are never adjusted** (no retroactive charges).
- **Past months are never adjusted, even if unpaid.**

All rate-change adjustments are:
- Recorded via append-only bill adjustment records — never a silent rewrite.
- Audited (who, when, old amount, new amount).
- Accompanied by an auto-generated public note ("Standard amount changed from ₦X to ₦Y"), with an optional custom note.
- Visible to tenants, including the admin's identity.

The model leaves room for future flexibility (e.g., new expense types) without changing this structure.

### 18.4 Partial-month billing (move-in / move-out asymmetry)

The asymmetry exists because of **when the information is available to the system.**

**Move-in partial month:**
- The admin sets the tenancy start date mid-month at creation time.
- At generation time the system can detect it is a partial month (start date ≠ 1st).
- **Default:** not billed.
- **Admin opt-in:** the admin can choose to bill it anyway, at the full standard amount.

**Move-out partial month:**
- At generation time the tenancy is still active with no end date; the system cannot know it will end mid-month.
- **Default:** billed in full (treated as a full month).
- After the tenancy closes, the admin can forego the final partial-month bill via a **write-off**.
- If the admin has foreknowledge of the move-out, they can manually exempt the bill (skip it).

**Billing overrides:**
- A per-tenancy, per-month billing override lets the admin force-bill or force-skip a tenancy for a specific month. This serves both the move-in opt-in and the move-out foreknowledge skip.

**Proration:**
- Proration is **not** automatic and **not** the default.
- The schema leaves room for future proration (`monthly_bill.final_amount` can differ from `standard_amount`), but MVP locks `final_amount = standard_amount`.

### 18.5 Payment allocation and the billing engine

The billing engine is the authoritative source of tenant billing state.

Locked rules:

- Tenant payments populate tenant billing records through allocation.
- Payments are processed chronologically.
- Bills are filled from oldest billing month to newest.
- Partial payments reduce outstanding balances.
- Overpayments create advance credit.
- Advance credit remains linked to the original payment.
- Advance credit is applied automatically to existing or newly generated bills.
- Advance credit movements are recorded in an append-only ledger and reconciled against the derived advance balance; mismatches are flagged as integrity errors.
- Payment date is not the billing month.
- The billing engine's reconciliation is final.
- Utility bill payments do not affect tenant billing balances.

The exact algorithm and edge cases are defined in `05-billing-engine.md`.

---

## 19. Bill Adjustment Transparency

Admin alterations to billing must be transparent.

### 19.1 What tenants can see

Adjustments arise only from rate changes or write-offs. For either, tenants can see:
- That the bill was adjusted and the adjustment type.
- The final amount due.
- The original or standard amount.
- An auto-generated public note, plus any custom note.
- The admin's identity.

### 19.2 What admin sees

Admin sees everything tenants see, plus:
- When the adjustment was made.
- Internal reason, if provided.
- Previous and new amounts.
- Related audit record.

### 19.3 No silent edits

Bill changes must not be silent.

If a bill amount changes after creation, the system should preserve:

- The original amount.
- The adjusted amount.
- The adjustment timestamp.
- The adjustment actor, for admin visibility.

If a bill already has payment allocations, adjustment rules must preserve financial integrity.

Detailed correction behavior belongs in `05-billing-engine.md`.

---

## 20. Transaction Ingestion

Detailed ingestion behavior belongs in `06-transaction-ingestion.md`.

### 20.1 MVP sources, in priority order

1. PDF (Payvice Avantus billing software export) — primary.
2. CSV — secondary.
3. XLSX — secondary, if practical.
4. Manual entry — always available; fallback for parse failures.

Deferred sources:

- Google Sheets.
- Paystack.
- Monnify.
- Direct bank APIs.
- OCR / scanned-image PDF parsing.

### 20.2 PDF-first design rules

- PDF import is implemented as a PDF import profile targeting the Payvice Avantus export format. The import-profile abstraction is retained so other formats can be added later.
- MVP supports text-based PDFs only. Scanned/image PDFs are rejected with a clear error message. Manual entry is the fallback.
- Uploads are bounded by maximum file size and maximum page count, sized to fit free-tier memory and request timeouts. Exact limits are finalized in `06-transaction-ingestion.md`.
- Commission rows are fully excluded and discarded.
- Category mapping is configuration-driven.
- Utility providers are registry-driven.

### 20.3 Two-phase import flow

Imports are two-phase:

```text
Upload PDF
   ↓
Parse + validate (synchronous, bounded)
   ↓
Staged import batch (preview rows, errors, counts)
   ↓
Admin reviews preview
   ↓
Confirm → transactions committed
```

The staged batch is stored in the database, so a cold start or restart between upload and confirm does not lose work.

### 20.4 File storage

Because free hosting may provide ephemeral storage, the MVP should not depend on retaining uploaded statement files.

The system should store:

- Normalized transaction rows.
- Import batch metadata.
- Row counts.
- Import errors.
- Import timestamp.
- Ignored-category summary.

The original PDF binary is not retained by default. Extracted rows are stored per import batch, preserving auditability and allowing re-parsing if the parser is later improved.

### 20.5 Category mapping

Parsed statement rows are mapped to system categories through configuration.

MVP mapping for the Payvice Avantus profile:

| Channel / direction | Category | System behavior |
|---|---|---|
| `FUNDING` credit | `tenant_payment` | Persist, match, allocate |
| `BEDC` debit | `utility_bill_payment` | Persist as utility bill payment |
| `TRANSFER` debit | `ignored` | Not recorded as ledger entry; summarized |
| `CHARGE` debit | `ignored` | Not recorded as ledger entry; summarized |
| `VAT` debit | `ignored` | Not recorded as ledger entry; summarized |
| `COMMISSION` any | `excluded` | Fully discarded |
| Unknown | `unrecognized` | Flagged for review |

Only `tenant_payment` and `utility_bill_payment` produce persisted transaction records.

### 20.6 Commission exclusion

Commission rows are fully ignored and discarded.

They are not stored, counted, displayed, logged, or reported.

The parser recognizes commission rows only to discard them.

---

## 21. Transaction Matching

Transaction matching identifies which tenancy a tenant payment belongs to.

Only transactions with category `tenant_payment` enter matching.

Utility bill payments never enter tenancy matching.

### 21.1 Matching inputs

Matching may use:

- Normalized sender name.
- Sender aliases.
- Reference text.
- Manual admin selection.

In the Payvice Avantus format, `FUNDING` rows carry only a sender name, so sender-name alias matching is the primary mechanism.

### 21.2 Matching states

A transaction may be:

- Unmatched.
- Ambiguous.
- Matched to a tenancy.
- Manually matched.
- Marked as irrelevant or non-utility, if supported later.

### 21.3 Manual matching

Admin can manually match unmatched transactions.

Manual matching actions should be audited.

Matching must not directly implement billing allocation rules.

---

## 22. Payment Allocation

Payment allocation connects matched tenant payments to monthly bills.

It belongs exclusively to the Tenant Payment Ledger.

### 22.1 MVP allocation approach

Locked rules:

- Allocate to the oldest unpaid bill first.
- Then allocate to the current month.
- Then allocate to future months if applicable.
- If money remains, record it as advance credit.
- Payments are processed chronologically.
- Payment date does not determine billing month.

The exact algorithm and edge cases are defined in `05-billing-engine.md`.

### 22.2 Allocation integrity

Payment allocations must:

- Reference an existing tenant payment transaction.
- Reference an existing monthly bill.
- Not exceed the transaction amount.
- Preserve history.
- Be auditable.

Corrections should use reversal or correction mechanisms rather than silent edits.

---

## 23. Reporting

Reports derive from authoritative records.

They must not maintain independent copies of financial truth.

### 23.1 Admin reports

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

### 23.2 Tenant portal reports

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

### 23.3 Utility spend report

A separate report derived from the Utility Bill Payment Ledger.

Groups utility bill payments by provider and calendar month.

Does not reconcile tenant balances.

---

## 24. Security Principles

The MVP must follow the security principles below.

### 24.1 Transport security

Production must use HTTPS.

### 24.2 Server-side authorization

All access must be authorized server-side.

The frontend must not be trusted to enforce visibility.

### 24.3 Organization scoping

Queries should be organization-scoped where appropriate.

Even if MVP uses one organization, the design should preserve organization isolation.

### 24.4 Property and tenancy scoping

Tenant portal access must be scoped to:

- The tenant's property.
- The tenant's tenancy.
- The visibility policy.

A tenant must not be able to request another tenancy's data by guessing an identifier.

### 24.5 Access code security

Tenant access codes must be:

- Hashed.
- Rate-limited.
- Resettable.
- Excluded from logs.
- Excluded from URLs.

### 24.6 Session security

Tenant sessions must:

- Expire.
- Be revocable.
- Be bound to a tenancy.
- Be read-only.
- Support multiple concurrent sessions.

Admin sessions must:

- Require secure authentication.
- Expire appropriately.
- Be separate from tenant sessions.

### 24.7 Secrets

Secrets must never be committed to source control.

Use environment variables or a suitable secrets mechanism.

Examples of secrets:

- Database connection string.
- Session signing secret.
- Admin bootstrap password.
- Future email provider credentials.
- Future payment provider keys.

---

## 25. Auditability

The MVP should maintain a lightweight audit log.

Audited events should include:

- Admin login.
- Manual transaction matching.
- Manual transaction unmatching.
- Bill generation.
- Bill adjustment.
- Tenancy closure.
- Sender alias changes.
- Tenant access code reset.
- Configuration changes.

Audit records should be append-oriented.

Tenants do not see the audit log in MVP.

Commission data must never appear in the audit log.

---

## 26. Data Integrity Requirements

The database should enforce integrity where practical.

Key requirements:

- One active tenancy per room.
- One monthly bill per tenancy per month.
- Payment allocations cannot exceed transaction amount.
- Transactions are not silently rewritten.
- Allocations preserve history.
- Financial operations should be atomic.
- Money amounts should be stored as integer minor units.
- A single currency is assumed for MVP.
- Foreign keys should be used where appropriate.
- Duplicate transaction detection should be supported.
- Duplicate statement detection should be supported.
- Advance credit balance is derived, and its movements are recorded in an append-only ledger that must reconcile with the derived balance.

---

## 27. Money Handling

The MVP should use a single currency.

Money amounts should be stored as integer minor units.

Example:

```text
₦1,000 = 100000 minor units
```

Floating-point arithmetic should not be used for financial calculations.

---

## 28. API Architecture

The backend should expose a REST API.

The API layer is responsible for:

- Request validation.
- Authentication.
- Authorization.
- Visibility enforcement.
- Serialization.
- Error handling.
- Invoking application services.

The API should not contain large amounts of business logic.

Conceptual endpoint groups:

Admin:

- Admin authentication.
- Property management.
- Room management.
- Tenancy management.
- Tenant management.
- Sender alias management.
- Bill generation.
- Bill adjustment.
- Transaction import.
- Transaction matching.
- Utility provider management.
- Reports.
- Audit log.
- Tenant access code management.

Tenant portal:

- Tenant access code verification.
- Tenant session creation.
- Tenant portal property summary.
- Tenant portal utility spend summary.
- Tenant portal own tenancy details.
- Tenant portal bill history.
- Tenant portal payment history.

All tenant endpoints must enforce the visibility policy.

---

## 29. Frontend Architecture

The frontend should be organized around user-facing domains.

Admin areas may include:

- Dashboard.
- Properties.
- Rooms.
- Tenancies.
- Tenants.
- Sender aliases.
- Transactions.
- Imports.
- Matching queue.
- Bills.
- Adjustments.
- Utility providers.
- Utility spend.
- Reports.
- Settings.
- Audit log.

Tenant portal areas may include:

- Tenant access page.
- Property view.
- Utility spend view.
- My Room / My Tenancy view.
- Bill history.
- Payment history.
- Access expired or invalid page.

Financial calculations displayed in the frontend must originate from backend data.

---

## 30. Deployment Architecture

The MVP should support simple deployment.

### 30.1 MVP deployment target

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

### 30.2 Deployment constraints

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

### 30.3 Deployment independence

Business logic must not depend on the chosen free host.

The application should remain portable to:

- Paid hosting.
- A VPS.
- A managed platform.
- A dedicated deployment.

### 30.4 Deployment Models

The application should support three deployment models.

#### 30.4.1 Centralized SaaS

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

#### 30.4.2 Dedicated Deployment

A customer receives an isolated deployment.

```text
Customer A
Application + Database

Customer B
Application + Database
```

The same application codebase can be deployed independently for each customer.

#### 30.4.3 Standalone / Self-Hosted

The application may eventually be packaged for customers who want to run it themselves.

The application architecture should not require this mode, but it should remain technically possible.

### 30.5 Deployment Independence

The application must not contain business logic that assumes:

- One organization.
- One property.
- One deployment.
- SaaS-only operation.
- Self-hosted-only operation.

Deployment configuration should determine how the application is hosted, while domain logic remains unchanged.

### 30.6 Multi-Tenant Architecture

For SaaS deployments, organization-level isolation is mandatory.

Conceptually:

```text
Organization A
├── Properties
├── Rooms
├── Tenancies
├── Transactions
└── Billing Records

Organization B
├── Properties
├── Rooms
├── Tenancies
├── Transactions
└── Billing Records
```

Application queries must always operate within the authenticated user's organization context.

The exact database-level isolation strategy will be defined in `04-database.md`.

### 30.7 Scalability Strategy

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

### 30.8 Serverless Integrations (future / deferred)

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

## 31. Testing Focus

Testing should cover both original architectural concerns and MVP-specific decisions.

Important test areas include:

- Payment allocation.
- Chronological oldest-outstanding-first ordering.
- Advance credit creation and application.
- Advance movement ledger reconciliation with the derived advance balance.
- Duplicate transaction detection.
- Duplicate statement detection.
- Sender alias matching.
- Bill generation idempotency.
- Bill adjustment visibility.
- Tenant visibility policy.
- Utility record visibility.
- Authorization boundaries.
- Concurrent tenant sessions.
- Access code reset invalidation.
- Property isolation.
- Tenancy isolation.
- Payvice Avantus PDF parsing.
- Category mapping.
- Commission exclusion.
- Control-total validation.
- Manual matching.
- Financial reporting accuracy.

Financial allocation scenarios should have strong automated test coverage.

---

## 32. Architectural Decision Records

ADR-001 through ADR-007 are listed below and remain relevant.

### ADR-001 — Organization as Root Entity

Status: Accepted.

Organizations provide the top-level boundary for customer data.

```text
Organization
    → Property
        → Room
            → Tenancy
                → Tenant
```

---

### ADR-002 — Multi-Tenant Architecture

Status: Accepted.

The application will be designed to support multi-tenant SaaS deployments.

The same architecture must also support dedicated and standalone deployments.

---

### ADR-003 — Deployment-Model Independence

Status: Accepted.

Business logic must not depend on whether the application is deployed as SaaS, dedicated, or standalone.

---

### ADR-004 — Transaction Source Abstraction

Status: Accepted.

All transaction sources must normalize into a common transaction representation before entering the core business logic.

---

### ADR-005 — Statement Imports as MVP

Status: Superseded by ADR-014.

CSV and XLSX statement imports are the initial transaction ingestion mechanism.

---

### ADR-006 — Future Event-Driven Integrations

Status: Accepted.

Paystack and Monnify webhooks are planned future transaction sources.

Serverless functions may be used for webhook ingestion where appropriate.

---

### ADR-007 — Billing Engine Independence

Status: Accepted.

The billing engine must remain independent of transaction source, frontend, and API implementation details.

---

Note: ADR-005 (Statement Imports as MVP) is amended by ADR-014 below. PDF is now the primary MVP ingestion source; CSV and XLSX remain secondary.

The following MVP-specific ADRs are recorded here.

### ADR-008 — Tenant Portal Visibility Boundary

Status: Accepted.

Context:

Tenants need secure access to billing information without exposing other tenants' personal or transaction details.

Decision:

The privacy boundary is the tenancy.

Members of the same tenancy can see full tenancy details.

Tenants in other rooms of the same property can see limited billing information, such as amount due, billing status, and adjustment notices.

Tenants cannot see information from other properties.

Admin can see everything.

Consequences:

- The backend must enforce tenancy and property scopes.
- The visibility policy must be server-side.
- Future visibility changes can be introduced through policy configuration.

### ADR-009 — Shared Tenancy Access Code

Status: Accepted.

Context:

Tenants need secure read-only access without full user management.

Decision:

Each tenancy uses a shared access code.

Roommates in the same tenancy may use the same code.

Multiple concurrent sessions are allowed.

Sessions are issued per device/browser.

Resetting the access code invalidates existing sessions.

Consequences:

- The system cannot identify individual tenants by session.
- Tenant portal actions are limited to read-only operations.
- Access code reset is the primary revocation mechanism.
- Individual tenant credentials may be added later if required.

### ADR-010 — Rate-Change Adjustments and Write-Offs (revised)
Status: Accepted (replaces the earlier per-bill-adjustment form).

Context:
Arbitrary per-room bill overrides are fraud-prone and are removed. Adjustments must still be possible for legitimate reasons and must stay transparent.

Decision:
There are no arbitrary per-room bill amount overrides. Adjustments occur only as (a) rate-change adjustments, applied uniformly to unsettled current-month bills, or (b) debt write-offs. All adjustments are append-only, audited, preserve the original amount, carry an auto-generated public note with an optional custom note, and show the admin's identity to tenants.

Consequences:
- Bills support typed adjustment metadata (`rate_change`, `write_off`).
- Silent rewriting of bill amounts is not allowed.
- The tenant portal displays adjustment notices with admin identity.

### ADR-011 — Configurable Tenant Portal Default View

Status: Accepted.

Context:

The tenant portal should default to property-wide transparency now, but may later default to the room view.

Decision:

The tenant portal supports:

- Property view.
- My Room / My Tenancy view.

The default view is configurable.

MVP default is the property view.

Consequences:

- The frontend should not hardcode the default view.
- Changing the default later should be a configuration change.
- Authorization remains independent of the default view.

### ADR-012 — Free-Hosting Synchronous MVP

Status: Accepted.

Context:

The MVP is expected to run on free-tier hosting.

Free hosting may not support background jobs, cron jobs, persistent local files, or reliable email delivery.

Decision:

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

Consequences:

- The system must tolerate cold starts.
- Imports must be small enough to process synchronously.
- Original statement files are not retained by default.
- Export functionality is used as a backup strategy.

### ADR-013 — No Full Tenant User Management in MVP

Status: Accepted.

Context:

The product should remain simple.

Full tenant user management is not required initially.

Decision:

Tenants access the portal through tenancy access codes.

The MVP does not implement:

- Tenant passwords.
- Tenant profiles.
- Tenant password resets.
- Tenant self-registration.
- Individual tenant credentials.

Consequences:

- Simpler implementation.
- Lower friction for tenants.
- Less administrative overhead.
- Limited individual accountability.
- Future individual tenant access may require a new ADR.

### ADR-014 — PDF Statement Import as Primary MVP Ingestion Source

Status: Accepted.

Context:

The billing software that settles the utility bills exports statements only as PDF. PDF is therefore more important than CSV, XLSX, or Google Sheets. The original architecture and MVP v0.2.0 deferred PDF parsing.

Decision:

PDF import is a must-have MVP feature and the primary transaction source. It is implemented as a PDF import profile for the Payvice Avantus export format. MVP supports text-based PDFs only (no OCR). Imports are staged with admin preview and confirmation before transactions are committed. File size and page limits apply to fit free-tier hosting.

Consequences:

- The Transaction Ingestion module carries real parser complexity and needs strong test coverage.
- Sample PDFs from the billing software are on the critical path for design and testing.
- Free-tier CPU/memory limits shape parser library choice and upload limits.
- Extracted rows are retained per import batch for audit and re-parse; PDF binaries are not retained by default.
- Scanned PDFs require manual entry or a future OCR decision.

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

### ADR-016 — Utility Provider Registry

Status: Accepted.

Context:

BEDC is the first utility provider, but future bill types are expected.

Decision:

Utility bill payments are recorded through a provider registry.

BEDC is the first registered provider.

Future bill types and providers can be added without hardcoding.

Consequences:

- Provider data is registry-driven.
- Adding a provider does not require billing-engine changes.

### ADR-017 — Separate Tenant Payment and Utility Bill Payment Ledgers

Status: Accepted.

Context:

Tenant payments and provider payments serve different purposes and must not be conflated.

Decision:

Tenant payments populate tenant billing records.

Utility bill payments populate separate provider spend reporting.

The two ledgers do not settle each other.

Consequences:

- Tenant billing state stays clean.
- Provider payments serve as proof-of-payment / spend records.
- Reporting is split into tenant billing and utility spend.

### ADR-018 — Payment Date Does Not Determine Billing Month

Status: Accepted.

Context:

Tenants pay late, so the payment date does not reliably indicate which month the payment is for.

Decision:

The billing engine determines which monthly bill a payment settles.

Payment date is only the receipt date.

Late payments may settle earlier billing months.

Consequences:

- Allocation, not date, determines billing month.
- Reports must show both receipt date and allocated billing month.

### ADR-019 — Commission Rows Fully Excluded

Status: Accepted.

Context:

Commission rows are agent income and must never enter the system.

Decision:

Commission rows are discarded during parsing.

They are not stored, counted, displayed, logged, or reported.

Consequences:

- The parser recognizes commission rows only to discard them.
- No commission data persists anywhere.
- Control-total validation may transiently account for commissions without retaining them.

### ADR-020 — Chronological Oldest-Outstanding-First Allocation

Status: Accepted.

Context:

Tenant payments must populate billing records deterministically.

Decision:

Tenant payments are processed chronologically.

Payments fill outstanding bills from oldest billing month to newest.

Remaining payment amount becomes advance credit.

Consequences:

- Allocation is deterministic and reproducible.
- Advance credit remains linked to the original payment.
- Detailed behavior is specified in `05-billing-engine.md`.

### ADR-021 — Advance Movement Ledger and Reconciliation

Status: Accepted.

Context:

Advance credit is derived from payments and allocations. To make it auditable and tamper-evident for fraud detection, an independent append-only record is needed.

Decision:

The advance balance remains derived and is never stored as a mutable value. Every advance event (created, applied, reversed) is written to an append-only advance movement ledger in the same transaction as the corresponding allocation. The system reconciles the derived balance against the movement ledger, and any mismatch is flagged as an integrity error.

Consequences:

- Advance credit is auditable and tamper-evident.
- No second mutable source of truth is introduced.
- Reconciliation provides fraud detection.

### ADR-022 — Automatic Rolling Bill Generation (Lazy)

Status: Accepted.

Context: Free hosting cannot run scheduled jobs, but billing should feel automatic and rolling.

Decision: Bills are generated lazily/on-demand the first time the system needs them (dashboard load, payment processing, report request). Generation is idempotent and synchronous, requiring no background scheduler.

Consequences: No manual monthly action is needed. The "manual generation" point in ADR-012 is revised. Reports trigger generation to stay accurate.

### ADR-023 — No Per-Room Overrides; Rate-Change-Driven Adjustments

Status: Accepted.

Context: Per-room amount overrides are fraud-prone. Only the global standard amount should be adjustable.

Decision: The standard monthly amount is the only adjustable billing parameter. When it changes, unsettled current-month bills are adjusted by the delta via recorded adjustments. Settled bills and past months are never adjusted.

Consequences: Adjustments are uniform, systematic, and transparent. Arbitrary per-room overrides are not possible.

### ADR-024 — Partial-Month Billing Asymmetry

Status: Accepted.

Context: The system knows about move-in at creation time but only learns of move-out after the fact.

Decision: A move-in partial month is not billed by default (admin can opt in). A move-out partial month is billed in full by default (admin can forego via write-off after closure, or exempt with foreknowledge). A per-tenancy, per-month billing override supports both.

Consequences: Billing reflects what the system knows at generation time. Admin overrides handle real-world exceptions.

### ADR-025 — Debt Write-Offs, No Hard Deletes

Status: Accepted.

Context: Closed tenancies may leave unpaid debt the admin chooses to forego.

Decision: Foregoing debt is an audited write-off that zeroes the outstanding balance. Financial records are never hard-deleted, so history stays verifiable and auditable.

Consequences: Write-offs are recorded as typed bill adjustments. Closed-tenancy debt persists for pursuit or write-off.

### ADR-026 — Closed Tenancies Lose Portal Access

Status: Accepted.

Context: Old access codes must not expose current property information after occupants leave.

Decision: When a tenancy closes, its portal credential becomes permanently inactive. There is no historical-access restoration.

Consequences: Closed tenancies cannot view the portal. Admin retains the records for pursuit or write-off.

### ADR-027 — Property Dashboard Metrics

Status: Accepted.

Context: Tenants need a transparent property-level view of billing and utility spend.

Decision: The property view shows total outstanding debt, total room count, fully-paid room count, a clearly labeled fully-paid/total ratio, current-month utility spend (BEDC outflow), and historical utility spend (BEDC outflow) as the only historical data.

Consequences: Historical figures come from the Utility Bill Payment Ledger, not tenant payments. Historical months expose totals only, no room counts.

---

## 33. Remaining Detailed Design Documents

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

## 34. Open Questions

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

## 35. Implementation Sequence

The MVP should be implemented incrementally.

Recommended sequence:

```text
Requirements
   ↓
Architecture
   ↓
Database Design
   ↓
Billing Engine Design
   ↓
Transaction Ingestion Design
   ↓
Core Backend
   ↓
API
   ↓
Frontend
   ↓
Authentication / Authorization
   ↓
Testing
   ↓
Deployment
```

Authentication and authorization design should be considered early because tenant visibility and access rules affect API and database design.

Transaction Ingestion Design starts with the Payvice Avantus PDF import profile, before CSV/XLSX.

No significant architectural change should be made silently. Significant changes must be documented as ADRs.

---

## 36. Summary of Locked MVP Rules

The following rules are now considered locked for MVP design.

Architecture and ledgers:

1. The system maintains two separate ledgers: Tenant Payment Ledger and Utility Bill Payment Ledger.
2. Tenant payments populate tenant billing records through allocation.
3. Utility bill payments populate month-bounded provider spend reporting.
4. The two ledgers do not settle each other.
5. Utility providers are registry-driven and registered globally (system-wide); BEDC is the first provider.

Ingestion:

6. Payvice Avantus PDF is the primary statement source.
7. CSV, XLSX, and manual entry remain supported as secondary sources.
8. MVP PDF parsing supports text-based PDFs only; no OCR.
9. PDF imports use staged preview and admin confirmation before commit.
10. Extracted statement content is retained per import batch; PDF binaries are not retained by default.
11. `FUNDING` credits are tenant payments.
12. `BEDC` debits are utility bill payments.
13. `TRANSFER`, `CHARGE`, and `VAT` are ignored for now but configurable later.
14. Commission rows are fully discarded.
15. Category mapping is configuration-driven.

Billing:

16. Tenant payments are matched to tenancies by sender alias.
17. Matched tenant payments are allocated by the billing engine.
18. Allocation is chronological and oldest-outstanding-first.
19. Partial payments reduce outstanding balances.
20. Overpayments become advance credit.
21. Advance credit remains linked to the original payment and is applied automatically to existing or newly generated bills.
22. Advance credit movements are recorded in an append-only ledger and reconciled against the derived balance; mismatches are flagged.
23. Payment date does not determine billing month.
24. The billing engine's reconciliation is final.
25. Monthly bills use a uniform standard amount; there are no arbitrary per-room overrides.
26. Bill generation is manual and idempotent.
27. Existing bills are not silently rewritten when the standard amount changes.
28. Bill generation is automatic and rolling (lazy), not manual.
29. Rate changes adjust unsettled current-month bills by the delta; settled bills and past months are never adjusted.
30. Rate-change adjustments carry an auto-generated public note and show the admin's identity.
31. A move-in partial month is not billed by default; admin can opt in.
32. A move-out partial month is billed in full by default; admin can forego via write-off after closure.
33. Foregone debt is written off via an audited action; records are never hard-deleted.
34. Proration is not automatic; the schema preserves room for it in the future.

Visibility and access:

35. Tenant portal default view is the property view.
36. Tenants can also view their own tenancy/room details.
37. Roommates in the same tenancy can see full tenancy details.
38. Tenants in other rooms can see limited billing information for other rooms.
39. Other-room visibility includes amount due, billing status, and adjustment notices.
40. Tenant personal information in other rooms is hidden.
41. Tenants can see property-level utility spend records for their property.
42. Tenants cannot see information from other properties.
43. Admin can see everything.
44. Visibility rules are enforced server-side and are configurable for future changes.
45. Admin bill adjustments are visible to tenants.
46. Bill adjustments preserve historical amounts and are audited.
47. Tenancy access uses a shared access code.
48. Multiple concurrent tenant sessions are allowed.
49. Tenant sessions are read-only.
50. Resetting the access code invalidates existing tenant sessions.
51. Closed tenancies permanently lose tenant portal access.

Hosting:

52. The MVP avoids background jobs, webhooks, scheduled tasks, and email dependencies.
53. The MVP is designed to run on free-tier hosting while preserving portability.