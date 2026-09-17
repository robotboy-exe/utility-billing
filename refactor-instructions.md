# MASTER REFACTOR PROMPT: Lean Architecture Doc (v0.7.0 -> v0.8.0)

**Objective:** Refactor `docs/03-mvp-architecture.md` to remove redundancies, extract ADRs, and collapse sprawling sections into high-level summaries with pointers to specialized docs (`04`, `05`, `06`). 

**Rules for the Agent:**
1. Do NOT modify `04-database.md`, `05-billing-engine.md`, or `06-transaction-ingestion.md`.
2. Execute the phases sequentially.
3. When replacing sections, ensure the final document has sequential top-level numbering (1 through 19).
4. If `utility-billing-arch.md` or any `03-mvp-architecture-amendment-*.md` files exist in the root or `docs/` folder, delete them.

---

## PHASE 1: Extract ADRs to `docs/adr/`

Create the directory `docs/adr/` if it doesn't exist. 
Read Section 32 of the current `docs/03-mvp-architecture.md`. Extract ADR-001 through ADR-027 into individual markdown files using the naming convention `ADR-XXX-slug.md` (e.g., `ADR-001-organization-root.md`, `ADR-014-pdf-primary-ingestion.md`). 
Copy the exact Context/Decision/Consequences text for each ADR into its respective file.

---

## PHASE 2: Surgical Replacements in `03-mvp-architecture.md`

Perform the following surgical replacements in `docs/03-mvp-architecture.md`. 

### 1. Header Metadata
Change `Version: 0.7.0` to `Version: 0.8.0`.
Append to Document Lineage:
> Version 0.8.0 refactors the document for leanness: extracts ADRs to `docs/adr/`, collapses domain model and visibility sprawl, replaces detailed billing/ingestion rules with pointers to `05` and `06`, and transforms the locked rules summary into a compact checklist.

### 2. Replace Section 7 (Domain Model)
*Delete subsections 7.1 through 7.16 entirely.* Replace them with this exact text:

> The MVP retains the domain hierarchy described in this document.
> ```text
> Organization ─── Property ─── Room ─── Tenancy ─── Tenant
>                                       │
>                                       └── Sender Alias
> ```
> **Entity Summary**
> | Entity | Purpose & Key Relationships |
> |---|---|
> | Organization | Root isolation boundary. Owns properties, users, and financial records. |
> | Property | Physical building. Contains rooms. |
> | Room | Physical space. Persists across tenancies. One active tenancy at a time. |
> | Tenancy | Occupancy period. Privacy boundary for the tenant portal. Owns financial history. |
> | Tenant | Individual occupant. Multiple tenants per tenancy. No individual logins in MVP. |
> | Sender Alias | Accepted bank sender name for a tenancy. Primary matching key for `FUNDING` rows. |
> | Transaction | Normalized source transaction. Categorized as `tenant_payment` or `utility_bill_payment`. |
> | Monthly Bill | Billing state for a tenancy/month. One per tenancy/month. |
> | Payment Allocation | Links a tenant payment to a monthly bill. |
> | Bill Adjustment | Recorded change to a bill's final amount (rate-change or write-off only). |
> | Utility Provider | Global registry of utility companies (e.g., BEDC). |
> | Utility Bill Payment | Outgoing payment to a provider. Does not settle tenant bills. |
> | Import Profile | Global parser configuration (e.g., PAYVICE_AVANTUS). |
> | Import Batch | Staged/confirmed import operation metadata. |
> | Audit Log | Append-only record of admin/system actions. |
> 
> *Detailed schema, constraints, indexes, and exact field definitions are specified in `04-database.md`.*

### 3. Merge Sections 8, 9, and 10 into a new Section 8 (Authentication & Authorization)
*Delete the old sections 8, 9, and 10 (including the WhatsApp UI template in 10.4).* Replace them with this exact text:

