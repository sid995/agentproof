# AgentProof

## Product Requirements Document

### Document status

Status: Initial product specification
Product type: Developer infrastructure SaaS
Primary implementation language: Python
Primary framework: Django
Working product name: AgentProof
Primary audience: AI application engineering teams
Deployment model: Cloud-hosted SaaS with future self-hosted support

---

# 1. Executive summary

AgentProof is an AI agent reliability, evaluation, observability, and governance platform.

Engineering teams connect their AI applications through a lightweight Python SDK or an OpenTelemetry-compatible
ingestion API. AgentProof records model calls, tool calls, retrieval operations, agent decisions, latency, token usage,
cost, failures, and user-defined metadata.

Teams then use AgentProof to:

* Inspect complete agent execution traces.
* Build versioned evaluation datasets.
* Run deterministic and model-based evaluators.
* Compare prompts, models, tools, retrieval strategies, and agent versions.
* Replay failed production executions.
* Detect regressions before deployment.
* Enforce release quality gates.
* Monitor cost, latency, errors, and quality.
* Redact sensitive information.
* Maintain auditable records of changes and evaluations.

The first product release focuses on the full developer loop:

1. Instrument an AI application.
2. Send traces to AgentProof.
3. Inspect failed or expensive executions.
4. Turn traces into evaluation test cases.
5. compare a candidate version against a baseline.
6. Block a release when quality drops.
7. produce an audit report explaining what was tested.

---

# 2. Problem statement

AI applications are probabilistic systems composed of several moving parts:

* Prompts
* Models
* Tool definitions
* Retrieval pipelines
* Agent instructions
* Memory
* External APIs
* User input
* Evaluation logic

A change to any component can improve one scenario while silently breaking another.

Traditional application monitoring reports whether a request failed, how long it took, and where an exception occurred.
It does not reliably answer:

* Did the answer satisfy the user’s request?
* Did the agent call the correct tool?
* Did the tool receive valid arguments?
* Did the model invent unsupported information?
* Did a prompt change reduce quality?
* Is a cheaper model sufficiently accurate?
* Which production failures should become regression tests?
* Can the team prove what was evaluated before deployment?

Teams often solve this with spreadsheets, custom scripts, provider dashboards, scattered logs, and manual testing. These
approaches are difficult to reproduce, compare, audit, or integrate into CI/CD.

AgentProof provides one system for collecting execution data, defining quality, running repeatable evaluations, and
enforcing release standards.

---

# 3. Product vision

AgentProof should become the reliability control plane for AI applications.

An engineering team should be able to answer four questions from one system:

1. What happened?
2. Was the result good?
3. What changed?
4. Should this version be released?

---

# 4. Product positioning

## 4.1 Category

AI application reliability and evaluation infrastructure.

## 4.2 Primary value proposition

AgentProof helps engineering teams ship AI agents safely by converting production traces into repeatable evaluations and
automated release gates.

## 4.3 Product tagline

Test, trace, and ship reliable AI agents.

## 4.4 Differentiation

AgentProof will focus on the connection between observability and release engineering.

The product will not stop at displaying traces. It will let teams:

* Convert a trace into a test case.
* Replay the case against a candidate version.
* Compare the candidate against a baseline.
* Apply deterministic release policies.
* Record the evidence behind the decision.

---

# 5. Target users

## 5.1 Primary persona: AI application engineer

Responsibilities:

* Builds agents, assistants, RAG systems, and tool-calling workflows.
* Changes prompts, models, retrieval settings, and tools.
* Debugs failed AI executions.
* Needs repeatable tests.

Needs:

* Detailed execution traces.
* Fast local instrumentation.
* Easy dataset creation.
* Reproducible comparisons.
* CI integration.

## 5.2 Secondary persona: Engineering lead

Responsibilities:

* Owns production reliability.
* Reviews releases.
* Controls cost and latency.
* Defines quality standards.

Needs:

* Regression dashboards.
* Release quality gates.
* Cost and latency comparisons.
* Failure trends.
* Team-level audit history.

## 5.3 Secondary persona: AI product manager

Responsibilities:

* Defines user-facing quality expectations.
* Reviews production failures.
* Prioritizes improvements.

Needs:

* Understandable evaluations.
* Example-level comparisons.
* Labels and comments.
* Quality trends by feature or customer segment.

## 5.4 Future persona: Compliance or security reviewer

Responsibilities:

* Reviews data handling.
* Verifies evaluation procedures.
* Investigates incidents.

Needs:

* Data retention policies.
* Redaction records.
* Immutable audit events.
* Exportable reports.
* Access history.

---

# 6. Jobs to be done

## 6.1 Instrumentation

When I deploy an AI workflow, I want to capture its complete execution so I can understand what happened without
reconstructing it from unrelated logs.

## 6.2 Debugging

When an agent produces a bad result, I want to inspect every model, retrieval, and tool step so I can identify the
cause.

## 6.3 Evaluation

When I change a prompt or model, I want to run it against a stable dataset so I can measure the effect.

## 6.4 Regression prevention

When a candidate version performs worse than production, I want the build to fail automatically so the regression is not
released.

## 6.5 Cost control

When comparing model configurations, I want to see quality, latency, and cost together so I do not optimize one metric
blindly.

## 6.6 Governance

When someone asks why a version was approved, I want a record of the dataset, configuration, results, policy, and
approver.

---

# 7. Product goals

## 7.1 MVP goals

The MVP must allow a developer to:

1. Create an organization, project, and environment.
2. Create a scoped ingestion API key.
3. Install the AgentProof Python SDK.
4. Instrument an AI workflow.
5. Send trace batches to AgentProof.
6. Inspect traces and spans in a web interface.
7. Create datasets and test cases.
8. Define evaluators.
9. Run evaluation suites asynchronously.
10. Compare baseline and candidate runs.
11. configure a regression policy.
12. receive a pass or fail result suitable for CI.
13. review an audit trail.

## 7.2 Engineering goals

The project must demonstrate:

* Maintainable Django architecture.
* Strong static typing.
* Async and synchronous Python boundaries.
* Protocol-based adapter design.
* Background processing.
* Idempotent distributed jobs.
* Transactional consistency.
* Multi-tenant data isolation.
* API and SDK design.
* Observability.
* Property-based testing.
* Performance profiling.
* Secure secret handling.
* Package publishing.
* Production deployment.

## 7.3 Business goals

The product must be understandable in a short demonstration.

A viewer should see meaningful value within five minutes:

* An agent execution appears.
* A failure is identified.
* The failure becomes a regression test.
* A candidate prompt is evaluated.
* A release gate blocks the weaker version.

