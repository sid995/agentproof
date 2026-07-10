# AgentProof Development Plan

This plan deliberately builds one vertical slice at a time. Each phase ends with a working capability.

Do not build every database model first and hope a product eventually emerges from the archaeological site.

---

# Phase 0: Define the engineering contract

## Objective

Make the product boundaries and engineering rules explicit before implementation.

## Tasks

1. Write the one-sentence product definition.
2. Confirm the central workflow:

    * ingest
    * inspect
    * create test case
    * evaluate
    * compare
    * decide
3. Define MVP and post-MVP scope.
4. Create architecture decision records.
5. Define code-quality rules.
6. Define supported Python and PostgreSQL versions.
7. Define local and production environments.
8. Decide how secrets are supplied.
9. Define naming conventions.
10. Define API versioning rules.

## Architecture decision records

Create ADRs as architectural decisions are made. Candidate decision areas
include:

* Modular monolith
* Django and Django REST Framework
* PostgreSQL as system of record
* Projects and deployment environments
* Environment-scoped API keys
* Canonical telemetry and OpenTelemetry normalization
* Celery and Redis for background jobs
* Transactional outbox
* Django templates and HTMX for the initial UI
* Pydantic at external data boundaries
* Service and selector application structure
* Versioned datasets and evaluators

## Phase completion documentation

Before marking any phase complete:

* Update this product plan with the phase status, implemented surface, remaining
  boundary, and validation command.
* Update architecture documentation when models, service boundaries, security
  rules, ingestion behavior, API contracts, or operational assumptions changed.
* Update OpenAPI documentation when public API behavior changed.
* Add or revise ADRs when the phase introduced, completed, or changed an
  architectural decision.
* Update user-facing or developer-facing README/docs when setup, usage, or
  validation commands changed.

## Exit criteria

* PRD is committed.
* Architecture decisions are committed.
* Repository conventions are documented.
* MVP workflow is fixed.

---

# Phase 1: Create the repository and Python environment

## Objective

Establish a professional Python project before feature work begins.

## Suggested repository structure

agentproof/
.github/
workflows/
backend/
src/
config/
apps/
accounts/
organizations/
projects/
api_keys/
telemetry/
datasets/
evaluators/
evaluations/
experiments/
policies/
alerts/
audit/
common/
tests/
manage.py
packages/
python-sdk/
src/
agentproof/
tests/
examples/
support-agent/
infra/
docker/
compose/
docs/
adr/
architecture/
api/
scripts/
pyproject.toml
uv.lock
compose.yml
README.md
CONTRIBUTING.md
SECURITY.md

## Install development tooling

Core:

* Django
* Django REST Framework
* psycopg
* Pydantic
* Celery
* Redis client

Quality:

* Ruff
* mypy
* django-stubs
* djangorestframework-stubs
* pre-commit

Testing:

* pytest
* pytest-django
* pytest-cov
* Hypothesis
* Factory Boy
* Testcontainers
* respx
* time-machine

Documentation:

* drf-spectacular
* MkDocs Material or Sphinx

## Configure Ruff

Enable rules for:

* pycodestyle
* Pyflakes
* import sorting
* bugbear
* comprehensions
* simplify
* annotations
* async mistakes
* pytest style
* security rules
* Django-specific checks

Do not enable every rule merely because it exists. Configure deliberate exceptions.

## Configure mypy

Requirements:

* Strict checking for domain, services, SDK, evaluators, and adapters.
* Reasonable exceptions for migrations and framework-generated files.
* No untyped public functions.
* No ignored errors without an explanation.

## Configure pre-commit

Run:

* Ruff check
* Ruff format check
* mypy
* file validation
* secret detection

## Create CI

Pull-request workflow:

1. Install dependencies.
2. Check formatting.
3. Run linting.
4. Run type checking.
5. Start PostgreSQL and Redis.
6. Run migrations.
7. Run tests.
8. Build documentation.
9. Build container.
10. Scan dependencies and container.

## Python concepts practised

* Packaging
* `pyproject.toml`
* Type checking
* Import boundaries
* Reproducible environments
* Tool configuration

## Exit criteria

* One command starts local dependencies.
* One command runs all checks.
* CI passes from a clean clone.
* Django health endpoint returns successfully.

---

# Phase 2: Bootstrap Django correctly

## Objective

Create the foundational Django configuration without burying everything in one settings file assembled during a caffeine
incident.

## Tasks

1. Create a custom user model immediately.
2. Split settings into:

    * base
    * local
    * test
    * production
3. Read configuration from environment variables.
4. Validate configuration at startup.
5. Configure PostgreSQL.
6. Configure Redis.
7. Configure structured logging.
8. Add request identifiers.
9. Configure ASGI.
10. Add health and readiness endpoints.
11. Configure static files.
12. Configure object-storage abstraction.
13. Configure DRF.
14. Configure OpenAPI generation.
15. Configure secure production defaults.

## Health endpoints

### Liveness

Checks that the process is running.

### Readiness

Checks:

* Database connectivity
* Redis connectivity
* Required configuration

Readiness should not call external model providers.

## Exit criteria

* Development and test settings work independently.
* Production settings reject missing required secrets.
* OpenAPI schema is generated.
* Health checks are tested.

---

# Phase 3: Implement organizations and tenant scoping

## Objective

Build tenant isolation before storing valuable data.

## Models

* User
* Organization
* Membership
* OrganizationInvitation

## Tasks

