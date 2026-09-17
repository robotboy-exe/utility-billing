# ADR-003 — Deployment-Model Independence

Status: Accepted.

Context:

The application may be deployed as centralized multi-tenant SaaS, a dedicated
deployment for a single customer, or a standalone/self-hosted installation. Core
business rules must behave identically across these models.

Decision:

Business logic must not depend on whether the application is deployed as SaaS,
dedicated, or standalone.

Consequences:

No core business rule may assume one organization, one property, one deployment,
SaaS-only operation, or self-hosted-only operation.
Deployment configuration determines how the application is hosted, while domain
logic remains unchanged.