---

# 8. Non-goals

The MVP will not:

* Train foundation models.
* Host model inference.
* Replace general infrastructure monitoring.
* Provide a complete notebook environment.
* Support every AI framework through custom integrations.
* Provide enterprise SSO.
* Provide on-premise deployment.
* Provide full billing automation.
* Automatically guarantee legal compliance.
* Store arbitrary application logs unrelated to AI execution.
* Provide a visual agent workflow builder.
* Become another general-purpose prompt playground.

---

# 9. Product principles

## 9.1 Evidence over scores

Every aggregate score must link back to individual examples and execution traces.

## 9.2 Reproducibility

Every evaluation must record:

* Dataset version
* Evaluator version
* Application version
* Model configuration
* Prompt version
* Runtime configuration
* Start and completion timestamps

## 9.3 Secure by default

Prompt and response capture must be configurable. API keys must never be stored in plaintext.

## 9.4 Framework-neutral ingestion

The internal model must not depend on one agent framework or model provider.

## 9.5 Human-readable failure analysis

Developers must be able to understand why a test failed.

## 9.6 Progressive complexity

A developer should receive value from tracing before configuring advanced evaluations.

---

# 10. Core product terminology

## Organization

A tenant representing a company or team.

## Project

An AI application or service owned by an organization.

## Environment

A project deployment context such as development, staging, or production.

## Trace

One complete application or agent execution.

## Span

A timed operation within a trace.

Examples:

* Agent invocation
* Model call
* Tool call
* Retrieval operation
* Guardrail check
* Custom operation

## Dataset

A named collection of evaluation cases.

## Dataset version

An immutable snapshot of a dataset.

## Test case

An input, expected behavior, metadata, and optional reference output.

## Evaluator

A versioned method for judging an execution.

## Evaluation run

An asynchronous execution of a dataset against one application configuration.

## Evaluation result

The result of one evaluator applied to one test-case execution.

## Experiment

A comparison between two or more application configurations.

## Baseline

The currently accepted configuration.

## Candidate

A proposed configuration being tested.

## Regression policy

Rules deciding whether a candidate passes or fails.

---

# 11. Release scope

## 11.1 MVP scope

### Identity and tenancy

* User registration and login
* Organization creation
* Organization membership
* Owner, administrator, developer, and viewer roles
* Tenant-scoped queries
* Project creation
* Environment creation

### API key management

* Project and environment-scoped keys
* Key creation
* One-time plaintext display
* Stored key hash
* Revocation
* Last-used timestamp
* Expiration
* Scope restrictions

### Telemetry ingestion

* Single-trace ingestion
* Batch ingestion
* Idempotency keys
* Payload validation
* Schema versioning
* OpenTelemetry-compatible attribute mapping
* Metadata-only capture mode
* Redacted capture mode
* Full capture mode
* Payload size limits
* Rejected-record reporting

### Trace explorer

* Trace list
* Filtering
* Search
* Trace detail
* Span waterfall
* Model-call details
* Tool-call details
* Token and cost summary
* Error display
* JSON attribute inspection
* Trace annotations
* Convert trace to test case

### Evaluation datasets

* Dataset creation
* Dataset versioning
* Manual test-case creation
* Test-case creation from a trace
* JSONL import
* JSONL export
* Metadata tags
* Dataset cloning
* Immutable published versions

### Evaluators

* Exact match
* Contains text
* Regular expression
* JSON schema validation
* Maximum latency
* Maximum cost
* Required tool call
* Forbidden tool call
* Tool argument validation
* Semantic similarity
* Model-based rubric judge
* Composite weighted evaluator

### Evaluation execution

* Background execution
* Progress tracking
* Retry policy
* Cancellation
* Per-case timeout
* Run status
* Result storage
* Error classification
* Partial completion
* Re-run failed cases

### Experiments

* Baseline configuration
* Candidate configuration
* Side-by-side results
* Score deltas
* Cost deltas
* Latency deltas
* Example-level comparison
* Win, loss, and tie classification

### Regression policies

* Minimum overall score
* Minimum evaluator-specific score
* Maximum failure count
* Maximum relative cost increase
* Maximum relative latency increase
* Required evaluator pass
* CI-compatible result endpoint
* Signed result token or status check

### Alerts

* Evaluation run failed
* Regression policy failed
* Error rate exceeded
* Cost threshold exceeded
* Webhook notification
* Email notification

### Audit

* Membership changes
* API key creation and revocation
* Dataset publication
* Evaluator changes
* Evaluation execution
* Policy changes
* Release approvals
* Data deletion
* Exportable audit report

## 11.2 Post-MVP scope

* Prompt registry
* Prompt diffs
* Model registry
* Production trace sampling
* Scheduled evaluations
* Advanced replay
* Human review queues
* Reviewer agreement metrics
* Enterprise SSO
* SCIM
* PostgreSQL row-level security
* Self-hosted deployment
* Bring-your-own object storage
* Custom evaluator plugins
* Public evaluator marketplace
* Slack and Microsoft Teams integrations
* GitHub status checks
* GitLab pipeline integration
* Data residency controls

---

# 12. Primary user journeys

## 12.1 First-time activation

1. User creates an account.
2. User creates an organization.
3. User creates a project.
4. A development environment is created automatically.
5. User creates an ingestion API key.
6. Product displays an SDK installation command.
7. User copies a minimal instrumentation example.
8. User runs the example.
9. AgentProof receives the trace.
10. The UI displays the trace.
11. Product marks the organization as activated.

Success criterion:

The user sees their first trace without manually constructing an ingestion request.

## 12.2 Production failure to regression test

1. User filters traces with errors or low ratings.
2. User opens one trace.
3. User inspects the model and tool spans.
4. User selects “Add to dataset.”
5. User chooses an existing dataset or creates one.
6. AgentProof copies the trace input and relevant expectations.
7. User adds expected behavior.
8. User publishes a new dataset version.
9. The case becomes part of future evaluation runs.

## 12.3 Candidate evaluation

1. User selects a dataset version.
2. User selects the current baseline.
3. User defines a candidate configuration.
4. User selects evaluators.
5. User starts an experiment.
6. Background workers execute all cases.
7. Results appear incrementally.
8. The comparison page displays quality, cost, and latency.
9. A regression policy produces a pass or fail decision.

## 12.4 CI release gate

1. CI submits an evaluation run request.
2. AgentProof returns a run identifier.
3. CI polls the run status or receives a webhook.
4. AgentProof evaluates the candidate.
5. AgentProof applies the configured policy.
6. CI receives a machine-readable pass or fail response.
7. The result links to the full evidence in AgentProof.

