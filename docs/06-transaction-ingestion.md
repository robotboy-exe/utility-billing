# Transaction Ingestion

Document: `docs/06-transaction-ingestion.md`  
Version: `0.2.1`  
Status: Draft — accepted MVP ingestion design  
Last Updated: 2026-09-17  
Related documents: `03-mvp-architecture.md`, `04-database.md`, `05-billing-engine.md`

Changes in this version: Added `04-database.md` to the related documents and refreshed the metadata. No ingestion rules changed.

---

## 1. Purpose

This document defines how transactions enter the system.

It covers:

- Statement import.
- PDF parsing.
- The Payvice Avantus format.
- Transaction normalization.
- Category mapping.
- Commission exclusion.
- Utility provider payment recording.
- Tenant payment ingestion.
- Duplicate detection.
- Validation.
- Staged imports.
- Matching handoff.
- Free-hosting constraints.

This document does not define billing allocation rules. Billing allocation belongs in `05-billing-engine.md`.

---

## 2. MVP Transaction Sources

### 2.1 Primary source

The primary MVP transaction source is:

```text
Payvice Avantus PDF statement export
```

This source is mandatory.

---

### 2.2 Secondary sources

The following remain desirable but secondary:

- CSV statement import.
- XLSX statement import.
- Manual transaction entry.

CSV and XLSX profiles may be added later using the same import-profile abstraction.

---

### 2.3 Deferred sources

The following are deferred:

- Google Sheets.
- Paystack webhooks.
- Monnify webhooks.
- Direct bank APIs.
- OCR/scanned-image PDF parsing.

---

## 3. Free-Hosting Constraints

The ingestion design must respect free-hosting constraints.

### 3.1 Synchronous processing

Statement import must be manually triggered and processed synchronously.

No background workers are required.

---

### 3.2 Staged imports

Imports are two-phase:

```text
Upload / Parse
   ↓
Staged Import Batch
   ↓
Admin Preview
   ↓
Confirm or Reject
   ↓
Committed Records
```

Staging allows:

- Validation.
- Preview.
- Duplicate detection.
- Recovery from cold starts or restarts.
- Admin review before financial records are committed.

---

### 3.3 File retention

The original PDF binary is not retained by default.

The system stores:

- Extracted persistable transaction rows.
- Import batch metadata.
- Ignored-category summary counts and totals.
- Validation results.

No commission data is stored.

---

### 3.4 File limits

Initial operational limits:

| Limit | Suggested value |
|---|---:|
| Maximum file size | 10 MB |
| Maximum pages | 25 |

These limits are configurable and may be adjusted after deployment experience.

---

## 4. Import Flow

The MVP import flow is:

```text
Admin uploads Payvice Avantus PDF
   ↓
Parser detects format
   ↓
Parser extracts text lines
   ↓
Structural lines are classified
   ↓
Transaction rows are parsed
   ↓
Category mapping is applied
   ↓
Commission rows are discarded
   ↓
Ignored rows are summarized
   ↓
Persistable rows are staged
   ↓
Validation and duplicate checks run
   ↓
Admin reviews staged import
   ↓
Admin confirms or rejects
   ↓
Confirmed tenant payments enter matching
   ↓
Confirmed utility payments create utility bill payment records
   ↓
Matched tenant payments enter billing engine
```

---

## 5. Import Profiles

An import profile defines how a particular statement format is parsed and categorized.

Each profile includes:

- Profile code.
- Display name.
- Source type.
- Detection signature.
- Structural rules.
- Row grammar.
- Date/time rules.
- Amount rules.
- Direction rules.
- Channel taxonomy.
- Category mapping.
- Validation rules.
- Duplicate-detection rules.

Import profiles are configuration-driven where practical.

Import profiles are registered globally (system-wide). They are seeded once for the whole application, not per organization, so any future landlord automatically gets the Payvice Avantus parser pre-loaded. A per-organization override can be added later without a schema change.

Adding a new statement format should not require changes to the billing engine.

---

## 6. Payvice Avantus Profile

### 6.1 Profile registration

| Field | Value |
|---|---|
| Profile code | `PAYVICE_AVANTUS` |
| Display name | Payvice Avantus |
| Source type | PDF |
| Parsing method | Text-based PDF extraction |
| OCR required | No |
| Status | Primary MVP import profile |
| Scope | Global (system-wide) |

---

### 6.2 Detection signature

The parser identifies the Payvice Avantus format using:

1. A statement title line matching:

