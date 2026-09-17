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