1. Implement email-based authentication.
2. Implement organization creation.
3. Add membership roles.
4. Add invitation flow.
5. Add organization switcher.
6. Create tenant-scoped queryset helpers.
7. Create permission classes.
8. Add audit events.
9. Test cross-tenant access.
10. Add an admin interface.

## Important design rule

Never write:

Model.objects.get(id=resource_id)

for tenant-owned resources.

Use a scoped selector:

get_resource_for_organization(
organization=organization,
resource_id=resource_id,
)

## Tests

* User from organization A cannot read organization B.
* Resource identifiers cannot bypass scoping.
* Viewer cannot mutate.
* Developer cannot manage members.
* Owner cannot accidentally delete the final ownership relationship.
* Invitations expire.
* Invitation tokens are single-use.

## Python concepts practised

* Custom managers
* QuerySets
* Decorators
* Permission composition
* Domain exceptions
* Transactional services

## Exit criteria

* Multi-tenant authorization works.
* Cross-tenant tests pass.
* Every privileged change produces an audit event.

---

# Phase 4: Implement projects and environments

## Status

Complete on branch `phases/phase-4`.

Backend, API, admin, minimal web pages, migration, OpenAPI, ADR, and tests are
implemented. The validation gate is green:

```bash
make schema
make check
```

Completed cleanup:

* Align API, web views, serializers, and tests with the current service contract.
* Keep project fields named `capture_mode` and
  `retention_days`.
* Use the `CreatedProject` response shape when project creation also creates
  the default development environment.
* Keep environment detail lookups tenant-scoped.
* Regenerate or update migrations so they match the current models.
* Remove stale or duplicate permission helpers outside the projects app.
* Ensure direct environment records cannot silently mismatch their parent
  project organization.
* Run `make schema` and `make check`.

## Objective

Create the hierarchy under which telemetry and evaluation data will live.

## Models

* Project
* Environment

## Tasks

1. Add project creation. Done.
2. Add environment creation. Done.
3. Add development, staging, production, and custom types. Done.
4. Add capture policies. Done.
5. Add retention configuration. Done.
6. Add project and environment selectors. Done.
7. Add permission checks. Done.
8. Add UI pages. Done with minimal Django templates.
9. Add API endpoints. Done.
10. Add audit events. Done.

## Implemented shape

Projects:

* Belong to one organization.
* Have name, slug, description, lifecycle status, default capture mode, default
  retention period, creator, and timestamps.
* Are administered by owners and administrators.
* Automatically create one development environment during project creation.

Environments:

* Belong to one organization and one project.
* Have name, slug, environment type, lifecycle status, optional capture-mode
  override, optional retention override, creator, and timestamps.
* Are managed by owners, administrators, and developers.
* Inherit project capture and retention defaults when no override is set.

Read-only users:

* Viewers can read project and environment data but cannot create or update it.

## Exit criteria

A user can create:

organization → project → environment

and all objects remain tenant-scoped.

Additional Phase 4 exit criteria:

* A project creation response includes both the project and the default
  development environment.
* Cross-tenant project and environment identifiers cannot bypass scoped
  selectors.
* OpenAPI schema includes project and environment endpoints without enum or URL
  namespace warnings.
* `make check` passes.

---

# Phase 5: Build secure API keys

Status: Implemented at the management and authentication-check layer. Final
phase validation still requires a fresh `make schema` and `make check` run after
the latest documentation/API changes.

## Objective

Authenticate SDK and ingestion requests safely.

## Tasks

1. Design the API-key format.
2. Generate cryptographically secure secrets.
3. Store only a secure hash.
4. Store a searchable public prefix.
5. Display plaintext only once.
6. Implement key scopes.
7. Implement expiration.
8. Implement revocation.
9. Implement constant-time verification.
10. Add per-key rate limits.
11. Update last-used timestamp outside the critical request path.
12. Add audit events.

## Current implementation

* Environment-scoped API keys live in the `api_keys` app.
* Key values use the `ap_live_<prefix>_<secret>` format.
* Creation returns plaintext once and stores only the public prefix plus a
  Django password hash of the secret.
* Keys carry organization, project, environment, scopes, creator, expiration,
  revocation, and last-used metadata.
* Browser-authenticated management endpoints list, create, and revoke keys.
* Bearer-token authentication validates presented keys for an environment and
  required scope.
* Revocation, expiration, wrong environment, wrong scope, and malformed keys are
  rejected.
* Per-key throttling uses the public key prefix.
* `last_used_at` is updated asynchronously through Celery.
* Creation and revocation write audit events without storing plaintext secrets.

Implemented endpoints:

* `GET /api/v1/environments/{environment_id}/api-keys/`
* `POST /api/v1/environments/{environment_id}/api-keys/`
* `POST /api/v1/api-keys/{api_key_id}/revoke/`
* `POST /api/v1/environments/{environment_id}/auth-check/`

## Suggested scopes

* traces:write
* traces:read
* evaluations:run
* datasets:read
* ci:read

## Tests

* Plaintext is never persisted.
* Revoked key fails.
* Expired key fails.
* Wrong environment fails.
* Wrong scope fails.
* Prefix collision is handled.
* Timing-safe verification function is used.
* Key value never appears in logs.

Current test coverage lives in `backend/tests/test_api_keys.py` and covers
hashed storage, one-time plaintext API responses, audit events, revocation,
expiration, wrong environment, wrong scope, prefix-collision retry/failure,
viewer permissions, revoke behavior, and bearer auth-check behavior.

## Remaining boundary

Phase 5 establishes the API-key security primitive and an auth-check endpoint.
Actual trace ingestion endpoints are part of the next ingestion phase and should
reuse `EnvironmentAPIKeyAuthentication` with the required scope for each write
path.