> **8. Authentication & Authorization**
> The MVP uses a simplified auth model. Detailed session and credential schemas are in `04-database.md`.
> 
> **8.1 Roles**
> - **Admin:** Full access. Email/password login (hashed). Server-side authorization.
> - **Tenant Portal Session:** Read-only access to permitted tenant-facing information.
> 
> **8.2 Tenant Portal Access**
> - **No full user management:** Tenants do not have passwords, profiles, or individual logins.
> - **Shared access code:** Each tenancy gets a short, human-readable, hashed access code.
> - **Concurrency:** Multiple roommates can use the same code simultaneously (sessions are per-device).
> - **Delivery:** Admin generates and shares the code out-of-band (e.g., WhatsApp, SMS).
> - **Revocation:** Resetting the code invalidates all existing tenant sessions.
> - **Closure:** When a tenancy closes, its portal credential becomes permanently inactive. No historical access restoration.

### 4. Merge Sections 11 through 17 into a new Section 9 (Tenant Portal Visibility)
*Delete the old sections 11, 12, 13, 14, 15, 16, and 17.* Replace them with this exact text:

> **9. Tenant Portal Visibility**
> Visibility is a policy concern enforced server-side. The frontend must not be trusted to hide data. Configuration is stored in the `portal_setting` table (see `04-database.md`).
> 
> **9.1 Privacy Boundary**
> The privacy boundary is the **tenancy**. Members of the same tenancy see full details. Members of other tenancies see limited property-level billing info. Tenants cannot see other properties. Admin sees everything.
> 
> **9.2 Visibility Matrix**
> | Information | Same tenancy | Other rooms (same property) | Other properties | Admin |
> |---|---|---|---|---|
> | Property/Room list & names | Visible | Visible | Hidden | Visible |
> | Room billing amount/status | Visible | Visible | Hidden | Visible |
> | Room bill adjustment notice | Visible | Visible | Hidden | Visible |
> | Property utility spend | Visible | Visible | Hidden | Visible |
> | Tenants & contact details | Visible | Hidden | Hidden | Visible |
> | Tenancy bills/payments/transactions | Full | Hidden | Hidden | Visible |
> | Audit log | Hidden | Hidden | Hidden | Visible |
> 
> **9.3 Default View & Flexibility**
> - The default tenant view is the **Property view** (configurable to "Room view" later).
> - Utility bill payment records and spend reports are property-level records visible to all tenants in that property.

### 5. Merge Sections 18 through 22 into a new Section 10 (Billing, Ingestion, and Matching)
*Delete the old sections 18, 19, 20, 21, and 22.* Replace them with this exact text:

> **10. Billing, Ingestion, and Matching**
> The system maintains two strictly separated ledgers: the **Tenant Payment Ledger** and the **Utility Bill Payment Ledger**. They never settle each other.
> 
> **10.1 Transaction Ingestion (Summary)**
> - **Primary Source:** Payvice Avantus PDF (text-based only, no OCR).
> - **Flow:** Two-phase (Upload/Parse -> Staged Batch -> Admin Preview -> Confirm).
> - **Category Mapping:** Configuration-driven. `FUNDING` = tenant payment; `BEDC` = utility payment; `COMMISSION` = fully discarded (never stored/logged).
> - *Detailed parser grammar, validation, and duplicate detection rules belong in `06-transaction-ingestion.md`.*
> 
> **10.2 Matching**
> - Only `tenant_payment` rows enter matching (primarily via normalized sender aliases).
> - `utility_bill_payment` rows bypass matching and go straight to provider spend reporting.
> 
> **10.3 Billing & Allocation (Summary)**
> - **Generation:** Automatic and rolling (lazy generation triggered by dashboard/report usage).
> - **Standard Amount:** Uniform across all rooms. No arbitrary per-room overrides.
> - **Adjustments:** Only occur via global rate-changes (adjusting unsettled current-month bills by the delta) or debt write-offs. Fully audited and visible to tenants.
> - **Partial Months:** Move-in partial months are unbilled by default (admin can opt-in). Move-out partial months are billed in full by default (admin can write-off post-closure).
> - **Allocation:** Chronological, oldest-outstanding-first. Overpayments become advance credit.
> - **Advance Ledger:** Advance balance is derived. Movements are recorded in an append-only ledger and reconciled for fraud detection.
> - *Detailed allocation algorithms, edge cases, and correction workflows belong in `05-billing-engine.md`.*