```text
Outlet E-Statement for DD Mon YYYY- DD Mon YYYY
```

2. A column header line:

```text
Date/Time Description Credit Debit
```

The phrase `Outlet E-Statement` is a detection signature only.

The profile name remains:

```text
Payvice Avantus
```

---

## 7. Statement Structure

### 7.1 First-page header block

The first page contains:

```text
Account holder name
Account number
Statement title
Column header
Transaction rows
```

Example:

```text
Samuel Odeyovwi
13939443
Outlet E-Statement for 01 Jun 2026- 31 Jul 2026
Date/Time Description Credit Debit
```

The parser captures:

- Account holder name.
- Account number.
- Statement start date.
- Statement end date.

---

### 7.2 Structural classification

Lines are classified in this order:

1. Statement title line.
2. Column header line.
3. Total/footer line.
4. Transaction row.
5. Amount-only continuation row.
6. Unclassified line.

Structural lines are never treated as transactions.

---

### 7.3 Repeated page headers

If page headers repeat, the structural classifier ignores them.

The parser must not treat repeated headers as transactions.

---

### 7.4 Statement total line

The statement ends with:

```text
Total <total credits> <total debits>
```

Example:

```text
Total 36,792.00 64,056.00
```

This line is used for control-total validation.

---

## 8. Transaction Row Grammar

### 8.1 Normal transaction row

A transaction row normally appears as:

```text
DD-MM-YY H:MMAM/PM Description Amount
```

Examples:

```text
22-07-26 11:23AM BEDC/ Mr A. Y(27300169326) -1,000.00
18-06-26 1:21PM FUNDING/ Transfer From MICHEL ODION OMOBHUDE 2,000.00 -
19-06-26 9:57PM COMMISSION/ agent Commission 88.00 -
```

---

### 8.2 Date format

Date format:

```text
DD-MM-YY
```

Normalization:

```text
22-07-26 → 2026-07-22
```

Year rule:

```text
YY → 20YY
```

Validation:

- The transaction date must fall within the statement period.
- Dates outside the statement period are flagged.

---

### 8.3 Time format

Time format:

```text
H:MMAM/PM
```

The source does not consistently zero-pad hours or minutes.

Examples:

```text
11:8AM
7:1AM
12:40AM
5:46PM
```

Normalization rule:

- Zero-pad hour and minute before converting to a standard time representation.

---

### 8.4 Description format

Descriptions may contain:

- Channel prefixes.
- Counterparty names.
- Reference numbers in parentheses.
- Mixed case.
- Extra spaces.
- Hyphens.
- Wrapped text.

If a description contains a slash:

```text
CHANNEL/ remainder
```

Then:

- Channel = text before first slash.
- Remainder = text after first slash.

If no slash exists:

- Channel = `NONE`.
- Full text is treated as description.

Example:

```text
VAT Vat VAT -1.50
```

---

### 8.5 Reference extraction

Where present, reference numbers appear in parentheses.

Examples:

```text
BEDC/ Mr A. Y(27300169326)
TRANSFER/ SAMUEL OGHENERO ODEYOVWI(8109307552)
TRANSFER/ Samuel Oghenero Odeyovwi (2003232297)
```

Reference extraction rule:

- Extract the digits inside the final parentheses.
- Allow optional whitespace before the opening parenthesis.
- Reference is optional because some rows have none.

---

### 8.6 Wrapped transaction rows

A transaction may wrap across two lines when the description is long.

Example:

```text
16-06-26 8:16PM TRANSFER/ CHUKWUEMEKA ABRAHAMOGHENERUKEVWE EDOZIE (7083818518)
-1,000.00
```

Rule:

- If a line contains only an amount, it belongs to the immediately preceding incomplete transaction row.
- This rule applies even across page boundaries.

---

## 9. Amount and Direction Rules

### 9.1 Credit rows

Credit rows show an amount followed by a trailing dash.

Example:

```text
FUNDING/ Transfer From FATIMAH ABDALLAH 4,000.00 -
```

Direction:

```text
Credit
```

Amount:

```text
4,000.00
```

---

### 9.2 Debit rows

Debit rows show a leading minus.

Example:

```text
BEDC/ Mr A. Y(27300169326) -1,000.00
```

Direction:

```text
Debit
```

Amount:

```text
1,000.00
```

---

### 9.3 Double-minus quirk

Some charge rows appear as:

```text
CHARGE/ AUTO SERVICE CHARGE --20.00
```

Rule:

- Treat as debit.
- Strip leading minus markers.
- Use absolute magnitude.

Result:

```text
Direction: Debit
Amount: 20.00
```

---

### 9.4 Money representation

All amounts are stored as integer minor units.

Example:

```text
₦1,000.00 → 100000 minor units
```

Floating-point numbers must not be used for financial amounts.

---

## 10. Channel Taxonomy

The Payvice Avantus format contains the following observed channels.

| Channel | Observed direction | Meaning |
|---|---|---|
| `FUNDING` | Credit | Money paid into the account |
| `BEDC` | Debit | Payment to utility provider |
| `TRANSFER` | Debit | Outgoing transfer |
| `COMMISSION` | Credit | Agent commission |
| `CHARGE` | Debit | Bank/service charge |
| `VAT` | Debit | VAT on charges |
| Unknown | Any | Unrecognized; flagged for review |

---

## 11. Category Mapping

Category mapping determines how parsed rows are handled.

This mapping must not be hardcoded in the parser.

It must be configurable so future behavior can change without rebuilding the system.

### 11.1 MVP category mapping

| Channel / direction | Category | System behavior |
|---|---|---|
| `FUNDING` credit | `tenant_payment` | Persist, match, allocate |
| `BEDC` debit | `utility_bill_payment` | Persist as utility bill payment |
| `TRANSFER` debit | `ignored` | Not recorded as ledger entry; summarized |
| `CHARGE` debit | `ignored` | Not recorded as ledger entry; summarized |
| `VAT` debit | `ignored` | Not recorded as ledger entry; summarized |
| `COMMISSION` any | `excluded` | Fully discarded |
| Unknown | `unrecognized` | Flagged for review |

---

### 11.2 Persisted categories

Only these categories produce persisted transaction records:

```text
tenant_payment
utility_bill_payment
```

All other categories do not create ledger transaction records in MVP.

---

### 11.3 Ignored categories

Ignored categories are not recorded as ledger entries.

However, the import batch may store summary totals such as:

- Number of ignored rows.
- Total ignored amount.
- Category breakdown.

This allows the admin to see that non-ledger rows existed without storing each ignored transaction.

---

### 11.4 Excluded category

Commission rows are excluded.

Excluded means:

- Not stored.
- Not displayed.
- Not counted.
- Not logged.
- Not included in reports.
- Not included in audit records.

The parser recognizes commission rows only to discard them.

---

## 12. Commission Exclusion Policy

Commission rows are fully ignored and discarded.

### 12.1 Hard rules

For any row whose channel is `COMMISSION`:

- Do not store the row.
- Do not store the amount.
- Do not store the date.
- Do not store the description.
- Do not display the row.
- Do not count the row in import summaries.
- Do not write it to audit logs.
- Do not include it in reports.

---

### 12.2 Validation allowance

The statement footer totals include commission amounts.

To preserve statement validation, the parser may transiently recognize commission rows during parsing solely to validate statement totals.

No commission data may be retained after parsing.

If this transient validation is ever considered unacceptable, the alternative is to disable credit-total validation for this profile.

---

## 13. Tenant Payment Ingestion

Tenant payments originate from `FUNDING` credit rows.

Example:

```text
18-06-26 5:59AM FUNDING/ Transfer From FAITH UJUNWA OBI 1,000.00 -
```

Parsed as:

| Field | Value |
|---|---|
| Date | 2026-06-18 |
| Time | 05:59 |
| Channel | FUNDING |
| Direction | Credit |
| Sender name | FAITH UJUNWA OBI |
| Amount | ₦1,000.00 |
| Category | tenant_payment |

---

### 13.1 Sender extraction

For `FUNDING` rows, the description follows:

```text
Transfer From <SENDER NAME>
```

The parser extracts the sender name after:

```text
Transfer From
```

Rules:

- Case-insensitive prefix matching.
- Trim surrounding whitespace.
- Normalize sender name for alias matching.

---

### 13.2 Account-holder self-funding

If the account holder funds the account and has a recognized sender alias for an active tenancy, the payment is treated exactly like any other tenant payment.

No special-casing is required.

Matching is alias-driven.

---

## 14. Utility Bill Payment Ingestion

Utility bill payments originate from provider debit rows.

The first registered provider is BEDC.

Example:

```text
22-07-26 11:23AM BEDC/ Mr A. Y(27300169326) -1,000.00
```

Parsed as:

