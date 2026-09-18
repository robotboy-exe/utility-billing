Read docs/03-mvp-architecture.md, docs/04-database.md, docs/05-billing-engine.md, docs/06-transaction-ingestion.md, docs/adr/*, and the root README.md before writing anything.

Derive Core Principles primarily from the ADRs in docs/adr — each accepted architectural decision should become a principle if it constrains how code gets written (not just a design note).

Prioritize:
- Data integrity and correctness rules for the billing engine (docs/05-billing-engine.md) — this is the highest-risk module; money-handling code needs the strictest testing/validation constraints
- Ingestion reliability from docs/06-transaction-ingestion.md (idempotency, failure handling, data validation at intake)
- Database constraints from docs/04-database.md (schema stability, migration discipline)
- Any tech stack or dependency constraints already decided in docs/03-mvp-architecture.md

Do not invent principles that aren't grounded in something stated in these docs. If a section of the constitution template (e.g. testing standards, versioning policy) has no corresponding decision in the docs, leave it as a flagged open question in your response rather than filling it with generic best-practice boilerplate.

Keep the existing template structure (Core Principles, additional constraints section, governance section, version/ratification footer).
