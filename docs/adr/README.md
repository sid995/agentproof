# Architecture Decision Records

Architecture decisions are recorded using numbered Markdown documents.

ADRs are added when a phase introduces or completes an architectural decision.
They are not phase changelogs; implementation details that do not change an
architectural decision belong in the product plan or architecture document.

At phase close, review this directory explicitly:

- Add an ADR when the phase introduced a new architectural decision.
- Update an existing ADR when implementation changed or completed the accepted
  decision.
- Leave this directory unchanged only when the phase did not affect an
  architectural decision, and record the implementation details in the product
  plan or architecture docs instead.

Accepted ADRs:

- [ADR-002: Django bootstrap](ADR-002-django-bootstrap.md)
- [ADR-003: Multi-tenant organization model](ADR-003-multi-tenant-organizations.md)
- [ADR-004: Projects and deployment environments](ADR-004-projects-and-environments.md)
- [ADR-005: Environment-scoped API keys](ADR-005-environment-scoped-api-keys.md)
- [ADR-006: Canonical telemetry domain and OpenTelemetry normalization](ADR-006-canonical-telemetry-domain.md)
