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