## Python concepts practised

* Secure random generation
* Hashing
* Constant-time comparison
* Custom DRF authentication
* Typed credentials
* Rate-limit design

## Exit criteria

A request authenticated with a valid environment key reaches a protected test endpoint.

---

# Phase 6: Define the telemetry domain

Status: Implemented and validated with `make check`.

## Objective

Design the canonical internal trace model before accepting provider-specific payloads.

## Models

* Trace
* Span
* SpanEvent
* TraceAnnotation

## Domain types

Create enums for:

* Trace status
* Span status
* Span type
* Capture mode

Suggested span types:

* agent
* model
* tool
* retrieval
* guardrail
* workflow
* custom

## Pydantic ingestion models

Create:

* TraceEnvelope
* SpanEnvelope
* EventEnvelope
* TokenUsage
* ErrorDetails
* ModelAttributes
* ToolAttributes

## Normalization interface

Define a protocol conceptually equivalent to:

TelemetryNormalizer:
supports(schema_version, source)
normalize(payload) -> list[CanonicalTrace]

Implement:

* Native AgentProof schema
* OpenTelemetry-style schema adapter

## Trace-tree validation

Validate:

* Unique span identifiers
* Valid parent references
* No cycles
* Valid timestamps
* Child timing consistency where possible
* Root-span determination

## Property-based tests

Generate random span trees and verify:

* Normalization never creates cycles.
* Every non-root span has one valid parent.
* Aggregated duration remains non-negative.
* Duplicate identifiers are rejected.

## Python concepts practised

* Pydantic discriminated unions
* Protocols
* Generics
* Recursive structures
* Graph validation
* Property-based testing
* Frozen domain models

## Exit criteria

Canonical traces can be validated and persisted through a service without an HTTP endpoint.

## Current implementation

Phase 6 is implemented in the `telemetry` app.

Implemented backend surface:

* Durable models: `Trace`, `Span`, `SpanEvent`, and `TraceAnnotation`.
* Domain enums: trace status, span status, and span type. Capture mode remains
  owned by the existing project/environment configuration.
* Frozen canonical domain objects for traces, spans, span events, token usage,
  errors, model metadata, and tool metadata.
* Native AgentProof Pydantic envelopes for trace, span, event, token, error,
  model, and tool payloads.
* `TelemetryNormalizer` protocol with native AgentProof and OpenTelemetry-style
  normalizers.
* Trace-tree validation for duplicate span identifiers, missing parents, cycles,
  timestamp ordering, child timing, and root-span determination. Child spans may
  not start before their parent, including when the parent span is still
  in-flight.
* OpenTelemetry-style normalization accepts standard OTLP JSON shapes for
  string-encoded nanosecond timestamps and `KeyValue` attribute arrays, while
  retaining support for the existing flattened attribute shape. OTLP trace names
  are derived from the root span rather than export order.
* Token and cost metadata is normalized from native payloads and OpenTelemetry
  attributes. Malformed, negative, or non-finite `agentproof.estimated_cost`
  values are rejected during parsing.
* `persist_canonical_trace` service for validating and persisting canonical
  traces, spans, and span events in one transaction. Duplicate trace identity
  errors are surfaced as `TelemetryPersistenceError`.
* Tenant scope is derived from parent relationships where possible:
  `Trace` from `Environment`, `Span` from `Trace`, `SpanEvent` from `Span`, and
  `TraceAnnotation` from `Trace`. Parent relationships are immutable after
  creation and admin treats denormalized scope fields as read-only.
* Database invariants enforce valid status/type values, unique trace and span
  identities, non-negative durations and estimated costs, and `ended_at` not
  preceding `started_at` for trace and span rows.
* Django admin registration for the telemetry tables.

Tests:

* `backend/tests/test_telemetry.py` covers canonical persistence,
  organization/project/environment consistency, duplicate trace identity,
  malformed span trees, native normalization, OpenTelemetry-style normalization,
  OTLP JSON timestamp and `KeyValue` attribute parsing, model/admin-safe tenant
  derivation, database invariants, and Hypothesis-generated span tree
  validation.

Validated gate:

* `UV_CACHE_DIR=.uv-cache make check`

## Remaining boundary

Phase 6 intentionally does not add HTTP ingestion endpoints. Phase 7 should
reuse this canonical domain layer from authenticated ingestion APIs and add
batch acceptance, capture policy, redaction, idempotency, outbox processing, and
per-record accepted/rejected responses.

---

# Phase 7: Build the ingestion pipeline

## Objective

Accept trace batches safely and efficiently.

## Request pipeline

1. Authenticate key.
2. Resolve organization, project, and environment.
3. Enforce request size.
4. Parse schema version.
5. Validate payload.
6. Apply capture policy.
7. Redact sensitive values.
8. Normalize telemetry.
9. Calculate idempotency identifier.
10. Persist traces and spans in bulk.
11. Create processing outbox events.
12. Return accepted and rejected records.
13. Process aggregates asynchronously.

## Services

Create:

* ingest_trace_batch
* redact_trace
* normalize_trace
* persist_trace
* enqueue_trace_processing

## Idempotency

Use:

* External trace ID
* Environment ID
* Schema version

Optionally include a payload hash to identify conflicting duplicate submissions.

## Partial failures

A batch response should identify:

* Accepted traces
* Duplicate traces
* Invalid traces
* Rejected traces

Do not reject the entire batch because the seventh record contains malformed attributes. Humans already made CSV imports
miserable enough.

