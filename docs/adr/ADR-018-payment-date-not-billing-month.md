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
