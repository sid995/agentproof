# ADR-006: Canonical telemetry domain and OpenTelemetry normalization

## Status

Accepted

Implementation status: implemented and validated.

## Context

AgentProof must ingest telemetry from its own SDK and from OpenTelemetry-style
exports. Provider-specific payloads should not leak directly into persistence,
evaluation, or trace-explorer code.

Telemetry data is high-volume and tenant-sensitive. Direct model and admin
writes must not be able to create cross-tenant trace rows or structurally
invalid span trees.

## Decision

AgentProof normalizes telemetry into frozen canonical domain objects before
persistence.

The telemetry domain includes:

- `CanonicalTrace`
- `CanonicalSpan`
- `CanonicalSpanEvent`
- `TokenUsage`
- `ErrorDetails`
- `ModelAttributes`
- `ToolAttributes`

The `TelemetryNormalizer` protocol accepts source metadata and returns canonical
traces. The implemented normalizers are:

- Native AgentProof envelopes
- OpenTelemetry-style span exports

OpenTelemetry-style normalization supports standard OTLP JSON string-encoded
nanosecond timestamps, standard `KeyValue` attribute arrays, and the existing
flattened attribute shape. Trace names are derived from the root span rather
than export order.

Trace-tree validation rejects:

- Missing trace identifiers
- Duplicate span identifiers
- Missing parent references
- Parent cycles
- Negative durations
- End timestamps before start timestamps
- Child spans starting before their parent
- Child spans ending after an ended parent

Persistent telemetry tables are:

- `Trace`
- `Span`
- `SpanEvent`
- `TraceAnnotation`

Tenant scope is derived from parent relationships where possible:

- Trace scope comes from Environment.
- Span scope comes from Trace.
- SpanEvent scope comes from Span.
- TraceAnnotation scope comes from Trace.

Parent relationships are immutable after creation. Denormalized scope fields are
read-only in admin and corrected from cached parent objects or parent lookups in
model saves. Normal create paths reuse supplied/cached scope and avoid
unnecessary parent queries.

Database constraints enforce valid status/type values, unique trace/span
identities, non-negative durations and estimated costs, and `ended_at >=
started_at` where applicable.

`persist_canonical_trace` validates scope and trace structure before writing.
Duplicate trace identity failures are normalized to `TelemetryPersistenceError`.

## Consequences

Positive:

- Provider-specific payload parsing is isolated from persistence.
- Native and OpenTelemetry-style telemetry share one internal model.
- Trace-tree invariants are enforced before storage.
- Direct ORM/admin writes cannot silently drift tenant scope in normal paths.
- Future HTTP ingestion can reuse the canonical layer.

Negative:

- Canonical conversion adds an explicit translation layer before persistence.
- Bulk ingestion still needs separate batching/idempotency/redaction design.
- Some cross-table tenant guarantees remain application-enforced rather than
  database-trigger enforced.
