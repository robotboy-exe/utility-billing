### ADR-027 — Property Dashboard Metrics

Status: Accepted.

Context: Tenants need a transparent property-level view of billing and utility spend.

Decision: The property view shows total outstanding debt, total room count, fully-paid room count, a clearly labeled fully-paid/total ratio, current-month utility spend (BEDC outflow), and historical utility spend (BEDC outflow) as the only historical data.

Consequences: Historical figures come from the Utility Bill Payment Ledger, not tenant payments. Historical months expose totals only, no room counts.