---

# 13. Functional requirements

Priority meanings:

* P0: Required for MVP
* P1: Important after the central workflow works
* P2: Future enhancement

## 13.1 Accounts and organizations

### FR-ORG-001: Create organization

Priority: P0

A logged-in user must be able to create an organization.

Acceptance criteria:

* Organization name is required.
* Organization slug is unique.
* Creator becomes owner.
* An audit event is recorded.
* A default project is not created automatically.

### FR-ORG-002: Invite member

Priority: P1

An owner or administrator must be able to invite a user by email.

Acceptance criteria:

* Invitation expires.
* Invitation token is hashed.
* Existing members cannot be invited again.
* Accepted invitation creates a membership.
* Invitation acceptance is audited.

### FR-ORG-003: Role enforcement

Priority: P0

Endpoints and UI actions must enforce organization roles.

Role capabilities:

Owner:

* Full organization access
* Delete organization
* Transfer ownership
* Manage billing

Administrator:

* Manage projects and members
* Manage policies
* Manage API keys

Developer:

* View and send traces
* Manage datasets
* Run evaluations
* Manage project-level configurations

Viewer:

* Read-only access

## 13.2 Projects and environments

### FR-PROJ-001: Create project

Priority: P0

A member with sufficient permissions must be able to create a project.

Fields:

* Name
* Slug
* Description
* Lifecycle status
* Default capture mode
* Default retention period
* Creator

Project creation creates a default development environment so a newly created
project can immediately receive environment-scoped configuration and, later,
API keys and telemetry.

### FR-PROJ-002: Create environment

Priority: P0

Supported environment types:

* Development
* Staging
* Production
* Custom

Environment names must be unique within a project.

Fields:

* Name
* Slug
* Environment type
* Lifecycle status
* Optional capture-mode override
* Optional retention override
* Creator

When an environment has no capture or retention override, it inherits the
project default.

### FR-PROJ-003: Project and environment authorization

Priority: P0

Owners and administrators may create and update projects.

Owners, administrators, and developers may create and update environments.

Viewers may read project and environment records but may not mutate them.

## 13.3 API keys

### FR-KEY-001: Create key

Priority: P0

The product must display the complete key only once.

Stored values:

* Public key prefix
* Secure hash
* Name
* Organization
* Project
* Environment
* Scopes
* Created by
* Created at
* Expires at
* Revoked at
* Last used at

### FR-KEY-002: Authenticate ingestion request

Priority: P0

Authentication must:

* Reject malformed keys.
* Reject expired keys.
* Reject revoked keys.
* Use constant-time hash comparison.
* Validate project and environment scope.
* Update last-used information asynchronously.

## 13.4 Trace ingestion

### FR-ING-001: Accept trace batch

Priority: P0

Endpoint:

POST /api/v1/ingest/traces

Request behavior:

* Authenticate API key.
* Validate schema version.
* Enforce request size.
* Accept one or more traces.
* Validate required identifiers.
* Support idempotency.
* Return per-record acceptance status.
* Enqueue post-processing.
* Respond before expensive aggregation completes.

### FR-ING-002: Deduplicate trace

Priority: P0

A duplicate combination of organization, environment, external trace identifier, and schema version must not create
another trace.

### FR-ING-003: Redact sensitive values

Priority: P1

Before storage, the ingestion pipeline must support:

* Exact-key redaction
* Regular-expression redaction
* Secret-pattern redaction
* Email redaction
* Authorization header redaction
* User-defined redaction rules

### FR-ING-004: Normalize provider data

Priority: P0

Provider-specific attributes must be mapped into an internal canonical structure.

The raw provider attributes may be retained when capture policy permits.

## 13.5 Trace explorer

### FR-TRACE-001: List traces

Priority: P0

Filters:

* Project
* Environment
* Time range
* Status
* Model provider
* Model name
* Trace name
* Error type
* Minimum duration
* Minimum cost
* Tags
* User identifier
* Session identifier

### FR-TRACE-002: Inspect trace

Priority: P0

Trace detail must display:

* Start and end time
* Total duration
* Status
* Total tokens
* Estimated cost
* Root input
* Root output
* Span hierarchy
* Span timings
* Errors
* Attributes
* Events
* Model requests
* Model responses
* Tool names
* Tool arguments
* Tool results

### FR-TRACE-003: Annotate trace

Priority: P1

A user must be able to:

* Add a label.
* Add a comment.
* Mark expected or unexpected behavior.
* Assign a failure category.
* Add the trace to a dataset.

## 13.6 Dataset management

### FR-DATA-001: Create dataset

Priority: P0

Required fields:

* Name
* Project
* Description

Optional fields:

* Tags
* Input schema
* Output schema

### FR-DATA-002: Version dataset

Priority: P0

Publishing a dataset version must produce an immutable snapshot.

Changes after publication must create a new draft.

### FR-DATA-003: Define test case

Priority: P0

Test-case fields:

* Stable logical identifier
* Input
* Expected output
* Expected tool calls
* Forbidden tool calls
* Reference context
* Metadata
* Tags

### FR-DATA-004: Import and export

Priority: P1

The product must support JSONL import and export.

Import must return row-level validation errors.

## 13.7 Evaluators

### FR-EVAL-001: Evaluator interface

Priority: P0

All evaluators must implement one conceptual interface:

* Validate configuration.
* Evaluate an execution.
* Return a normalized result.
* Explain the result.
* Declare whether the evaluator is deterministic.
* Declare required input fields.

Normalized result:

* Status
* Numeric score
* Boolean pass
* Explanation
* Evidence
* Error details
* Evaluator version
* Duration
* Cost

### FR-EVAL-002: Deterministic evaluators

Priority: P0

The first release must include:

* Exact match
* Contains
* Regular expression
* JSON schema
* Latency threshold
* Cost threshold
* Required tool
* Forbidden tool
* Tool argument schema

### FR-EVAL-003: Model-based rubric evaluator

Priority: P0

A rubric evaluator must support:

* Provider configuration
* Model configuration
* System rubric
* Scoring range
* Pass threshold
* Structured JSON result
* Retry on malformed result
* Token and cost recording
* Explanation storage

### FR-EVAL-004: Evaluator versioning

Priority: P0

Changes to evaluator configuration must create a new immutable version.

Historic runs must continue to reference the original evaluator version.

## 13.8 Evaluation runs

### FR-RUN-001: Start run

Priority: P0

A user must select:

* Dataset version
* Application target
* Evaluator versions
* Runtime configuration
* Optional concurrency limit