## Performance work

1. Use bulk inserts.
2. Avoid one query per span.
3. Measure query counts.
4. Add only necessary indexes.
5. Set payload limits.
6. Benchmark small and large batches.
7. Move large raw payloads to object storage when required.

## Tests

* Duplicate request
* Duplicate trace within batch
* Invalid parent span
* Payload too large
* Mixed valid and invalid records
* Redaction
* Metadata-only mode
* Database failure
* Outbox recovery

## Python concepts practised

* Iterators
* Chunking
* Batch processing
* Context managers
* Transactions
* Error aggregation
* Idempotency
* Efficient serialization

## Exit criteria

A valid API key can submit a batch, receive an acknowledgement, and view persisted records through Django admin.

## Implemented surface

Status: Complete.

Implemented:

* `POST /api/v1/ingest/traces` authenticated with environment-scoped bearer API
  keys requiring `traces:write`.
* Batch envelope validation for `agentproof` / `agentproof.v1` and
  `opentelemetry` / `otel.v1` source-schema pairs.
* Per-record responses for accepted, duplicate, invalid, and rejected records.
* Idempotency on environment, external trace ID, and schema version, including
  duplicate detection inside one batch.
* Capture policy using the environment effective capture mode:
  metadata-only, redacted, and full with mandatory secret-pattern filtering.
* Phase 7 `TraceProcessingEvent` marker and Celery task for accepted traces.
  This is intentionally narrow and does not replace the full Phase 8
  transactional outbox.
* OpenAPI schema refreshed for the ingestion endpoint.

Remaining boundary:

* `/api/v1/ingest/spans` and `/api/v1/ingest/otel` aliases remain future work.
* Generic transactional outbox publishing remains Phase 8.
* Payload-hash conflict detection and large raw-payload object storage remain
  future hardening work.

Validated gates:

* `UV_CACHE_DIR=.uv-cache uv run pytest backend/tests/test_api_keys.py backend/tests/test_telemetry.py backend/tests/test_ingestion.py -q`
* `UV_CACHE_DIR=.uv-cache make schema`
* `UV_CACHE_DIR=.uv-cache make check`

---

# Phase 8: Implement the transactional outbox

## Objective

Make database changes and background dispatch reliable.

## Tasks

1. Create OutboxEvent model.
2. Add event creation within domain transactions.
3. Build an outbox publisher.
4. Lock unpublished rows safely.
5. Publish Celery tasks.
6. Mark events as published.
7. Retry stale events.
8. Record publishing errors.
9. Add metrics.
10. Test worker crashes between publish and acknowledgement.

## Design requirement

Consumers must remain idempotent because at-least-once delivery permits duplicates.

## Python concepts practised

* Database locking
* Transaction boundaries
* Idempotent consumers
* Retry algorithms
* Exponential backoff
* Distributed failure handling

## Exit criteria

Stopping the publisher midway does not lose required work.

## Implemented surface

Status: Complete.

Implemented:

* Generic `OutboxEvent` model with tenant scope, event type, aggregate
  identity, JSON payload, pending/publishing/published/failed states, publish
  attempts, retry timing, lock timing, publish timing, and last-error capture.
* Service APIs for transactional enqueue, locked batch publishing, stale
  publishing-row recovery, bounded exponential retry, and terminal failure
  after repeated publish errors.
* Celery tasks:
  * `outbox.publish_pending_events`
  * `outbox.recover_stale_events`
* Publisher registry with `trace.accepted` as the first event type. Trace
  ingestion now creates the trace, Phase 7 `TraceProcessingEvent`, and generic
  outbox event in one database transaction.
* At-least-once delivery semantics. Consumers remain idempotent; duplicate
  dispatch of `ingestion.process_trace_events` remains safe.
* Django admin visibility and requeue action for pending or failed outbox
  events.
* Structured logging counters for selected, published, failed, retried, and
  stale-recovered events.

Remaining boundary:

* Invitation email delivery still uses `transaction.on_commit` because moving
  it to the generic JSON outbox would require storing invitation plaintext
  tokens. That should wait for an encrypted/sensitive-payload outbox contract.
* API key last-used updates remain direct Celery dispatch because they are
  usage metadata, not required domain work for this phase.
* Poison-message/dead-letter operator workflows beyond terminal `failed` state
  remain future operational hardening.

Validated gates:

* `UV_CACHE_DIR=.uv-cache uv run pytest backend/tests/test_outbox.py backend/tests/test_ingestion.py -q`
* `UV_CACHE_DIR=.uv-cache make migrations-check`
* `UV_CACHE_DIR=.uv-cache make check`

---

# Phase 9: Build the Python SDK

## Objective

Make instrumentation easy enough that another developer would willingly use it.

## SDK package structure

```text
agentproof/
├── __init__.py
├── client.py
├── config.py
├── context.py
├── trace.py
├── span.py
├── decorators.py
├── exceptions.py
├── transport/
│ ├── base.py
│ ├── sync_http.py
│ └── async_http.py
├── exporters/
│ └── batching.py
├── schemas/
└── integrations/
```

## Step 1: Configuration

Support:

* API key
* Endpoint
* Project environment
* Timeout
* Batch size
* Flush interval
* Capture mode
* Error mode

Configuration sources:

1. Explicit constructor arguments
2. Environment variables
3. Defaults

## Step 2: Context propagation

Use `contextvars` to track:

* Current trace
* Current span
* Parent relationships

The SDK must work correctly with asynchronous tasks.

## Step 3: Context managers

Implement:

* Synchronous trace context manager
* Asynchronous trace context manager
* Synchronous span context manager
* Asynchronous span context manager

Ensure finalization runs when exceptions occur.

## Step 4: Decorators

Implement decorators that:

* Preserve function metadata.
* Preserve typed signatures as far as practical.
* Support synchronous functions.
* Support coroutine functions.
* Capture exceptions.
* Avoid double instrumentation.

## Step 5: Export

Implement:

* In-memory buffer
* Batch exporter
* Background worker
* Flush
* Shutdown
* Retry
* Backpressure strategy

## Step 6: Safe failure

Default behavior:

* Telemetry errors are logged.
* User application execution continues.

Strict mode:

* Telemetry errors propagate.

## Step 7: Publish

1. Build wheel and source distribution.
2. Validate package metadata.
3. Publish to a test package index.
4. Install into the sample application.
5. Publish stable release.

## Tests

* Nested spans
* Async task context
* Exceptions
* Flush on shutdown
* Server unavailable
* Queue full
* Forked process behavior
* Repeated shutdown
* Decorated generator rejection or support
* Thread safety

## Python concepts practised

* `contextvars`
* Decorators
* Signature preservation
* Context managers
* Async context managers
* Threads
* Queues
* Resource finalization
* Protocols
* Package publishing

## Exit criteria

The sample agent sends traces using fewer than ten lines of setup code.

## Status

Status: Complete.

Implemented surface:

* `agentproof-sdk` now exposes `AgentProofClient`, `AgentProofConfig`,
  decorators, context managers, structured exceptions, native `agentproof.v1`
  schemas, sync and async HTTP transports, and batching exporters.
* The SDK sends native batches to `POST /api/v1/ingest/traces` with bearer
  environment API-key authentication. Backend tenant scope remains derived from
  the API key.
* Trace and span context managers use `contextvars` for sync and async parent
  relationships. Finalization captures exceptions and preserves user
  application execution in safe failure modes.
* Export uses an in-memory queue, background worker, bounded batching, retry,
  flush, shutdown, and queue backpressure behavior.
* The sample agent in `examples/sample_agent.py` sends a trace with fewer than
  ten setup lines.

Remaining boundary:

* TestPyPI/PyPI publication remains an operational release step requiring
  package-index credentials and an explicit release instruction.
* Full OpenTelemetry exporter integration remains future compatibility work;
  Phase 9 uses native AgentProof export as the happy path.

Validated gates:

* `UV_CACHE_DIR=.uv-cache uv run pytest packages/python-sdk/tests -q`
* `UV_CACHE_DIR=.uv-cache uv run ruff check packages/python-sdk/src packages/python-sdk/tests`
* `UV_CACHE_DIR=.uv-cache uv run mypy packages/python-sdk/src`
* `UV_CACHE_DIR=.uv-cache make build-sdk`
* `UV_CACHE_DIR=.uv-cache make check`

---

# Phase 10: Build the trace explorer

## Objective

Turn stored telemetry into a useful debugging interface.

## Recommended UI approach

Implemented with:

* Django templates
* Dependency-free server-rendered HTML
* A small shared template/base style

HTMX, Alpine.js, Tailwind CSS, and a frontend build pipeline remain out of
scope for this phase. This keeps the project centred on Python while still
producing a credible product interface.

## Pages

### Trace list

Display:

* Time
* Name
* Status
* Duration
* Model
* Tokens
* Cost
* Environment
* Tags

### Trace detail

Display:

* Summary header
* Span waterfall
* Hierarchical span tree
* Input and output
* Model calls
* Tool calls
* Errors
* Raw attributes
* Annotation panel

## Query work

Create selectors:

* list_traces
* get_trace_summary
* get_trace_tree
* get_trace_cost_breakdown
* get_trace_token_breakdown

Use:

* `select_related`
* `prefetch_related`
* annotated aggregates
* cursor pagination

Measure query counts in tests.

## Optional advanced feature

Use server-sent events for evaluation progress later. Do not add WebSockets merely to animate a progress bar.

## Exit criteria

A user can find and diagnose a failed agent run without accessing the database or raw logs.

## Implementation status

Phase 10 is implemented as a logged-in Django web explorer under `/traces/`.
The trace list is scoped to the active organization, supports project,
environment, status, search, tag, and cursor filters, and displays the core
debugging columns from stored telemetry. The trace detail page shows summary
metadata, span waterfall/tree rows, inputs and outputs, model and tool spans,
errors, raw attributes, token and cost breakdowns, span events, and a trace
annotation panel.

Read behavior is centralized in telemetry selectors:

* `list_traces`
* `get_trace_summary`
* `get_trace_tree`
* `get_trace_cost_breakdown`
* `get_trace_token_breakdown`

This phase intentionally does not add public JSON trace APIs or dataset-case
creation from traces.

Validation evidence:

* `UV_CACHE_DIR=.uv-cache uv run pytest backend/tests/test_trace_explorer.py -q`
* `UV_CACHE_DIR=.uv-cache make check`

---

# Phase 11: Build versioned datasets

## Objective

Convert observed failures into durable regression cases.

## Tasks

1. Create Dataset.
2. Create mutable draft representation.
3. Add TestCase editing.
4. Add “Create from trace.”
5. Validate case schemas.
6. Publish immutable DatasetVersion.
7. Calculate content hash.
8. Clone published version into a new draft.
9. Add JSONL import.
10. Add JSONL export.
11. Add tags and filtering.

## Immutability rule

Once a dataset version is published:

* Test cases cannot be edited.
* Test cases cannot be deleted.
* Metadata affecting evaluation cannot change.
* A new version is required.