| Field | Value |
|---|---|
| Date | 2026-07-22 |
| Time | 11:23 |
| Channel | BEDC |
| Direction | Debit |
| Provider | BEDC |
| Customer/meter reference | 27300169326 |
| Amount | ₦1,000.00 |
| Category | utility_bill_payment |

---

## 15. Utility Provider Registry

Utility bill payments must not hardcode BEDC.

The system should maintain a provider registry.

Utility providers are registered globally (system-wide). They are seeded once for the whole application, not per organization, so any future landlord automatically gets registered providers pre-loaded. A per-organization override can be added later without a schema change.

### 15.1 Provider fields

| Field | Example |
|---|---|
| Provider code | `BEDC` |
| Display name | Benin Electricity Distribution Company |
| Channel signature | `BEDC` |
| Reference label | Meter/customer number |
| Active status | Active |

---

### 15.2 Future providers

Future utility providers can be added by:

1. Registering a new provider.
2. Mapping its statement channel signature.
3. Defining its reference type.
4. Enabling it in the import profile category mapping.

No billing-engine changes should be required to add a new provider.

---

## 16. Utility Spend Reporting Handoff

Utility bill payments populate a separate month-bounded report.

Rules:

- Group by provider and calendar month.
- Use the payment date to determine the month.
- Do not infer consumption month.
- Do not connect utility payments to tenant bills.
- Do not use utility payments to reduce tenant balances.

Example:

| Month | Provider | Total Spent |
|---|---|---:|
| June 2026 | BEDC | ₦22,000.00 |
| July 2026 | BEDC | ₦23,000.00 |

This reporting belongs to the Utility Bill Payment Ledger.

---

## 17. Matching Handoff

Only `tenant_payment` rows enter tenancy matching.

### 17.1 Matching inputs

Matching uses:

- Normalized sender name.
- Sender aliases.
- Active tenancy status.
- Property context.

`FUNDING` rows do not include payer account numbers, so sender-name alias matching is the primary matching mechanism.

---

### 17.2 Matching outcomes

A tenant payment may become:

| Outcome | Meaning |
|---|---|
| Matched | Sender alias maps to one tenancy |
| Ambiguous | Sender alias maps to multiple tenancies |
| Unmatched | No sender alias match |
| Manually matched | Admin assigned tenancy manually |

Only matched tenant payments enter the billing engine.

---

### 17.3 Utility payments do not match tenancies

`utility_bill_payment` rows do not enter tenancy matching.

They are recorded directly as utility provider spend records.

---

## 18. Duplicate Detection

### 18.1 Row-level duplicate key

For persistable rows, the duplicate key should be derived from:

```text
statement account
normalized transaction date/time
channel
normalized description
direction
amount in minor units
```

The key is stored as a deterministic hash.

---

### 18.2 Statement fingerprint

The import batch should also compute a statement fingerprint from:

```text
statement account
statement period
ordered persistable row duplicate keys
```

This fingerprint detects re-importing the same statement.

---

### 18.3 Duplicate behavior

| Situation | Behavior |
|---|---|
| Same statement imported again | Reject or flag as duplicate statement |
| Same row already imported | Skip row as duplicate |
| Two identical rows inside same statement | Flag for admin review |
| Duplicate detected after commit | Handle through correction/reversal, not silent deletion |

---

## 19. Validation Rules

The parser must validate:

1. Format detection.
2. Statement period parsing.
3. Account number presence.
4. Row grammar conformance.
5. Date validity.
6. Transaction date within statement period.
7. Amount validity.
8. Direction consistency.
9. Channel recognition.
10. Control totals.
11. Duplicate rows.
12. Duplicate statements.
13. Wrapped-row completion.

---

## 20. Control Total Validation

The statement footer contains:

```text
Total <credits> <debits>
```

The parser should recompute totals from parsed rows.

Because commission rows are excluded from storage but included in the statement totals, totals validation may transiently include commission rows during parsing only.

No commission data is retained.

### 20.1 Totals match

If totals match:

```text
totals_status = valid
```

---

### 20.2 Totals mismatch

If totals do not match:

```text
totals_status = mismatch
```

The staged import is flagged for admin review.

A mismatch does not automatically mean the import must be rejected, but it must not be silently ignored.

---

### 20.3 Missing totals

If no total line is found:

```text
totals_status = missing
```

The import should be flagged.

---

## 21. Staged Import Batch

Each import creates a staged batch.

### 21.1 Batch metadata

The batch stores:

- Import profile.
- Statement account holder.
- Statement account number.
- Statement start date.
- Statement end date.
- Upload timestamp.
- Totals validation status.
- Duplicate statement status.
- Import status.