### FR-RUN-002: Execute cases

Priority: P0

Execution must:

* Create one case execution for every test case.
* Be resumable.
* Be idempotent.
* Apply per-case timeout.
* Record retries.
* Record provider errors separately from evaluator failures.
* Continue when one case fails unless the run is cancelled.

### FR-RUN-003: Track progress

Priority: P0

Statuses:

* Pending
* Preparing
* Running
* Cancelling
* Cancelled
* Completed
* Completed with errors
* Failed

Progress:

* Total cases
* Queued cases
* Running cases
* Completed cases
* Failed cases

## 13.9 Experiments

### FR-EXP-001: Compare variants

Priority: P0

An experiment must contain:

* One baseline
* One or more candidates
* Dataset version
* Evaluators
* Regression policy

### FR-EXP-002: Example-level comparison

Priority: P0

For every test case, display:

* Baseline output
* Candidate output
* Baseline scores
* Candidate scores
* Score delta
* Cost delta
* Latency delta
* Winner
* Failure explanation

## 13.10 Regression policy

### FR-POL-001: Define policy

Priority: P0

Rules may include:

* Overall score must not decrease.
* Required evaluator score must exceed threshold.
* Candidate failure count must not exceed baseline.
* Cost increase must stay below percentage.
* Latency increase must stay below percentage.
* Selected critical cases must all pass.

### FR-POL-002: Evaluate policy

Priority: P0

Policy result:

* Passed
* Failed
* Indeterminate

The result must include every applied rule and its evidence.

## 13.11 Alerts and webhooks

### FR-ALT-001: Configure webhook

Priority: P1

Webhook requirements:

* HTTPS destination
* Secret signing key
* Event selection
* Retry policy
* Delivery history
* Manual redelivery

### FR-ALT-002: Send evaluation event

Priority: P1

Events:

* evaluation.started
* evaluation.completed
* evaluation.failed
* policy.passed
* policy.failed

## 13.12 Audit log

### FR-AUD-001: Record security-sensitive actions

Priority: P0

Audit events must be append-only from the application perspective.

Required fields:

* Organization
* Actor
* Action
* Resource type
* Resource identifier
* Timestamp
* Request identifier
* IP address
* User agent
* Before state
* After state
* Additional metadata

---

# 14. Non-functional requirements

## 14.1 Performance

Initial service targets:

* Trace-ingestion response p95 below 300 milliseconds for valid batches that are accepted asynchronously.
* Trace visible in the dashboard within five seconds.
* Trace-list response p95 below 500 milliseconds for normal indexed queries.
* Evaluation status updates visible within five seconds.
* Batch ingestion supports at least 500 spans per request.
* System design supports one million spans per day without architectural replacement.

These are engineering targets, not promises engraved into a stone tablet.

## 14.2 Reliability

* Ingestion must be idempotent.
* Background jobs must be retryable.
* Job retries must not duplicate evaluation results.
* Poison messages must move to a dead-letter workflow.
* Partial batch failures must not reject valid records.
* Evaluation runs must survive worker restarts.
* External provider errors must use exponential backoff with jitter.

## 14.3 Security

* Passwords use Django-supported secure password hashing.
* API keys are hashed at rest.
* Secrets never appear in application logs.
* Organization authorization is applied before object lookup results are returned.
* CSRF protection remains enabled for browser requests.
* API endpoints use explicit authentication classes.
* Login and key endpoints are rate-limited.
* Sensitive fields support redaction.
* Audit records cover privileged operations.
* Dependency scanning runs in CI.
* Containers run as non-root users.
* Production cookies are secure, HTTP-only, and same-site restricted.

## 14.4 Privacy

Capture modes:

Metadata only:

* Store timing, provider, model, token counts, status, and selected tags.
* Do not store prompts, responses, tool arguments, or tool results.

Redacted:

* Process content through configured redaction rules before storage.

Full:

* Store submitted content after mandatory secret-pattern filtering.

Retention:

* Configurable by environment.
* Default production retention should be shorter than development retention unless explicitly changed.
* Deletion jobs must remove associated object-storage content.
* Deletion actions must be audited.

## 14.5 Maintainability

* Business logic must not live in serializers, views, signals, or Celery task bodies.
* External providers must be behind typed protocols.
* Django signals must not coordinate critical business workflows.
* Migrations must be reviewed and tested.
* Public interfaces must be typed.
* Circular imports are prohibited.
* Each Django application must have a clear ownership boundary.

## 14.6 Accessibility

* Keyboard navigation
* Semantic HTML
* Visible focus states
* Accessible labels
* Colour-independent status indicators
* Screen-reader-friendly tables and dialogs

---

# 15. Technical architecture

## 15.1 Architectural style

Use a modular Django monolith.

Reasons:

* One deployment unit reduces operational complexity.
* Django provides authentication, ORM, migrations, administration, and security.
* Product boundaries remain explicit through Django applications.
* Background workers scale separately.
* High-volume components can be extracted later after usage demonstrates the need.

Do not begin with microservices. Distributed systems provide enough problems without volunteering for unnecessary ones.

## 15.2 Runtime components

### Web application

Responsibilities:

* Browser interface
* Management API
* Authentication
* Authorization
* Configuration
* Trace queries
* Dataset management
* Evaluation control
* Audit views

Runtime:

* Django under ASGI
* Gunicorn-compatible ASGI process manager or equivalent
* ASGI worker implementation

### Ingestion API

Initially deployed within the Django application.

Responsibilities:

* API key authentication
* Request validation
* Idempotency
* Redaction
* Canonical mapping
* Bulk persistence
* Background-job enqueueing

It may become a separate service only when measured traffic requires independent scaling.

### Celery workers

Queues:

* ingestion-processing
* evaluations
* provider-calls
* notifications
* maintenance
* exports

### Scheduler

Responsibilities:

* Retention deletion
* Usage aggregation
* Webhook retry
* Scheduled evaluation support
* Stale run recovery
* API-key cleanup

### PostgreSQL

Responsibilities:

* Tenant data
* Configuration
* Traces
* Spans
* Datasets
* Evaluation results
* Audit data
* Usage summaries

### Redis

Responsibilities:

* Celery broker
* Short-lived caching
* Rate limiting
* Distributed locks
* Progress counters

Redis must not be the system of record.

### Object storage

Responsibilities:

* Large raw trace payloads
* Dataset imports
* Dataset exports
* Audit exports
* Large evaluation artifacts

## 15.3 Django applications

Suggested boundaries:

* accounts
* organizations
* projects
* api_keys
* telemetry
* datasets
* evaluators
* evaluations
* experiments
* policies
* alerts
* audit
* usage
* common
* web
* api

