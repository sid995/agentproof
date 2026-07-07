# ADR-008: Transactional outbox

Status: Accepted

Date: 2026-07-07

## Context

AgentProof creates database records that require follow-up background work.
Directly calling Celery from request or service code can lose that work when the
database transaction commits but the broker publish fails, or when a worker
crashes after publishing but before recording acknowledgement.

Phase 7 introduced `TraceProcessingEvent` as a narrow durable marker for
accepted traces. Phase 8 needs a generic outbox that other domains can reuse
without replacing the existing idempotent consumer state.

## Decision

Add a dedicated `outbox` app with `OutboxEvent` rows created inside domain
transactions.

An outbox event records:

* tenant scope through `organization`;
* `event_type`;
* aggregate type and aggregate id;
* JSON payload;
* pending, publishing, published, and failed states;
* attempt count, next retry time, lock time, publish time, and last error.

The publisher claims ready rows, marks them `publishing`, dispatches through an
event-type registry, and marks successful rows `published`. Failed publishes
return to `pending` with bounded exponential backoff until the event reaches a
terminal `failed` state. A recovery task moves stale `publishing` rows back to
`pending`.

The first registered event type is `trace.accepted`, which dispatches
`ingestion.process_trace_events` for the existing `TraceProcessingEvent`.

## Consequences

Background work has at-least-once delivery semantics. Consumers must remain
idempotent because a publisher can crash after broker publish and before marking
the outbox row published.

Invitation emails are not moved to this outbox yet because the current
invitation flow would require storing plaintext tokens in a JSON payload. That
needs an encrypted or sensitive-payload contract first.

API-key last-used updates also stay as direct Celery dispatch because they are
usage metadata rather than required domain work.
