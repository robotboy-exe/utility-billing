System Architecture

Document: "architecture.md"
Version: 0.1.0
Status: First Pass / Draft
Last Updated: 2026-08-08

---

1. Purpose

This document defines the high-level architecture of the tenancy-based utility billing and payment ledger application.

The application is designed for landlords or property managers who need to:

- Maintain a register of rooms and tenants.
- Record incoming tenant payments.
- Import transactions from bank statements.
- Match incoming payments to the appropriate tenancy.
- Automatically allocate payments against monthly utility bills.
- Track outstanding debt, current payments, and advance payments.
- Preserve complete historical financial records.
- Generate reports showing the current financial state of each active tenancy.

This document defines the system structure and major architectural decisions. Detailed business rules and implementation specifications belong in dedicated documents.

---

2. Architectural Goals

The system should be:

Correct

Financial calculations and payment allocations must be deterministic, auditable, and reproducible.

Modular

Business domains should be separated so that changes to one subsystem do not unnecessarily affect others.

Source-Agnostic

The billing system must not depend on whether a transaction originated from a CSV file, Excel statement, Paystack webhook, Monnify webhook, bank API, or another source.

Deployment-Agnostic

The application should support:

- Centralized multi-tenant SaaS
- Dedicated deployments
- Single-tenant/self-hosted deployments

The business logic must remain identical across these deployment models.

Extensible

The architecture should allow future features such as:

- Multiple properties
- Multiple utility categories
- Additional payment providers
- Direct bank integrations
- Notifications
- Mobile applications
- Additional reporting and export formats

Maintainable

The system should be structured so that both human developers and AI coding assistants can understand and modify individual modules without needing to reason about the entire application simultaneously.

---

3. Guiding Principles

3.1 Business Logic First

Financial and tenancy rules take precedence over UI considerations.

3.2 Separation of Concerns

The following concerns should remain separate:

- Presentation
- API
- Business logic
- Data access
- External integrations
- Persistence

3.3 Domain Isolation

Major business domains should have clear boundaries.

For example, the billing engine should not contain bank statement parsing logic.

3.4 Immutable Financial History

Transactions and historical payment allocations must be preserved.

Corrections should be represented through controlled correction/reversal mechanisms rather than silently rewriting historical financial data.

3.5 Single Source of Truth

Each important piece of information should have one authoritative representation.

For example, a transaction should be stored once and referenced by payment allocations rather than duplicated into every monthly bill.

3.6 Deployment Independence

No core business rule should behave differently depending on whether the application is running as SaaS, a dedicated installation, or a standalone installation.

---

4. System Context

At a high level:

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

External transaction sources may include:

- CSV statements
- XLSX statements
- PDF statements
- Google Sheets
- Paystack
- Monnify
- Direct bank APIs
- Manual entry

---

5. High-Level Application Architecture

The initial technology architecture is:

┌────────────────────────────────────────────┐
│                  Browser                   │
│                                            │
│             React + TypeScript             │
└──────────────────────┬─────────────────────┘
                       │
                       │ HTTPS / REST API
                       ▼
┌────────────────────────────────────────────┐
│                 FastAPI                    │
│                                            │
│  API Layer                                 │
│       ↓                                    │
│  Application Services                      │
│       ↓                                    │
│  Domain / Business Logic                   │
│       ↓                                    │
│  Data Access                               │
└──────────────────────┬─────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────┐
│                 PostgreSQL                 │
└────────────────────────────────────────────┘

The backend will use Python.

The frontend will be a separate web application communicating with the backend through an API.

---

6. Technology Stack

Frontend

Initial recommendation:

- React
- TypeScript
- Vite

Responsibilities:

- User interface
- Navigation
- Forms
- Tables
- Dashboards
- Reports
- API interaction
- Client-side presentation state

The frontend should not contain authoritative financial business logic.

---

Backend

Initial recommendation:

- Python
- FastAPI

Responsibilities:

- API endpoints
- Authentication and authorization
- Business workflows
- Validation
- Transaction processing
- Tenant matching
- Payment allocation
- Reporting queries
- Integration with external transaction sources

---

Database

Initial recommendation:

- PostgreSQL

SQLite may be used during early local development where appropriate, but PostgreSQL should be treated as the production database target.

---

ORM / Database Tooling

Initial recommendation:

- SQLAlchemy
- Alembic