## 15.4 Internal application layers

Within each Django application:

### Models

Database representation and local invariants.

### Services

State-changing use cases.

Examples:

* create_api_key
* publish_dataset
* start_evaluation_run
* cancel_evaluation_run
* apply_regression_policy

### Selectors

Read-focused query functions.

Examples:

* list_traces
* get_trace_detail
* list_dataset_versions
* get_experiment_comparison

### Tasks

Thin Celery task entry points that call services.

### Adapters

External integration implementations.

Examples:

* OpenAI adapter
* Anthropic adapter
* webhook adapter
* object-storage adapter

### Protocols

Typed interfaces for adapters.

Avoid creating repository abstractions around every Django model. Django’s ORM already exists. Abstract boundaries where
external systems or genuinely interchangeable implementations exist.

## 15.5 Event processing

Critical internal events must use a transactional outbox.

Example:

1. A database transaction creates an evaluation run.
2. The same transaction creates an outbox event.
3. A worker publishes the event to Celery.
4. The outbox event is marked published.
5. A recovery task republishes stale unpublished events.

This prevents a committed database record from existing without its required background job.

The outbox stores tenant-scoped `OutboxEvent` rows. Publishers claim ready rows
with row-level locks where the database supports them, mark them `publishing`,
dispatch the registered Celery task, then mark them `published`. Failures return
events to `pending` with bounded exponential backoff until repeated failures
move them to `failed`.

The first event type is `trace.accepted`. Trace ingestion commits the canonical
trace, the Phase 7 `TraceProcessingEvent`, and the generic outbox event in the
same transaction. The trace-processing consumer is idempotent so duplicate
dispatch after a publisher crash remains safe.

---

# 16. Data model

Every tenant-owned table must include an organization identifier directly or through an enforced parent relationship.

## 16.1 Identity

### User

Use Django’s custom user model from the beginning.

Fields:

* id
* email
* display_name
* password
* is_active
* is_staff
* created_at
* updated_at

### Organization

Fields:

* id
* name
* slug
* status
* created_at
* updated_at

### Membership

Fields:

* id
* organization_id
* user_id
* role
* status
* joined_at

Constraint:

* Unique organization and user pair

## 16.2 Projects

### Project

Fields:

* id
* organization_id
* name
* slug
* description
* status
* capture_mode
* retention_days
* created_by_id
* created_at
* updated_at

Constraint:

* Unique organization and slug pair
* Status must be valid.
* Default capture mode must be valid.
* Default retention must be between 1 and 3,650 days.

### Environment

Fields:

* id
* organization_id
* project_id
* name
* slug
* environment_type
* status
* capture_mode_override
* retention_days_override
* created_by_id
* created_at
* updated_at

Constraint:

* Unique project and slug pair
* Environment type must be valid.
* Status must be valid.
* Capture override must be empty or a valid capture mode.
* Retention override must be empty or between 1 and 3,650 days.

Application services must prevent an environment organization from differing
from the parent project organization.

## 16.3 API keys

### APIKey

Fields:

* id
* organization_id
* project_id
* environment_id
* name
* prefix
* key_hash
* scopes
* created_by_id
* created_at
* expires_at
* revoked_at
* last_used_at

## 16.4 Telemetry

Telemetry is normalized into canonical traces before durable storage. The
`telemetry` app owns trace storage, frozen canonical domain objects, native
AgentProof envelopes, OpenTelemetry-style normalization, trace-tree validation,
and service-level persistence. The ingestion app owns authenticated HTTP batch
acceptance, capture policy, redaction, idempotency, per-record result
aggregation, and Phase 7 processing markers.

Current telemetry normalization supports:

* Native AgentProof trace envelopes.
* OpenTelemetry-style span exports.
* Standard OTLP JSON string-encoded nanosecond timestamps.
* Standard OTLP `KeyValue` attribute arrays and flattened attribute maps.
* Root-span-based trace naming for OpenTelemetry exports.
* Rejection of malformed, negative, or non-finite estimated cost values.

Current trace ingestion supports:

* `POST /api/v1/ingest/traces`.
* Environment API-key bearer authentication with `traces:write`.
* `agentproof` / `agentproof.v1` and `opentelemetry` / `otel.v1` batches.
* Per-record accepted, duplicate, invalid, and rejected responses.
* Idempotency on environment, external trace ID, and schema version.
* Effective environment capture mode with metadata-only, redacted, and full
  storage behavior.
* `TraceProcessingEvent` records for accepted traces. This is a Phase 7
  processing marker consumed through the Phase 8 generic transactional outbox.

Trace-tree validation requires:

* Unique span identifiers inside a trace.
* Valid parent span references.
* At least one root span.
* No parent cycles.
* Non-negative durations.
* Span end timestamps not preceding start timestamps.
* Child spans not starting before their parent, including in-flight parents.
* Child spans not ending after an ended parent.

Tenant scope is parent-derived wherever possible. Trace organization and
project scope comes from the selected environment; span scope comes from its
trace; span event scope comes from its span; annotation scope comes from its
trace. Parent relationships are immutable after creation so denormalized scope
columns cannot drift through normal model or admin writes.

### Trace

Fields:

* id
* organization_id
* project_id
* environment_id
* external_trace_id
* schema_version
* name
* status
* started_at
* ended_at
* duration_ms
* input
* output
* attributes
* tags
* error_type
* error_message
* total_input_tokens
* total_output_tokens
* estimated_cost
* user_identifier
* session_identifier
* created_at

Important indexes:

* organization, project, environment, started_at
* organization, external_trace_id
* organization, status, started_at
* project, session_identifier
* GIN index on selected JSONB attributes only when query demand exists

Constraints:

* Unique organization, environment, external trace identifier, and schema version
* Valid trace status
* Non-negative duration when present
* `ended_at` must be greater than or equal to `started_at` when present
* Non-negative estimated cost when present

### Span

Fields:

* id
* organization_id
* trace_id
* external_span_id
* parent_external_span_id
* span_type
* name
* status
* started_at
* ended_at
* duration_ms
* attributes
* input
* output
* error_type
* error_message
* provider_name
* model_name
* input_tokens
* output_tokens
* estimated_cost
* created_at

Constraints:

* Unique trace and external span identifier pair
* Valid span type
* Valid span status
* Non-negative duration when present
* `ended_at` must be greater than or equal to `started_at` when present
* Non-negative estimated cost when present

### SpanEvent

Fields:

* id
* organization_id
* span_id
* name
* occurred_at
* attributes

Scope:

* `organization_id` is derived from the parent span.

### TraceAnnotation

Fields:

* id
* organization_id
* trace_id
* author_id
* annotation_type
* value
* comment
* created_at

Scope:

* `organization_id` is derived from the parent trace.

## 16.5 Datasets

### Dataset

Fields:

* id
* organization_id
* project_id
* name
* slug
* description
* created_by_id
* created_at
* updated_at

### DatasetVersion

Fields:

* id
* organization_id
* dataset_id
* version_number
* status
* content_hash
* published_by_id
* published_at
* created_at

Constraint:

* Unique dataset and version number pair

### TestCase

Fields:

* id
* organization_id
* dataset_version_id
* logical_id
* name
* input
* expected_output
* expected_tool_calls
* forbidden_tool_calls
* reference_context
* metadata
* tags
* source_trace_id
* created_at

## 16.6 Evaluators

### Evaluator

Fields:

* id
* organization_id
* project_id
* name
* evaluator_type
* description
* created_by_id
* created_at

### EvaluatorVersion

Fields:

* id
* organization_id
* evaluator_id
* version_number
* configuration
* implementation_version
* is_deterministic
* content_hash
* created_at

## 16.7 Evaluations

### ApplicationConfiguration

Fields:

* id
* organization_id
* project_id
* name
* application_version
* endpoint
* encrypted_credentials
* model_configuration
* prompt_configuration
* tool_configuration
* metadata
* created_at

### EvaluationRun

Fields:

* id
* organization_id
* project_id
* dataset_version_id
* application_configuration_id
* status
* initiated_by_id
* total_cases
* completed_cases
* failed_cases
* started_at
* completed_at
* cancelled_at
* summary
* error_message
* created_at

### EvaluationRunEvaluator

Fields:

* evaluation_run_id
* evaluator_version_id
* weight
* required

### CaseExecution

Fields:

* id
* organization_id
* evaluation_run_id
* test_case_id
* status
* attempt_count
* input
* output
* trace_id
* duration_ms
* estimated_cost
* error_type
* error_message
* started_at
* completed_at

Constraint:

* Unique evaluation run and test case pair

### EvaluationResult

Fields:

* id
* organization_id
* case_execution_id
* evaluator_version_id
* status
* passed
* score
* explanation
* evidence
* duration_ms
* estimated_cost
* error_message
* created_at

Constraint:

* Unique case execution and evaluator version pair

## 16.8 Experiments and policies

### Experiment

Fields:

* id
* organization_id
* project_id
* name
* dataset_version_id
* baseline_run_id
* status
* created_by_id
* created_at

### ExperimentCandidate

Fields:

* id
* experiment_id
* evaluation_run_id
* name

### RegressionPolicy

Fields:

* id
* organization_id
* project_id
* name
* description
* created_at

### RegressionPolicyVersion

Fields:

* id
* regression_policy_id
* version_number
* rules
* content_hash
* created_at

### PolicyDecision

Fields:

* id
* organization_id
* experiment_id
* candidate_run_id
* policy_version_id
* status
* rule_results
* decided_at

## 16.9 Operations

### OutboxEvent

Fields:

* id
* organization_id
* event_type
* aggregate_type
* aggregate_id
* payload
* status
* created_at
* updated_at
* next_attempt_at
* locked_at
* published_at
* attempt_count
* last_error

### WebhookEndpoint

Fields:

* id
* organization_id
* target_url
* encrypted_secret
* subscribed_events
* active
* created_at

### WebhookDelivery

Fields:

* id
* webhook_endpoint_id
* event_type
* payload
* status
* response_status
* attempt_count
* next_attempt_at
* created_at

### AuditEvent

Fields:

* id
* organization_id
* actor_id
* action
* resource_type
* resource_id
* request_id
* source_ip
* user_agent
* before_state
* after_state
* metadata
* occurred_at

---

# 17. API design

## 17.1 API categories

### Browser management API

Authentication:

* Session authentication
* CSRF protection

### Public management API

Authentication:

* Personal or service token
* Future OAuth support

### Ingestion API

Authentication:

* Project environment API key

### Webhook API

Authentication:

* HMAC signature

## 17.2 Important endpoints

### Organizations

* POST /api/v1/organizations
* GET /api/v1/organizations
* GET /api/v1/organizations/{organization_id}
* POST /api/v1/organizations/{organization_id}/invitations
* PATCH /api/v1/organizations/{organization_id}/members/{membership_id}

### Projects

* POST /api/v1/projects
* GET /api/v1/projects
* GET /api/v1/projects/{project_id}
* PATCH /api/v1/projects/{project_id}
* POST /api/v1/projects/{project_id}/environments
* GET /api/v1/projects/{project_id}/environments
* GET /api/v1/environments/{environment_id}
* PATCH /api/v1/environments/{environment_id}

Project creation returns the created project and its automatically created
development environment.

Minimal server-rendered project pages are exposed under:

* GET /projects/
* POST /projects/
* GET /projects/{project_id}/
* POST /projects/{project_id}/
* GET /projects/environments/{environment_id}/

### API keys

* GET /api/v1/environments/{environment_id}/api-keys/
* POST /api/v1/environments/{environment_id}/api-keys/
* POST /api/v1/api-keys/{api_key_id}/revoke/
* POST /api/v1/environments/{environment_id}/auth-check/

### Ingestion

* POST /api/v1/ingest/traces

Future ingestion aliases:

* POST /api/v1/ingest/spans
* POST /api/v1/ingest/otel

### Traces

* GET /api/v1/traces
* GET /api/v1/traces/{trace_id}
* POST /api/v1/traces/{trace_id}/annotations
* POST /api/v1/traces/{trace_id}/dataset-cases

### Datasets

* POST /api/v1/datasets
* GET /api/v1/datasets
* GET /api/v1/datasets/{dataset_id}
* POST /api/v1/datasets/{dataset_id}/cases
* POST /api/v1/datasets/{dataset_id}/publish
* POST /api/v1/datasets/{dataset_id}/imports
* GET /api/v1/dataset-versions/{version_id}/export

### Evaluators

* POST /api/v1/evaluators
* GET /api/v1/evaluators
* POST /api/v1/evaluators/{evaluator_id}/versions
* POST /api/v1/evaluator-versions/{version_id}/validate

### Runs

* POST /api/v1/evaluation-runs
* GET /api/v1/evaluation-runs/{run_id}
* POST /api/v1/evaluation-runs/{run_id}/cancel
* POST /api/v1/evaluation-runs/{run_id}/retry-failures
* GET /api/v1/evaluation-runs/{run_id}/results

