# ADR-003: Multi-tenant organization model

## Status

Accepted

## Context

AgentProof must isolate projects, traces, datasets, evaluations, API keys,
and audit records between customer organizations.

Relying on URL identifiers or frontend state is insufficient. Tenant context
must be established and enforced on the server.

## Decision

AgentProof will use application-level shared-database tenancy.

The tenant hierarchy begins with:

- User
- Organization
- Membership
- OrganizationInvitation

Each authenticated session stores one active organization identifier.

A middleware component resolves:

- request.organization
- request.organization_membership

Tenant endpoints require:

1. An authenticated user
2. An active organization context
3. A URL organization matching the current context
4. An appropriate membership role
5. A tenant-scoped queryset

State-changing use cases remain inside service functions and re-check
authorization and business invariants.

Roles are:

- Owner
- Administrator
- Developer
- Viewer

Every organization must retain at least one active owner.

## Invitations

Invitation plaintext tokens are:

- Generated with a cryptographically secure random generator
- Delivered once by email
- Hashed before database storage
- Single-use
- Expiring
- Revocable
- Bound to one normalized email address

Invitation email delivery currently uses transaction.on_commit.

It will move to the transactional outbox when the outbox infrastructure
is introduced.

## Audit events

Security-relevant tenant actions produce append-only audit events.

Audit events capture:

- Organization
- Actor
- Action
- Resource type and identifier
- Request identifier
- Source IP
- User agent
- Before state
- After state
- Additional metadata
- Timestamp

## Consequences

Positive:

- Tenant isolation rules are explicit.
- Role enforcement is reusable.
- URL identifiers alone cannot switch tenant context.
- Business services remain safe outside HTTP views.
- Membership changes are auditable.
- Final-owner removal is protected by transactional row locking.

Negative:

- Each tenant request performs a membership lookup.
- Application code must consistently use scoped selectors.
- Application-level tenancy remains vulnerable to developer mistakes unless
  tests and future database-level controls remain rigorous.
- PostgreSQL row-level security is deferred until later enterprise hardening.