### 6. Renumber Section 23 to Section 11 (Reporting)
*Keep the content of old Section 23 exactly as is, but change the heading to `11. Reporting`.*

### 7. Merge Sections 24, 25, 26, and 27 into a new Section 12 (Data, Security, and Audit Principles)
*Delete the old sections 24, 25, 26, and 27.* Replace them with this exact text:

> **12. Data, Security, and Audit Principles**
> - **Transport & Secrets:** HTTPS in production. Secrets in environment variables, never in source control.
> - **Server-Side Authorization:** All access and visibility rules enforced server-side.
> - **Scoping:** Queries strictly scoped by `organization_id`, `property_id`, and `tenancy_id`.
> - **Money Handling:** Single currency. All amounts stored as `BIGINT` minor units (e.g., ₦1,000 = 100000). No floating-point math.
> - **Immutability:** Financial records (transactions, allocations, advance movements, audit logs) are append-only. Corrections use reversal/correction records, never silent rewrites.
> - **Auditability:** Lightweight, append-only audit log for admin/system actions. Commission data is never logged. Tenants do not see the audit log.
> - *Detailed security implementations belong in `09-security.md`.*

### 8. Merge Sections 28 and 29 into a new Section 13 (API & Frontend Architecture)
*Delete old 28 and 29.* Replace with:
> **13. API & Frontend Architecture**
> - **API:** RESTful. Handles validation, auth, visibility enforcement, and serialization. No heavy business logic. Endpoints grouped by Admin and Tenant Portal.
> - **Frontend:** React + TypeScript + Vite. Organized by user-facing domains (Dashboard, Properties, Tenancies, Imports, Tenant Portal). Must not contain authoritative financial logic.

### 9. Trim and Renumber Section 30 to Section 14 (Deployment Architecture)
*Keep 30.1, 30.2, 30.3, 30.4, 30.7, and 30.8.* 
*Delete 30.5 (Deployment Independence) and 30.6 (Multi-Tenant Architecture) entirely, as they are already covered in Section 2 (Principles) and Section 7 (Domain Model).*
*Renumber the remaining subsections sequentially under the new heading `14. Deployment Architecture`.*

### 10. Collapse Section 31 into Section 15 (Testing Focus)
*Delete the long bulleted list in old Section 31.* Replace with:
> **15. Testing Focus**
> Financial allocation scenarios, advance ledger reconciliation, and PDF parsing edge cases require extensive automated test coverage. 
> *Specific test scenarios and edge cases are defined in the Testing sections of `05-billing-engine.md` and `06-transaction-ingestion.md`.*

### 11. Replace Section 32 with Section 16 (ADR Index)
*Delete the entire inline text of ADR-001 through ADR-027.* Replace with this exact text:

