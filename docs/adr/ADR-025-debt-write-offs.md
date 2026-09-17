### ADR-025 — Debt Write-Offs, No Hard Deletes

Status: Accepted.

Context: Closed tenancies may leave unpaid debt the admin chooses to forego.

Decision: Foregoing debt is an audited write-off that zeroes the outstanding balance. Financial records are never hard-deleted, so history stays verifiable and auditable.

Consequences: Write-offs are recorded as typed bill adjustments. Closed-tenancy debt persists for pursuit or write-off.
