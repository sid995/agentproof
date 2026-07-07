# ADR-007: Trace ingestion pipeline

Status: Accepted

Date: 2026-07-07

## Context

AgentProof needs to accept telemetry from SDKs and OpenTelemetry-style
exporters without trusting tenant scope from submitted payloads. Phase 5 added
environment-scoped API keys, and Phase 6 added canonical telemetry models,
normalizers, validation, and persistence. Phase 7 connects those layers through
an authenticated ingestion API.

The product plan also calls for a transactional outbox, but the generic outbox
publisher is Phase 8. Phase 7 still needs a durable marker that accepted traces
need post-ingestion processing.

## Decision

Phase 7 exposes `POST /api/v1/ingest/traces` as the ingestion endpoint.

The endpoint:

* Authenticates with an environment API key requiring `traces:write`.
* Derives organization, project, and environment scope from the verified key.
* Accepts `agentproof` / `agentproof.v1` and `opentelemetry` / `otel.v1`
  batches.
* Normalizes through the telemetry app rather than storing provider-specific
  shapes directly.
* Applies environment capture policy and built-in secret redaction before
  persistence.
* Treats environment, external trace ID, and schema version as the idempotency
  identity.
* Returns per-record accepted, duplicate, invalid, and rejected results.
* Creates one `TraceProcessingEvent` for each accepted trace.

`TraceProcessingEvent` is intentionally narrow. It records post-ingestion work
for accepted traces and can be requeued by a recovery task, but it is not the
generic transactional outbox. The generic outbox remains a Phase 8 concern.

## Consequences

The ingestion path now has a small durable processing marker before the full
outbox exists. This keeps Phase 7 useful and testable while avoiding a partial
generic outbox implementation.

Future `/api/v1/ingest/spans` and `/api/v1/ingest/otel` endpoints can be added
as aliases or specialized surfaces without changing the canonical telemetry
storage contract.