SQLAlchemy will provide the application data-access/model layer.

Alembic will manage database schema migrations.

---

Deployment

Initial deployment architecture should support containerization:

- Docker
- Reverse proxy such as Nginx
- PostgreSQL
- HTTPS

The exact infrastructure provider is intentionally not fixed at this stage.

---

7. Domain Model

The application should use the following hierarchy:

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

Financial records attach to the appropriate tenancy.

---

7.1 Organization

Represents the landlord, property manager, or customer account.

This is the root of tenant isolation.

An organization owns:

- Properties
- Users
- Rooms
- Tenancies
- Transactions
- Billing records
- Reports
- Configuration

The Organization abstraction enables the same codebase to support multiple customers.

---

7.2 Property

Represents a physical property or building managed by an organization.

A property contains one or more rooms.

Although the first version may be used for a single property, the architecture should support multiple properties.

---

7.3 Room

Represents the physical room.

A room persists even when its occupants change.

A room can have multiple historical tenancies but only one active tenancy at a time.

---

7.4 Tenancy

Represents a specific occupancy period for a room.

A tenancy:

- Belongs to one room.
- Has one or more tenants.
- Has a start date.
- May have an end date.
- Owns the financial history associated with that group of occupants.

When all occupants leave, the tenancy is closed and a new tenancy is created for the next occupants.

---

7.5 Tenant

Represents an individual occupant.

A tenancy can have multiple tenants.

Partial roommate changes do not create a new tenancy when at least one existing occupant remains.

---

7.6 Sender Alias

Represents an accepted bank sender name associated with a tenancy.

Multiple sender aliases may belong to the same tenancy.

This accommodates situations where a tenant's payment may come from:

- Their own bank account.
- A parent.
- A spouse.
- A business account.
- Another authorized payer.

---

7.7 Transaction

Represents an incoming payment received from an external transaction source.

Transactions should be retained as permanent financial records.

A transaction may originate from:

- Statement import
- Payment provider webhook
- Bank API
- Manual entry
- Other future integrations

The transaction source should not affect downstream billing behavior.

---

7.8 Monthly Bill

Represents the utility billing state for a specific tenancy and month.

The initial system uses a single global monthly utility amount shared across rooms.

A future architecture may support property-specific or utility-specific amounts.

---

7.9 Payment Allocation

Represents how an incoming transaction was distributed across monthly bills.

A single transaction may produce multiple payment allocations.

For example:

₦6,000 transaction

→ May bill:    ₦2,000
→ June bill:   ₦2,000
→ July bill:   ₦2,000

This provides an auditable connection between the original transaction and the bills it settled.

---

7.10 Audit Log

Records important administrative actions and system events.

Examples:

- Manual transaction matching
- Tenant changes
- Tenancy closure
- Configuration changes
- Corrections
- Reversals

---

8. Core Modules

The application should be divided into domain-oriented modules.

Organization
Property
Tenancy
Transaction Ingestion
Transaction Matching
Billing
Reporting
Administration
Authentication
Audit

---

8.1 Organization Module

Responsible for:

- Organizations
- Organization configuration
- Organization-level isolation

---

8.2 Property Module

Responsible for:

- Properties
- Rooms
- Property configuration

---

8.3 Tenancy Module

Responsible for:

- Tenancies
- Tenants
- Tenant changes
- Sender aliases
- Tenancy lifecycle

---

8.4 Transaction Ingestion Module

Responsible for obtaining transactions from external sources.

MVP:

- CSV
- XLSX

Planned:

- PDF
- Google Sheets
- Paystack webhooks
- Monnify webhooks
- Direct bank APIs

All sources must be normalized into the application's standard transaction model.

Detailed ingestion architecture belongs in "transaction-ingestion.md".

---

8.5 Transaction Matching Module

Responsible for:

- Matching sender names to sender aliases.
- Identifying the associated tenancy.
- Handling unmatched transactions.
- Supporting manual matching.

Matching must not directly implement billing allocation rules.

---

8.6 Billing Module

Responsible for:

- Monthly bills
- Payment allocation
- Outstanding debt
- Current-month payments
- Advance payments
- Partial payments
- Billing status

This is the core financial business domain.

Detailed rules belong in "billing-engine.md".

---

8.7 Reporting Module

Responsible for presenting information such as:

- Rooms fully paid
- Rooms owing
- Amount owed
- Current-month payment status
- Advance payments
- Payment history
- Transaction history

Reports should derive their data from authoritative records rather than maintain independent copies of financial state.

---

8.8 Administration Module

Responsible for:

- Global utility bill amount
- Application configuration
- Import profiles
- Administrative operations

---

8.9 Authentication and Authorization

Responsible for:

- User authentication
- Sessions/tokens
- Organization membership
- Roles and permissions

The architecture should support multiple users per organization even if the first release has only one administrator.

---

8.10 Audit Module

Responsible for recording important actions affecting the system.

Audit records should be append-oriented and should not be casually editable.

---

9. Transaction Flow

The generalized transaction flow is:

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

The same flow should apply regardless of whether the source is a statement import or a future webhook.

---

10. Transaction Source Abstraction

The system must separate transaction acquisition from transaction processing.

Conceptually:

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

Adding a new transaction source should not require modifications to the billing engine.

---

11. Billing Independence

The Billing Engine must not depend on:

- React
- FastAPI request handlers
- CSV parsing
- XLSX parsing
- PDF extraction
- Paystack
- Monnify
- Bank APIs

The Billing Engine should operate on domain-level data.

This allows it to be tested independently from the user interface and external integrations.

---

12. Deployment Architecture

The application should support three deployment models.

12.1 Centralized SaaS

Multiple organizations use the same application infrastructure.

                    Application
                         │
                  ┌──────┴──────┐
                  │              │
              Organization A  Organization B
                  │              │
                  └──────┬───────┘
                         │
                     Database

Data must be strictly isolated by organization.

This is the primary scalable commercial model.

---

12.2 Dedicated Deployment

A customer receives an isolated deployment.

Customer A
Application + Database

Customer B
Application + Database

The same application codebase can be deployed independently for each customer.

---

12.3 Standalone / Self-Hosted

The application may eventually be packaged for customers who want to run it themselves.

The application architecture should not require this mode, but it should remain technically possible.

---

13. Deployment Independence

The application must not contain business logic that assumes:

- One organization.
- One property.
- One deployment.
- SaaS-only operation.
- Self-hosted-only operation.

Deployment configuration should determine how the application is hosted, while domain logic remains unchanged.

---

14. Multi-Tenant Architecture

For SaaS deployments, organization-level isolation is mandatory.

Conceptually:

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

Application queries must always operate within the authenticated user's organization context.

The exact database-level isolation strategy will be defined in "database.md".

---

15. Data Integrity

Financial records require strong integrity guarantees.

The system should:

- Use database constraints where appropriate.
- Use foreign keys.
- Use transactions for financial operations.
- Prevent duplicate transaction processing.
- Preserve payment allocation history.
- Make important financial operations atomic.
- Avoid silently overwriting historical records.

The database should be considered the authoritative persistence layer.

---

16. Security Principles

Security requirements include:

- HTTPS in production.
- Secure authentication.
- Password hashing.
- Secure session/token handling.
- Organization-level authorization.
- Server-side validation.
- Protection against unauthorized cross-organization access.
- Secure storage of integration credentials.
- Webhook signature verification.
- Audit logging of sensitive administrative actions.

Sensitive credentials must never be committed to source control.

Environment variables or a suitable secrets-management mechanism should be used.

---

17. Scalability Strategy

The initial workload is expected to be relatively light.

The application primarily processes:

- Financial transaction records.
- Monthly billing records.
- Tenant information.
- Reports.

It does not require significant computational resources under normal usage.

The architecture should therefore prioritize simplicity and correctness rather than premature distributed infrastructure.

Initial scaling strategy

Start with:

Reverse Proxy
      │
Application Server
      │
PostgreSQL

Scale horizontally only when actual usage requires it.

Potential future additions include:

- Multiple application instances.
- Managed PostgreSQL.
- Background job workers.
- Queue infrastructure.
- Object storage.
- Dedicated webhook processing.

---

18. Serverless Integrations

Paystack and Monnify webhook endpoints may eventually be deployed as serverless functions.

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

19. Import Architecture

Statement imports are the initial transaction ingestion strategy.

MVP formats:

- CSV
- XLSX

Future formats:

- PDF
- Google Sheets

The application should use an import-profile approach for varying bank statement formats.

An import profile can define:

- Relevant columns
- Header position
- Date format
- Amount format
- Sender field
- Reference field
- Credit/debit interpretation