---

### 21.2 Batch counters

The batch stores counters for review and reconciliation:

- Tenant payment rows staged (`tenant_payment_row_count`).
- Tenant payment amount total (`tenant_payment_total_minor`).
- Utility payment rows staged (`utility_payment_row_count`).
- Utility payment amount total (`utility_payment_total_minor`).
- Ignored row count and amount totals (in `ignored_summary`).
- Duplicate rows skipped (`duplicate_row_count`).
- Invalid rows detected (`invalid_row_count`).
- Unrecognized rows detected (`unrecognized_row_count`).

The `*_total_minor` counters are expressed in the batch `currency`. The batch must not store commission counts or amounts.

---

### 21.3 Staged rows

Only persistable categories are staged as row records:

```text
tenant_payment
utility_bill_payment
```

Ignored rows are summarized.

Commission rows are discarded.

---

## 22. Import Statuses

Suggested import batch statuses:

| Status | Meaning |
|---|---|
| Parsing | File is being parsed |
| Staged | Rows are ready for admin review |
| Duplicate statement | Statement fingerprint already exists |
| Totals mismatch | Control totals do not match |
| Confirmed | Admin approved import |
| Rejected | Admin rejected import |
| Completed | Import committed successfully |
| Failed | Parsing or validation failed |

---

## 23. Admin Preview

Before committing, the admin should see:

- Statement account.
- Statement period.
- Tenant payment rows.
- Utility payment rows.
- Ignored summary.
- Duplicate warnings.
- Invalid row warnings.
- Totals validation status.

The admin must not see commission data.

The admin may then:

- Confirm the import.
- Reject the import.

---

## 24. Error Handling

### 24.1 Invalid row

If a row cannot be parsed:

- Mark it as invalid.
- Show row number and reason.
- Do not commit it.
- Allow admin to reject or resolve manually.

---

### 24.2 Unknown channel

If a channel is not recognized:

- Mark row as unrecognized.
- Do not persist it.
- Flag for admin review.

Future channel mappings can be added through configuration.

---

### 24.3 Scanned PDF

If the PDF has no usable text layer:

- Reject the file.
- Show a clear message that scanned/image PDFs are unsupported.

OCR is out of scope for MVP.

---

### 24.4 File too large

If the file exceeds size or page limits:

- Reject the file.
- Show the configured limits.

---

## 25. Security Rules

The ingestion module must:

- Accept only expected PDF files.
- Parse files server-side.
- Enforce upload limits.
- Avoid exposing raw statement text in logs.
- Never log commission data.
- Never store secrets in import metadata.
- Enforce organization/property authorization on import actions.
- Store extracted financial rows only after admin confirmation.

---

## 26. Testing Requirements

Ingestion tests should cover:

1. Valid Payvice Avantus statement parsing.
2. Detection signature recognition.
3. Statement period extraction.
4. Account number extraction.
5. Credit trailing-dash parsing.
6. Debit leading-minus parsing.
7. Double-minus charge parsing.
8. Wrapped row parsing.
9. No-slash VAT row parsing.
10. Mixed-case sender parsing.
11. Optional whitespace before parentheses.
12. FUNDING sender extraction.
13. BEDC provider/reference extraction.
14. Commission exclusion.
15. Ignored category summarization.
16. Duplicate row detection.
17. Duplicate statement detection.
18. Totals validation.
19. Totals mismatch handling.
20. Dates outside statement period.
21. Unknown channel handling.
22. Scanned PDF rejection.
23. File size/page limit enforcement.

---

## 27. Locked Ingestion Rules

The following rules are locked for MVP:

1. Payvice Avantus PDF is the primary transaction source.
2. The format is text-based PDF; OCR is not supported.
3. Imports are staged and confirmed by admin.
4. Original PDF binaries are not retained by default.
5. `FUNDING` credits become tenant payments.
6. `BEDC` debits become utility bill payments.
7. Utility bill payments populate month-bounded provider spend reporting.
8. `TRANSFER`, `CHARGE`, and `VAT` are ignored for now but configurable later.
9. `COMMISSION` rows are fully discarded with no stored or displayed trace.
10. Tenant payments enter tenancy matching.
11. Utility payments do not enter tenancy matching.
12. Duplicate detection must prevent repeated import of the same statement and same transaction rows.
13. Control totals must be validated.
14. Category mapping must remain configurable for future changes.
15. Utility providers must be registry-driven, not hardcoded.