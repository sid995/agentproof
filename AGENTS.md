# AGENTS.md

## Purpose

This file is the always-on operating guide for Codex and other coding agents in
this repository. Use it to make routine development predictable: read the
current code first, make minimal high-confidence changes, validate with the
repo gates, and keep the phase documentation current.

User instructions in the active chat override this file. More specific
`AGENTS.md` files in subdirectories override this root guidance for that
subtree.

## Project Map

- `backend/src/agentproof_backend/`: Django backend source.
- `backend/src/agentproof_backend/apps/`: domain apps. Existing apps follow the
  pattern of models, selectors, services, APIs, permissions, admin, exceptions,
  and tests where relevant.
- `backend/tests/`: backend pytest suite.
- `packages/python-sdk/src/agentproof/`: Python SDK package.
- `packages/python-sdk/tests/`: SDK tests.
- `docs/plan/Product-development.md`: phase tracker and definition of done.
- `docs/architecture/README.md`: architecture and product-system details.
- `docs/adr/`: architecture decision records.
- `docs/api/openapi.yml`: generated OpenAPI schema.
- `Makefile`: canonical local commands.

## Default Workflow

1. Start by checking the current branch and worktree:
   `git status --short`.
2. Read the files that own the requested behavior before proposing or editing.
   Prefer `rg` and focused file reads over broad scans.
3. Verify whether the reported issue still exists in current code. Fix only
   still-valid issues and state why skipped findings are no longer valid.
4. Keep changes scoped to the requested phase or bug. Do not pull future-phase
   work forward unless the user explicitly asks for it.
5. Preserve user work. Never revert, overwrite, or clean up unrelated changes
   without explicit instruction.
6. Before editing, identify the smallest set of files needed. After editing,
   review the diff for correctness, tenant boundaries, migrations, tests, and
   documentation impact.

## Commands

Use the repository commands instead of inventing ad hoc equivalents.

- Install dependencies: `make install`
- Start local infrastructure: `make infra-up`
- Apply migrations: `make migrate`
- Run development ASGI server: `make server-asgi`
- Generate/update OpenAPI schema: `UV_CACHE_DIR=.uv-cache make schema`
- Full validation gate: `UV_CACHE_DIR=.uv-cache make check`
- Format Python: `UV_CACHE_DIR=.uv-cache make format`
- Lint only: `UV_CACHE_DIR=.uv-cache make lint`
- Type-check only: `UV_CACHE_DIR=.uv-cache make type-check`
- Django system checks: `UV_CACHE_DIR=.uv-cache make django-check`
- Migration drift check: `UV_CACHE_DIR=.uv-cache make migrations-check`
- Full pytest suite: `UV_CACHE_DIR=.uv-cache make test`

The `.uv-cache` override is intentional in this environment; it avoids failures
from unwritable global `uv` cache directories.

For fast feedback, run focused tests first, then the full gate before declaring
work done. Examples:

- Telemetry: `UV_CACHE_DIR=.uv-cache uv run pytest backend/tests/test_telemetry.py -q`
- API keys: `UV_CACHE_DIR=.uv-cache uv run pytest backend/tests/test_api_keys.py -q`
- SDK: `UV_CACHE_DIR=.uv-cache uv run pytest packages/python-sdk/tests -q`

If a check cannot be run, report the exact command and reason.

## Engineering Standards

- Treat the backend as the source of truth for authorization, tenant scoping,
  and state transitions. Do not trust client-supplied organization, project,
  environment, or user scope when the server can derive it.
- Keep tenant-owned data scoped through the established organization, project,
  and environment relationships. Validate cross-tenant writes in models,
  services, permissions, and admin paths where applicable.
- Put write behavior in service functions. Put read/query behavior in selectors
  when a domain already uses selectors. Keep serializers and views thin.
- Use database constraints for invariants that must survive direct ORM/admin
  writes, not only request-level validation.
- Keep migrations deterministic and review migration files before running tests.
  `make migrations-check` must pass unless the task is explicitly to create a
  migration.
- Use Pydantic or structured parsers at external data boundaries. Avoid ad hoc
  string parsing when the standard library, Django, DRF, or Pydantic can express
  the contract clearly.
- Fail closed for security-sensitive paths. Return explicit domain exceptions
  and API errors instead of leaking lower-level implementation details.
- Do not log plaintext secrets, API key material, tokens, passwords, or raw
  credentials. API key plaintext should remain one-time display only.
- Add audit events for security-relevant or tenant-relevant state changes when
  the surrounding domain has audit behavior.

## Testing Standard

Tests should prove the contract, not just the happy path.

- Add or update tests for every behavior change unless the change is purely
  documentation.
- Cover permission boundaries, tenant isolation, invalid input, duplicate or
  idempotency cases, and persistence failures when those are part of the risk.
- For Django model changes, test both the service/API path and direct ORM/admin
  invariant where the model promises protection.
- For normalizers/parsers, include malformed payloads and real provider-shaped
  payloads when supported.
- For API changes, update or verify OpenAPI output with
  `UV_CACHE_DIR=.uv-cache make schema`.
- For phase work, the minimum completion gate is
  `UV_CACHE_DIR=.uv-cache make check`.

## Documentation And Phase Close

Before marking any phase or feature complete, review documentation impact and
update all relevant docs in the same change:

- `docs/plan/Product-development.md`: status, implemented surface, remaining
  boundary, and validation evidence.
- `docs/architecture/README.md`: models, service boundaries, security rules,
  ingestion behavior, API contracts, or operational assumptions.
- `docs/adr/`: add or revise ADRs when a phase introduces, completes, or
  changes an architectural decision.
- `docs/api/openapi.yml`: regenerate when public API behavior changes.
- Root or package READMEs: setup, usage, endpoint, or validation changes.

If a document is reviewed and does not need changes, say so in the final
summary. Documentation-only edits still need a sanity check; run the full gate
when feasible.

## Review Mode

When asked to review, lead with findings ordered by severity. Each finding
should include a file and line reference, the bug or risk, and the concrete
impact. Keep summaries secondary. If there are no findings, say so and mention
any unrun tests or residual risk.

## Git Safety

- Do not run destructive commands such as `git reset --hard`, `git checkout --`,
  or broad cleanups unless the user explicitly requests them.
- Do not stage, commit, push, or open a pull request unless the user asks.
- Do not use `git add .`; if staging is requested, stage intentional file
  groups.
- Leave unrelated dirty worktree changes alone.

## Quality Bar

Done means the code is understandable, typed, tested, documented where needed,
and validated with the correct command. Prefer one boring, well-proven change
over a broad refactor. If the correct fix requires a larger design change, say
that plainly before expanding the scope.