The detailed design will be defined in "transaction-ingestion.md".

---

20. Frontend Architecture

The frontend should be organized around user-facing domains rather than arbitrary UI components.

Expected areas include:

- Dashboard
- Properties
- Rooms
- Tenancies
- Tenants
- Transactions
- Bills
- Reports
- Import Wizard
- Settings
- Audit Log

The frontend communicates with the backend through documented APIs.

Financial calculations displayed in the frontend should originate from authoritative backend data.

---

21. API Architecture

The backend should expose a REST API.

The API layer is responsible for:

- Request validation.
- Authentication.
- Authorization.
- Serialization.
- Error handling.
- Invoking application services.

The API should not contain large amounts of business logic.

Detailed endpoint definitions will be documented in "api.md".

---

22. Testing Architecture

Testing should occur at multiple levels.

Unit Tests

Focus on isolated business logic.

Especially:

- Payment allocation
- Debt calculation
- Advance calculation
- Matching logic
- Tenancy state transitions

Integration Tests

Test interactions between:

- Services
- Database
- API
- Transaction ingestion

End-to-End Tests

Test important user workflows from the frontend through the backend.

Financial allocation scenarios should have extensive automated test coverage.

---

23. Documentation Architecture

The project should maintain separate documents for major areas of concern.

Recommended structure:

docs/
│
├── 00-project-overview.md
├── 01-ai-development-guide.md
├── 02-requirements.md
├── 03-architecture.md
├── 04-database.md
├── 05-billing-engine.md
├── 06-transaction-ingestion.md
├── 07-api.md
├── 08-frontend.md
├── 09-security.md
├── 10-deployment.md
├── 11-testing.md
├── 12-roadmap.md
│
└── adr/
    ├── ADR-001-organization-root.md
    ├── ADR-002-multi-tenant-architecture.md
    ├── ADR-003-transaction-source-abstraction.md
    ├── ADR-004-statement-import-mvp.md
    └── ...

"architecture.md" remains the high-level architectural source of truth.

Detailed implementation decisions belong in the appropriate specialized documents.

---

24. Architectural Decision Records

The following decisions have been made.

ADR-001 — Organization as Root Entity

Status: Accepted

Organizations provide the top-level boundary for customer data.

Organization
    → Property
        → Room
            → Tenancy
                → Tenant

---

ADR-002 — Multi-Tenant Architecture

Status: Accepted

The application will be designed to support multi-tenant SaaS deployments.

The same architecture must also support dedicated and standalone deployments.

---

ADR-003 — Deployment-Model Independence

Status: Accepted

Business logic must not depend on whether the application is deployed as SaaS, dedicated, or standalone.

---

ADR-004 — Transaction Source Abstraction

Status: Accepted

All transaction sources must normalize into a common transaction representation before entering the core business logic.

---

ADR-005 — Statement Imports as MVP

Status: Accepted

CSV and XLSX statement imports are the initial transaction ingestion mechanism.

---

ADR-006 — Future Event-Driven Integrations

Status: Accepted

Paystack and Monnify webhooks are planned future transaction sources.

Serverless functions may be used for webhook ingestion where appropriate.

---

ADR-007 — Billing Engine Independence

Status: Accepted

The billing engine must remain independent of transaction source, frontend, and API implementation details.

---

25. Future Architectural Considerations

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

26. Open Architectural Questions

The following areas require detailed design before their respective modules are implemented:

1. Exact database schema and constraints.
2. Billing state machine.
3. Payment allocation algorithm and edge cases.
4. Transaction matching algorithm.
5. Statement import profile format.
6. Duplicate transaction detection.
7. Transaction correction/reversal mechanism.
8. Authentication implementation.
9. Authorization and roles.
10. API endpoint structure.
11. Deployment infrastructure.
12. Backup and recovery strategy.
13. Exact SaaS tenant-isolation mechanism.

These should be resolved in the relevant detailed design documents rather than prematurely embedded into this high-level architecture.

---

27. Implementation Philosophy

The application should be developed incrementally.

Architecture and business rules should be established before implementation of the corresponding module.

Recommended implementation sequence:

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

Each stage should be tested and reviewed before moving to the next.

The AI development process should follow the project's AI Development Guide and should not make architectural changes silently.

Any significant architectural change should be documented as an Architectural Decision Record (ADR).