## Import pipeline

1. Upload file.
2. Store temporary object.
3. Process in worker.
4. Validate each row.
5. Return row-level errors.
6. Create draft cases.
7. Delete temporary object after retention window.

## Python concepts practised

* Immutable data models
* Hashing
* Streaming file processing
* Generators
* Validation error accumulation
* Object storage
* Background imports

## Exit criteria

A production trace becomes a published test case through the UI.

## Implementation status

Phase 11 is implemented as a logged-in Django web surface under `/datasets/`.
Datasets are scoped to the active organization and project, maintain at most
one open mutable draft, and publish immutable numbered versions with
deterministic SHA-256 content hashes. Draft cases can be created manually or
from trace detail pages, edited while the draft is open, imported from JSONL,
and exported from published versions as JSONL.

Implemented surface:

* `datasets` app models for dataset containers, drafts, draft cases, published
  versions, immutable version cases, and JSONL import jobs.
* Service-layer writes for dataset creation, draft metadata updates, draft-case
  CRUD, trace-to-case creation, version publishing, version cloning, JSONL
  import processing, import cleanup, and JSONL export.
* JSON Schema validation for draft input/output schemas and case payloads.
* Server-rendered pages for dataset list/create, dataset detail, case editing,
  import status/errors, published version detail, clone, export, and trace
  promotion into a dataset case.
* Application-level immutability guards for published versions and published
  version cases.
* Database-level `PROTECT` relations prevent published versions or their cases
  from being removed through parent dataset, organization, or version deletes.

Remaining boundary:

* No public DRF dataset API is added in this phase.
* The existing `datasets:read` API-key scope remains future evaluator/API work.
* Automated recurring cleanup scheduling is not added; the cleanup task exists
  for worker/operations wiring.

Validation evidence:

* `UV_CACHE_DIR=.uv-cache uv run pytest backend/tests/test_datasets.py backend/tests/test_dataset_web.py -q`
* `UV_CACHE_DIR=.uv-cache make lint`
* `UV_CACHE_DIR=.uv-cache make type-check`
* `UV_CACHE_DIR=.uv-cache make check`

---

# Phase 12: Build the evaluator framework

## Objective

Create an extensible, typed evaluation engine.

## Step 1: Core types

Create:

* EvaluationContext
* EvaluationOutcome
* EvaluatorConfiguration
* EvaluatorError

## Step 2: Evaluator protocol

An evaluator must:

* Validate its configuration.
* Receive a typed context.
* Return a normalized outcome.
* Explain failures.
* Declare determinism.

## Step 3: Registry

Implement explicit registration.

The registry maps evaluator type to:

* Configuration model
* Implementation
* Version
* Display metadata

## Step 4: Deterministic evaluators

Build in this order:

1. Exact match
2. Contains
3. Regular expression
4. JSON schema
5. Required tool
6. Forbidden tool
7. Tool arguments
8. Latency threshold
9. Cost threshold

## Step 5: Composite evaluator

Support:

* Weighted child evaluators
* Required child evaluators
* Aggregate threshold

## Step 6: Model judge

Create a provider protocol:

* complete
* structured_complete
* estimate_cost

Implement one provider initially.

Requirements:

* Typed structured output
* Timeouts
* Retries
* Malformed-output handling
* Usage recording
* Cost recording
* Prompt-injection-resistant framing

## Tests

* Evaluator registry conflicts
* Invalid configuration
* Missing required execution data
* Malformed judge result
* Provider timeout
* Retry exhaustion
* Deterministic result repeatability
* Composite weighting

## Python concepts practised

* Protocols
* Abstract interfaces
* Generic configuration types
* Registries
* Dependency inversion
* Structured concurrency
* Typed provider adapters

## Exit criteria

An evaluator can run against a stored case execution independently of the web layer.

---

# Phase 13: Build asynchronous evaluation runs

## Objective

Execute full datasets reliably through Celery.

## Step 1: Run state machine

Allowed transitions:

- pending → preparing
- preparing → running
- running → completed
- running → completed_with_errors
- running → cancelling
- cancelling → cancelled
- pending → failed
- preparing → failed
- running → failed

Reject invalid transitions.

## Step 2: Run creation

The service must:

1. Verify permissions.
2. Resolve immutable versions.
3. Estimate case count.
4. Create run.
5. Create outbox event.
6. Commit.
7. Return run identifier.

## Step 3: Prepare run

Worker creates one CaseExecution per test case using bulk creation.

## Step 4: Execute case

Each case task:

1. Acquires an idempotency lock or checks terminal state.
2. Marks case running.
3. Calls the target application.
4. Persists output and trace.
5. Runs deterministic evaluators.
6. Runs model judges.
7. Persists results.
8. Marks case complete.
9. Updates run progress.

## Step 5: Finalize run

Finalizer:

* Verifies all cases are terminal.
* Computes aggregate scores.
* Computes cost and latency.
* Records failure categories.
* Marks run complete.
* Generates an outbox event.

## Step 6: Cancellation

Cancellation must:

* Mark the run cancelling.
* Prevent new case execution.
* Allow in-flight calls to finish or terminate at timeout.
* Mark remaining queued cases cancelled.
* Finalize the run.

## Step 7: Progress UI

Begin with polling.

Add server-sent events only after the polling implementation is stable.

## Tests

* Worker dies mid-case.
* Same task delivered twice.
* Provider timeout.
* User cancels.
* One evaluator fails.
* Database temporarily unavailable.
* Run finalizer executes twice.
* Stale running case is recovered.