### Experiments

* POST /api/v1/experiments
* GET /api/v1/experiments/{experiment_id}
* GET /api/v1/experiments/{experiment_id}/comparison
* POST /api/v1/experiments/{experiment_id}/decide

### CI

* POST /api/v1/ci/evaluations
* GET /api/v1/ci/evaluations/{run_id}/status
* GET /api/v1/ci/evaluations/{run_id}/decision

## 17.3 API conventions

* Version APIs through the URL.
* Use UUID identifiers.
* Use cursor pagination for traces.
* Use page-number pagination for small configuration collections.
* Return machine-readable error codes.
* Include request identifiers.
* Support idempotency keys on creation endpoints.
* Publish an OpenAPI schema.
* Generate SDK models from the canonical schema where practical.

---

# 18. Python SDK

## 18.1 Package name

agentproof-sdk

## 18.2 SDK goals

* Minimal setup
* Framework independence
* Typed public API
* Safe failure behavior
* Batching
* Background export
* Context propagation
* OpenTelemetry compatibility

The Phase 9 implementation uses native AgentProof export as the primary happy
path. Full OpenTelemetry exporter integration remains future compatibility
work.

## 18.3 Public concepts

### AgentProofClient

Responsibilities:

* Configuration
* Authentication
* Export
* Flush
* Shutdown

`AgentProofClient` resolves configuration from explicit constructor arguments,
environment variables, and defaults. It sends batches to
`POST /api/v1/ingest/traces` using `Authorization: Bearer <api-key>`. The SDK
does not send trusted tenant identifiers; organization, project, and
environment scope is derived by the backend from the verified environment API
key.

### Trace context manager

Example conceptual interface:

with client.trace("support-agent") as trace:
trace.set_input(...)
...

### Span context manager

Example conceptual interface:

with trace.span("search-documents", span_type="retrieval") as span:
...

### Decorators

* trace_agent
* trace_model
* trace_tool
* trace_retrieval

### Async equivalents

* Async context managers
* Async flush
* Async transport

The implemented SDK package exports:

* `AgentProofClient`
* `AgentProofConfig`
* `trace_agent`
* `trace_model`
* `trace_tool`
* `trace_retrieval`

Native `agentproof.v1` SDK schemas mirror the backend ingestion envelope:
trace/span IDs, names, status, timestamps, attributes, input/output, error
details, token usage, model/tool metadata, and span events.

## 18.4 Advanced Python concepts

The SDK should deliberately demonstrate:

* Generic result types
* Protocols
* Context variables
* Sync and async context managers
* Decorators preserving signatures
* Background batching
* Thread-safe queues
* Async queues
* Retry policies
* Typed overloads
* Frozen dataclasses
* Structured exceptions
* Resource cleanup
* Plugin registration
* Import-time restraint

## 18.5 SDK failure behavior

Telemetry failure must not crash the customer application by default.

Modes:

* silent
* log
* strict

Strict mode is intended for development and tests.

The default mode is `log`: telemetry failures are logged and user application
execution continues. `silent` swallows telemetry failures. `strict` propagates
configuration, queue, and transport errors for tests and development.

## 18.6 SDK export behavior

The SDK batches completed traces into the existing Phase 7 ingestion request
shape:

```json
{
  "source": "agentproof",
  "schema_version": "agentproof.v1",
  "records": [
    {
      "record_id": "trace-id",
      "payload": {}
    }
  ]
}
```

Export uses a bounded in-memory queue, a background worker for synchronous
clients, retry for transient transport failures, `flush()` / `aflush()`, and
`shutdown()` / `ashutdown()`. SDK batch size is capped to the backend record
limit, and batching also respects the backend 500-span request boundary.

---

# 19. Evaluator architecture

## 19.1 Core protocol

Each evaluator implementation must expose:

* evaluator_type
* configuration_model
* evaluate
* validate_configuration
* version_identifier

## 19.2 Input model

EvaluationContext:

* test_case
* execution
* trace
* application_configuration
* evaluator_configuration

## 19.3 Output model

EvaluationOutcome:

* passed
* score
* explanation
* evidence
* metadata
* cost
* duration
* error

## 19.4 Registry

Evaluators are registered through an explicit registry.

The registry must:

* Reject duplicate evaluator types.
* Validate configuration.
* Resolve implementation by type and version.
* Support future plugin discovery.
* Avoid arbitrary user code execution in the SaaS environment.

## 19.5 Determinism

Every evaluator declares one of:

* Deterministic
* Model-dependent
* External-system-dependent

The UI must expose this classification.

---

# 20. Background task design

## 20.1 Queue separation

ingestion-processing:

* Cost calculation
* Trace aggregation
* Search-field extraction

evaluations:

* Run orchestration
* Case scheduling
* Result aggregation

provider-calls:

* Candidate application requests
* Model-based judges

notifications:

* Email
* Webhook delivery

maintenance:

* Retention
* Cleanup
* Usage aggregation
* Stale-job recovery

## 20.2 Task rules

Every task must:

* Accept primitive serializable arguments.
* Fetch current state from the database.
* Be idempotent.
* Declare retryable exceptions.
* Apply a timeout.
* Log a correlation identifier.
* Record terminal failure.
* Avoid holding a database transaction during network I/O.

## 20.3 Evaluation orchestration

1. Create evaluation run.
2. Commit run and outbox event.
3. Dispatcher publishes prepare-run task.
4. Prepare-run creates case executions.
5. Case jobs are enqueued.
6. Each case calls the target application.
7. Evaluators run.
8. Results are persisted.
9. Progress counters update.
10. Finalizer computes aggregates.
11. Regression policy runs.
12. Notifications are generated.

---

# 21. Security model

## 21.1 Tenant isolation

Every request must establish an organization context.

Rules:

* Never accept organization identifiers from untrusted payloads when they can be derived from authentication.
* Querysets must be scoped before object retrieval.
* Child resources must be validated against their parent organization.
* Celery tasks must receive the organization identifier explicitly.
* Cache keys must contain the organization identifier.
* Object-storage paths must contain non-guessable tenant prefixes.

## 21.2 API key format

Suggested structure:

ap_live_<public_prefix>_<secret>

Only the prefix and secure secret hash are stored.

## 21.3 Encryption

Application-level encryption should protect:

* External provider credentials
* Webhook secrets
* Application target credentials

Encryption keys must come from environment configuration or a managed key service, never the database.

## 21.4 Prompt-injection considerations

Model-based evaluators must treat evaluated content as untrusted data.

Judge prompts must:

