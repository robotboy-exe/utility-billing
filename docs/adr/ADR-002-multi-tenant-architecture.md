# ADR-002 — Multi-Tenant Architecture

**Status:** Accepted

## Context

The product is intended to be commercially viable as a centralized multi-tenant SaaS
offering, while also supporting dedicated and self-hosted deployments for customers
who need them.

## Decision

The application will be designed to support multi-tenant SaaS deployments.
The same architecture must also support dedicated and standalone deployments.

## Consequences

Organization-level data isolation is mandatory for SaaS.
The same codebase serves all deployment models.
Deployment configuration, not business logic, determines the hosting model.