## Python concepts practised

* State machines
* Task orchestration
* Distributed locks
* Timeouts
* Cancellation
* Idempotent retries
* Exception classification

## Exit criteria

A dataset of at least one hundred cases runs reliably across worker restarts.

---

# Phase 14: Build experiments and comparisons

## Objective

Compare candidate configurations against a trusted baseline.

## Tasks

1. Create ApplicationConfiguration.
2. Encrypt external credentials.
3. Create Experiment.
4. Associate baseline run.
5. Associate candidate runs.
6. Calculate per-case deltas.
7. Calculate aggregate deltas.
8. Classify win, loss, or tie.
9. Build comparison interface.
10. Add downloadable report.

## Comparison dimensions

* Overall score
* Evaluator score
* Pass rate
* Cost
* Latency
* Provider errors
* Application errors
* Tool-selection differences

## Statistical honesty

Do not declare that a 0.2 percent improvement has transformed civilization.

Show:

* Dataset size
* Absolute difference
* Relative difference
* Number of wins
* Number of losses
* Number of ties

Later, add confidence intervals where appropriate.

## Exit criteria

A user can understand exactly which cases improved and which regressed.

---

# Phase 15: Build regression policies and CI integration

## Objective

Convert evaluation evidence into a machine-readable release decision.

## Policy rules

Implement:

1. Minimum overall score
2. Minimum evaluator score
3. Maximum failed cases
4. No regression on critical cases
5. Maximum cost increase
6. Maximum latency increase
7. Required evaluator pass

## Rule interface

Each policy rule should:

* Validate configuration.
* Receive baseline and candidate summaries.
* Return pass, fail, or indeterminate.
* Return evidence.
* Remain deterministic.

## CI workflow

1. CI calls start endpoint.
2. AgentProof returns run identifier.
3. CI polls status.
4. AgentProof returns policy decision.
5. CI exits with success or failure.
6. Output includes dashboard link.

## Optional CLI

Create an `agentproof` CLI using Typer.

Commands:

* agentproof login
* agentproof evaluations run
* agentproof evaluations status
* agentproof experiments compare
* agentproof ci check

## Python concepts practised

* Command-line applications
* Exit codes
* Typed configuration
* Policy pattern
* Deterministic rule engines
* API clients

## Exit criteria

A sample GitHub Actions workflow fails when a candidate violates a policy.

---

# Phase 16: Build notifications and webhooks

## Objective

Notify external systems reliably.

## Tasks

1. Create webhook endpoints.
2. Encrypt signing secrets.
3. Sign payloads with HMAC.
4. Add event IDs and timestamps.
5. Record delivery attempts.
6. Retry retryable failures.
7. Stop retrying permanent failures.
8. Add manual redelivery.
9. Add email notification adapter.
10. Display delivery history.

## Webhook retry example

* Immediate attempt
* Delayed retry with exponential backoff
* Maximum attempt count
* Dead state after exhaustion

## Security

* Resolve and validate destination addresses.
* Defend against server-side request forgery.
* Block private network destinations unless explicitly supported.
* Revalidate redirects.
* Set strict connection and response timeouts.
* Limit response body size.

## Exit criteria

A policy failure reaches a test webhook receiver with a verifiable signature.

---

# Phase 17: Add redaction, retention, and governance

## Objective

Make telemetry storage defensible rather than casually collecting every secret users accidentally send.

## Redaction engine

Create a chain of redactors:

* Header redactor
* Exact-key redactor
* Regex redactor
* Secret-pattern redactor
* Email redactor
* Custom tenant rule redactor

Use a protocol so redactors are independently testable.

## Redaction invariant tests

After redaction:

* Known API-key formats are absent.
* Authorization headers are absent.
* Configured fields are absent.
* Original sensitive values do not appear in logs or error messages.

## Retention engine

1. Resolve environment retention.
2. Find expired traces in bounded batches.
3. Delete dependent records.
4. Delete object-storage artifacts.
5. Record deletion audit event.
6. Continue safely after partial failure.

## Audit export

Generate a report containing:

* Dataset version
* Evaluator versions
* Application configuration hash
* Evaluation summary
* Policy rules
* Policy decision
* Actor history
* Timestamps

## Exit criteria

A user can configure capture and retention and download an evidence report.

---

# Phase 18: Performance engineering

## Objective

Measure the system rather than guessing where it is slow.

## Ingestion benchmarks

Measure:

* 1 trace with 10 spans
* 100 traces with 10 spans each
* 1 trace with 500 spans
* Mixed valid and invalid batch
* Duplicate batch

## Query benchmarks

Measure:

* Recent trace list
* Filter by error
* Filter by model
* Trace detail with 500 spans
* Experiment comparison with 1,000 cases

## Evaluation benchmarks

Measure:

* 100 deterministic cases
* 1,000 deterministic cases
* Concurrent provider calls
* Cancellation
* Retry storm

## Optimization order

1. Measure.
2. Inspect query count.
3. Add missing indexes.
4. Remove N+1 queries.
5. Bulk operations.
6. Cache stable aggregates.
7. Partition tables only when demonstrated.
8. Extract a service only after the monolith reaches a proven boundary.

## Profiling tools

Use:

* Django query instrumentation
* Python profiler
* memory profiler
* PostgreSQL EXPLAIN ANALYZE
* load-testing tool
* OpenTelemetry traces

## Exit criteria

Publish a benchmark report with hardware, dataset, methodology, and limitations.

---

# Phase 19: Production deployment

## Objective

Deploy a secure and observable system.

