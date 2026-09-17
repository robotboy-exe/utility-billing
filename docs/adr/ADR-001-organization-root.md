### ADR-001 — Organization as Root Entity

Status: Accepted.

Organizations provide the top-level boundary for customer data.

```text
Organization
    → Property
        → Room
            → Tenancy
                → Tenant
```
