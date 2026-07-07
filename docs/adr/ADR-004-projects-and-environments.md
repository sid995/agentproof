# ADR-004: Projects and deployment environments

## Status

Accepted

Implementation status: implemented and validated.

## Context

AgentProof telemetry, API keys, datasets, evaluations, and policies need a
stable hierarchy below an organization.

A project represents one AI application. An environment represents a deployed
context such as development, staging, or production.

Capture and retention policies need project defaults with optional
environment overrides.

## Decision

The resource hierarchy is:

```text
Organization
└── Project
    └── Environment
```

Projects store:

- Name
- Stable slug
- Description
- Lifecycle status
- Default capture mode
- Default retention period
- Creator

Environments store:

- Direct organization ownership
- Parent project
- Stable slug
- Environment type
- Lifecycle status
- Optional capture-mode override
- Optional retention override
- Creator

Every new project automatically receives one development environment.

## Capture modes

Supported project and environment capture modes are:

- metadata_only
- redacted
- full

An environment with no capture override inherits the project default.

## Retention

Projects define a default retention period.

Environments may define an override.

Retention must remain between 1 and 3,650 days.

## Authorization

Owners and administrators may:

- Create projects
- Update projects
- Archive projects

Owners, administrators, and developers may:

- Create environments
- Update environments
- Archive environments

Viewers have read-only access.

## Tenant isolation

Every project is queried through its organization.

Every environment is queried through:

- Organization
- Project
- Environment identifier

Environment records also contain organization_id directly for explicit tenant
scoping in background jobs, cache keys, audit records, and future high-volume
queries.

## Slugs

Project slugs are unique inside an organization.

Environment slugs are unique inside a project.

Slugs are immutable after creation.

## Deletion

Projects and environments are archived rather than deleted through the public
API.

Physical deletion will be handled later through retention and administrative
data-deletion workflows.

## Consequences

Positive:

- Product resources have a clear tenant hierarchy.
- Environment policy inheritance is explicit.
- Development environments exist immediately.
- Stable slugs support API keys and telemetry.
- Project and environment changes are auditable.
- Developers can manage environments without receiving organization-admin
  access.

Negative:

- Direct organization ownership on Environment duplicates information from
  Project.
- Cross-table organization consistency is enforced in application services.
- Archived resources remain queryable unless callers explicitly filter them.
- Policy inheritance requires loading the parent project.

## Current implementation notes

The Phase 4 implementation includes:

- Project and Environment models.
- Project and environment services/selectors.
- DRF serializers and API views.
- Minimal server-rendered project pages.
- Admin integration.
- OpenAPI schema updates.
- Tests for tenant scoping, permissions, audit events, and web pages.

Environment organization/project consistency is enforced in model and service
paths. The current validation gate is `make check`.
