# ADR-009: Versioned datasets and async JSONL imports

## Status

Accepted.

## Context

AgentProof needs to convert production traces into durable regression cases.
Those cases must be editable while being prepared, but evaluation runs need to
reference immutable dataset snapshots so historical results remain explainable.
Phase 11 also requires JSONL import/export so teams can move cases in and out
of AgentProof without a public dataset API.

## Decision

Implement versioned datasets as a dedicated Django `datasets` app.

* `Dataset` is the tenant/project-scoped container.
* `DatasetDraft` is the only mutable working copy. A partial database
  constraint allows at most one open draft per dataset.
* `DatasetDraftCase` stores editable cases and optional source trace links.
* `DatasetVersion` and `DatasetVersionCase` are immutable published snapshots.
  Application-level model and queryset guards reject updates and deletes.
* Publishing validates schemas and cases, snapshots draft content, assigns the
  next version number, and computes a deterministic SHA-256 content hash from
  canonical JSON.
* JSONL imports use Django `default_storage` for temporary files and Celery for
  row-by-row processing. Valid rows create draft cases; invalid rows are
  accumulated on the import job for UI display.
* Published versions export stable JSONL in version-case order.

## Consequences

* Evaluation runs can safely reference published versions without being affected
  by later draft edits.
* Users can continue editing by cloning a version into a new draft.
* The system rejects duplicate published content for the same dataset.
* JSONL imports are operationally asynchronous and require worker execution for
  production use; tests run tasks eagerly.
* Public dataset APIs remain future work.