* Clearly delimit content.
* Instruct the judge not to follow embedded instructions.
* Require structured output.
* Apply output schema validation.
* Record malformed responses.
* Permit repeated evaluation for consistency analysis.

---

# 22. Testing strategy

## 22.1 Test layers

### Unit tests

Cover:

* Value objects
* Evaluators
* Policy rules
* Redaction
* Cost calculation
* API-key hashing
* Schema normalization

### Model tests

Cover:

* Constraints
* State transitions
* Tenant ownership
* Immutability

### Service tests

Cover:

* Transactions
* Permissions
* Outbox creation
* Idempotency
* Audit events

### API tests

Cover:

* Authentication
* Authorization
* Validation
* Error responses
* Pagination
* Rate limiting

### Worker tests

Cover:

* Retry behavior
* Duplicate delivery
* Cancellation
* Partial failure
* Stale-run recovery

### Integration tests

Use real:

* PostgreSQL
* Redis
* Object storage emulator
* Celery worker

### Contract tests

Cover:

* Provider adapters
* Application target API
* Webhook signatures
* OpenTelemetry mapping

### Property-based tests

Apply to:

* Trace-tree construction
* Redaction invariants
* Policy calculations
* Idempotency
* Dataset serialization
* Cost aggregation

### Load tests

Scenarios:

* Large trace batches
* Trace-list filtering
* Concurrent evaluation runs
* Webhook retry storms

## 22.2 Required coverage

Do not optimize for one theatrical coverage percentage.

Require:

* All policy rules tested.
* All authorization paths tested.
* All state transitions tested.
* All public SDK interfaces tested.
* Every production bug receives a regression test.

---

# 23. Observability

The platform must observe itself.

## 23.1 Logs

Use structured logs containing:

* timestamp
* level
* service
* environment
* request_id
* organization_id
* project_id
* user_id
* trace_id
* evaluation_run_id
* task_id
* event
* duration
* error_type

## 23.2 Metrics

Application:

* HTTP request count
* HTTP latency
* HTTP errors
* Database query duration
* Cache hit ratio

Ingestion:

* Traces accepted
* Traces rejected
* Spans accepted
* Duplicate records
* Processing lag

Workers:

* Queue depth
* Task duration
* Retries
* Failures
* Dead jobs

Evaluations:

* Runs started
* Runs completed
* Case duration
* Evaluator duration
* Provider errors
* Evaluation cost

## 23.3 Tracing

Trace:

* HTTP requests
* Database calls where appropriate
* Celery task flow
* External model-provider requests
* Webhook delivery
* Evaluation orchestration

---

# 24. Product analytics

Track product events such as:

* organization_created
* project_created
* api_key_created
* sdk_setup_viewed
* first_trace_received
* trace_viewed
* dataset_created
* trace_added_to_dataset
* dataset_published
* evaluator_created
* evaluation_started
* evaluation_completed
* experiment_created
* policy_failed
* policy_passed
* webhook_configured

Do not place prompt or response content in product analytics.

---

# 25. Success metrics

## 25.1 Activation

Primary activation event:

The organization receives a trace and publishes its first dataset.

Supporting metrics:

* Time to first API key
* Time to first trace
* Percentage of new organizations receiving a trace
* Percentage creating a dataset
* Percentage running an evaluation

## 25.2 Engagement

* Weekly active projects
* Traces inspected per project
* Test cases added from production traces
* Evaluation runs per week
* Experiments per month

## 25.3 Retention

* Organizations running evaluations in consecutive weeks
* Projects sending production traces after thirty days
* Dataset growth over time

## 25.4 Reliability

* Ingestion acceptance rate
* Evaluation completion rate
* Webhook delivery success
* Duplicate result rate
* Worker recovery rate

## 25.5 Quality

* Regression policies triggered
* Production failures converted to test cases
* Percentage of releases evaluated
* False-positive policy rate reported by users

---

# 26. Key product risks

## 26.1 Storage growth

Risk:

Trace and span data grows rapidly.

Mitigation:

* Configurable retention
* Sampling
* Metadata-only capture
* Object storage for large payloads
* Aggregated usage reports
* Later table partitioning

## 26.2 Model-judge instability

Risk:

Model-based scores vary.

Mitigation:

* Store judge model and configuration.
* Require structured responses.
* Support repeated judgments.
* Prefer deterministic evaluators where possible.
* Show example-level evidence.

## 26.3 Evaluation cost

Risk:

Large datasets and model judges become expensive.

Mitigation:

* Estimate cost before execution.
* Add run budgets.
* Cache safe evaluator results by content hash.
* Limit concurrency.
* Allow deterministic-only runs.

## 26.4 Sensitive data

Risk:

Prompts and responses contain customer or personal information.

Mitigation:

* Metadata-only mode
* Redaction
* Retention controls
* Encryption
* Access audit
* Explicit capture configuration

## 26.5 Overengineering

Risk:

Building infrastructure nobody uses.

Mitigation:

The MVP must prioritize one demonstrable workflow:

production trace → dataset case → experiment → release decision.

Anything not serving this workflow remains secondary.

---

# 27. MVP completion criteria

The MVP is complete when the following demonstration works:

1. A sample support agent is instrumented with the Python SDK.
2. Ten executions are sent to AgentProof.
3. The web UI displays their trace trees.
4. A failed execution is added to a dataset.
5. The dataset is published.
6. A baseline prompt and candidate prompt are configured.
7. An experiment runs against both versions.
8. Exact-match, required-tool, latency, and rubric evaluators execute.
9. The comparison page displays quality, latency, and cost differences.
10. A regression policy rejects the candidate.
11. A CI endpoint returns a failed decision.
12. The audit log explains who created the dataset, started the run, and applied the policy.
13. The entire system runs locally through documented commands.
14. The deployed demonstration is reproducible from a clean environment.

---

# 28. Marketing deliverables

The public project should include:

* Product landing page
* Public documentation
* Architecture diagram
* Five-minute demo video
* Sample agent repository
* Python SDK package
* OpenAPI specification
* Performance benchmark
* Security design document
* Engineering decision records
* Screenshots of trace, experiment, and policy views
* Public roadmap
* Changelog

## Suggested portfolio description

AgentProof is a multi-tenant AI reliability platform built with Django and Python. It ingests OpenTelemetry-compatible
agent traces, executes distributed evaluation pipelines, compares model and prompt versions, detects regressions, and
enforces CI release policies. The system uses PostgreSQL, Redis, Celery, typed provider adapters, transactional outbox
processing, idempotent background jobs, and a separately published Python instrumentation SDK.

## Suggested demonstration title

How I built a release-quality system for probabilistic AI applications.
