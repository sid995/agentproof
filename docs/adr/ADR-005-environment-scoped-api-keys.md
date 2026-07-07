# ADR-005: Environment-scoped API keys

## Status

Accepted

Implementation status: implemented and validated.

## Context

AgentProof needs machine-to-machine credentials for SDK and ingestion traffic.
Those credentials must be scoped narrowly enough to prevent one leaked key from
accessing unrelated tenants, projects, or environments.

API keys also need a one-time plaintext display, durable revocation, expiration,
and last-used tracking.

## Decision

AgentProof API keys are scoped to one organization, project, and environment.

API keys store:

- Organization
- Project
- Environment
- Name
- Prefix
- Key hash
- Scopes
- Creator
- Creation time
- Expiration time
- Revocation time
- Last-used time

Plaintext key material is shown only once at creation. The database stores a
hash and a lookup prefix, never the full plaintext key.

Supported scopes are:

- `traces:write`
- `traces:read`

API-key authentication validates:

1. Key format
2. Prefix lookup
3. Hash match
4. Revocation state
5. Expiration state
6. Environment match
7. Required scope

API key management remains behind authenticated organization/project/environment
authorization. SDK-style authentication uses the presented key and returns an
environment-scoped authentication context.

## Consequences

Positive:

- Ingestion credentials are naturally bounded to a deployment environment.
- Plaintext key exposure is limited to creation time.
- Revocation and expiration are first-class operational controls.
- Future ingestion endpoints can share the same authentication primitive.

Negative:

- Every ingestion request needs a prefix lookup and hash verification.
- Environment movement or deletion must preserve key audit history.
- Broader cross-environment ingestion will require explicit additional
  credentials or a future higher-scope key type.