## Containers

Create separate process commands for:

* web
* Celery worker
* Celery scheduler
* outbox publisher
* migration job

## Production dependencies

* Managed PostgreSQL
* Managed Redis
* S3-compatible storage
* Container platform
* Error tracking
* Metrics backend
* Log aggregation

## Deployment sequence

1. Build immutable image.
2. Scan image.
3. Run tests.
4. Run migration compatibility checks.
5. Deploy migration job.
6. Deploy web.
7. Deploy workers.
8. Run smoke tests.
9. Verify health.
10. Verify ingestion.
11. Verify evaluation task.
12. Verify alerts.

## Production hardening

* Non-root container
* Read-only filesystem where practical
* Resource limits
* Worker concurrency limits
* Database connection limits
* Secure headers
* Trusted proxy configuration
* Backup policy
* Restore test
* Secret rotation
* Rate limits
* Dependency update automation

## Exit criteria

The public demo survives a clean redeployment and restores from documented backup procedures.

---

# Phase 20: Build the public demonstration

## Objective

Make the engineering understandable to recruiters, founders, and other developers.

## Sample application

Build a support agent that:

* Searches a small document collection.
* Calls an order-status tool.
* Produces a final answer.
* Contains one intentionally weak prompt.
* Has a corrected candidate prompt.

## Demo sequence

1. Run the weak agent.
2. Display its trace.
3. Identify an incorrect tool call.
4. Add the trace to a dataset.
5. Publish the dataset.
6. Run baseline and candidate.
7. Show the candidate fixing one case but breaking another.
8. Apply the policy.
9. Show CI rejecting the regression.
10. Open the audit report.

## Public material

Create:

* README
* Architecture diagram
* Local setup guide
* SDK quick start
* API reference
* Evaluation guide
* Security document
* Benchmark report
* Five-minute video
* Technical article

## Article topics

1. Designing a multi-tenant Django SaaS
2. Building an async-safe Python telemetry SDK
3. Reliable Celery workflows with a transactional outbox
4. Testing idempotent distributed jobs
5. Designing versioned evaluation datasets
6. Evaluating AI systems without trusting one opaque score
7. Building CI release gates for probabilistic software

## Exit criteria

A new developer can understand and run the project without private instructions.

---

# Recommended package decisions

## Web application

* Django
* Django REST Framework
* drf-spectacular
* psycopg
* django-filter
* django-htmx
* whitenoise for simple static-file deployment where appropriate

## Validation and domain boundaries

* Pydantic
* jsonschema

## Background processing

* Celery
* redis
* django-celery-beat when scheduled tasks require database-managed schedules

## SDK and HTTP clients

* httpx
* tenacity only where a shared, explicit retry utility is preferable to custom logic
* opentelemetry-api
* opentelemetry-sdk

## Storage and security

* django-storages
* boto3
* cryptography
* argon2-cffi

## Testing

* pytest
* pytest-django
* Hypothesis
* Factory Boy
* Testcontainers
* respx
* time-machine

## Quality

* uv
* Ruff
* mypy
* django-stubs
* pre-commit

## CLI

* Typer
* Rich

## Data processing

Add Polars only when dataset analysis or exports justify it. Do not install a data-frame engine to sum four numbers.

---

# Recommended learning order

Study each subject immediately before its implementation phase.

1. Django settings and application structure
2. Custom user models
3. Django ORM constraints and indexes
4. Transactions and row locking
5. DRF authentication and permissions
6. Python type system
7. Pydantic models
8. Context managers and decorators
9. `contextvars`
10. Async I/O
11. Celery task semantics
12. Idempotency
13. Transactional outbox
14. Protocols and adapter patterns
15. Property-based testing
16. PostgreSQL query analysis
17. OpenTelemetry concepts
18. Packaging and publishing
19. Container deployment
20. Production observability

---

# Minimum implementation order

When scope becomes overwhelming, follow only this sequence:

1. Repository quality setup
2. Organization
3. Project
4. Environment
5. API key
6. Trace models
7. Native ingestion endpoint
8. Minimal SDK
9. Trace list
10. Trace detail
11. Dataset
12. Test case from trace
13. Exact-match evaluator
14. Required-tool evaluator
15. Evaluation run
16. Candidate comparison
17. Regression policy
18. CI endpoint
19. Deployment
20. Demonstration

Everything else is an enhancement.

---

# Definition of done for every feature

A feature is complete only when:

* Product behavior is documented.
* Relevant phase, architecture, ADR, OpenAPI, and README documentation has been
  reviewed and updated or explicitly marked unchanged.
* Permission rules are explicit.
* Service logic is typed.
* Database constraints exist where appropriate.
* Unit tests exist.
* Integration tests exist where external infrastructure is involved.
* Error behavior is defined.
* Audit behavior is defined.
* Metrics are added.
* Logs contain correlation identifiers.
* OpenAPI documentation is updated.
* User documentation is updated.
* The feature works in the deployed environment.

---

# Final portfolio standard

The project should finish with:

* A polished public repository
* A deployed application
* A published Python SDK
* A realistic sample agent
* Automated CI evaluation
* Architecture decision records
* At least one property-based test suite
* At least one load-test report
* A security threat model
* A database indexing report
* An incident or failure-recovery document
* A short product demonstration
* Several technical articles derived from the implementation

The strongest part of AgentProof will not be the number of packages installed. It will be the visible evidence that each
package solves a measured problem and that the system behaves correctly when networks fail, workers restart, requests
repeat, and users provide data shaped like an eldritch JSON monument.