> **16. Architectural Decision Records (ADR Index)**
> The full Context, Decision, and Consequences for each ADR are stored in individual files in the `docs/adr/` directory.
> 
> | ADR | Title | Status | Summary |
> |---|---|---|---|
> | 001 | Organization as Root Entity | Accepted | Top-level boundary for customer data. |
> | 002 | Multi-Tenant Architecture | Accepted | Supports SaaS, dedicated, and standalone. |
> | 003 | Deployment-Model Independence | Accepted | Logic doesn't depend on hosting model. |
> | 004 | Transaction Source Abstraction | Accepted | Normalizes all sources before billing. |
> | 005 | Statement Imports as MVP | Superseded | Superseded by ADR-014 (PDF primary). |
> | 006 | Future Event-Driven Integrations | Accepted | Webhooks planned for future. |
> | 007 | Billing Engine Independence | Accepted | Billing logic isolated from sources/UI. |
> | 008 | Tenant Portal Visibility Boundary | Accepted | Privacy boundary is the tenancy. |
> | 009 | Shared Tenancy Access Code | Accepted | Roommates share one code; no individual logins. |
> | 010 | Rate-Change Adjustments & Write-Offs | Accepted | No per-room overrides; systematic adjustments only. |
> | 011 | Configurable Default View | Accepted | Property view default, configurable to Room. |
> | 012 | Free-Hosting Synchronous MVP | Accepted | No background jobs/cron; lazy generation. |
> | 013 | No Full Tenant User Management | Accepted | Shared codes instead of full user accounts. |
> | 014 | PDF as Primary Ingestion | Accepted | Payvice Avantus PDF is mandatory/primary. |
> | 015 | Category Mapping as Config | Accepted | Data-driven routing of statement rows. |
> | 016 | Utility Provider Registry | Accepted | BEDC first; registry-driven, not hardcoded. |
> | 017 | Separate Ledgers | Accepted | Tenant payments and utility spend never mix. |
> | 018 | Payment Date != Billing Month | Accepted | Allocation determines billing month. |
> | 019 | Commission Rows Excluded | Accepted | Commissions are fully discarded/ignored. |
> | 020 | Oldest-Outstanding-First Allocation | Accepted | Chronological filling of bills. |
> | 021 | Advance Movement Ledger | Accepted | Append-only log for advance credit auditability. |
> | 022 | Lazy Bill Generation | Accepted | Generated on-demand, not via scheduler. |
> | 023 | No Per-Room Overrides | Accepted | Only global standard amount is adjustable. |
> | 024 | Partial-Month Asymmetry | Accepted | Move-in skipped by default; move-out billed. |
> | 025 | Debt Write-Offs | Accepted | Audited zeroing of debt; no hard deletes. |
> | 026 | Closed Tenancies Lose Access | Accepted | Portal credentials permanently deactivated. |
> | 027 | Property Dashboard Metrics | Accepted | Outstanding debt, room ratios, BEDC outflow. |

### 12. Renumber Sections 33 and 34
*Change old Section 33 to `17. Remaining Detailed Design Documents`.*
*Change old Section 34 to `18. Open Questions`.*

### 13. Delete Section 35 (Implementation Sequence)
*Delete old Section 35 entirely.* It is generic waterfall filler and adds no MVP-specific value.

### 14. Compact Section 36 into Section 19 (Summary of Locked MVP Rules)
*Delete the verbose essay-style lists in old Section 36.* Replace with this compact checklist:

> **19. Summary of Locked MVP Rules**
> 
> **Architecture & Ledgers**
> - [ ] Two strictly separated ledgers (Tenant Payment vs. Utility Bill Payment).
> - [ ] Utility providers and Import profiles are global/system-wide registries.
> 
> **Ingestion**
> - [ ] Payvice Avantus PDF is the primary source (text-based, staged, admin-confirmed).
> - [ ] `FUNDING` = tenant payment; `BEDC` = utility payment; `COMMISSION` = discarded.
> 
> **Billing & Allocation**
> - [ ] Lazy/rolling bill generation (no background schedulers).
> - [ ] Uniform standard amount (no arbitrary per-room overrides).
> - [ ] Adjustments limited to rate-changes and write-offs (fully audited/visible).
> - [ ] Chronological, oldest-outstanding-first allocation.
> - [ ] Advance credit is derived; movements logged in an append-only ledger.
> - [ ] Move-in partial months unbilled by default; move-out billed in full by default.
> 
> **Visibility & Access**
> - [ ] Privacy boundary is the tenancy.
> - [ ] Shared access codes (no individual tenant logins).
> - [ ] Closed tenancies permanently lose portal access.
> - [ ] Visibility rules enforced server-side and configurable.
> 
> **Hosting**
> - [ ] Free-tier compatible (no cron, no background workers, no persistent local files).

---

## PHASE 3: Final Verification

1. Verify that `docs/03-mvp-architecture.md` now has exactly 19 top-level sections.
2. Verify that the word count of `03-mvp-architecture.md` has been reduced by roughly 40-50%.
3. Verify that `docs/adr/` contains 27 individual markdown files.
4. Delete `utility-billing-arch.md` and any `amendment` files if they are still present in the workspace.