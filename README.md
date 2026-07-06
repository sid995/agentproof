# Agentproof

## Django development

### Copy the environment template:

```bash
cp .env.example .env
```

### Start PostgresSQL and Redis

```bash
make infra-up
```

### Apply migrations:

```bash
make migrate
```

### Create a superuser:

```bash
make superuser
```

### Start the ASGI development server:

```bash
make server-asgi
```

### Application endpoints:

- Django admin: http://127.0.0.1:8000/admin/
- Swagger UI: http://127.0.0.1:8000/api/docs/
- OpenAPI schema: http://127.0.0.1:8000/api/schema/
- Liveness: http://127.0.0.1:8000/health/live/
- Readiness: http://127.0.0.1:8000/health/ready/

## Organizations and tenancy

AgentProof uses organization-based multi-tenancy.

Authenticated sessions maintain one active organization. Tenant endpoints
validate the active organization, membership status, role, and URL tenant
identifier.

Organization roles:

- Owner
- Administrator
- Developer
- Viewer

Main endpoints:

- `GET /api/v1/organizations/`
- `POST /api/v1/organizations/`
- `GET /api/v1/organizations/current/`
- `POST /api/v1/organizations/{id}/switch/`
- `GET /api/v1/organizations/{id}/members/`
- `POST /api/v1/organizations/{id}/invitations/`
- `POST /api/v1/invitations/accept/`

Invitation emails are printed to the console in local development.

## Projects and environments

Projects and environments are scoped to the active organization.

The project hierarchy is the ownership boundary that API keys, telemetry,
datasets, evaluations, and policies attach to.

Project behavior:

- Owners and administrators create and update projects.
- Each project belongs to the active organization.
- Each project has a stable slug, lifecycle status, default capture mode,
  default retention period, and creator.
- Creating a project also creates a default development environment.

Environment behavior:

- Owners, administrators, and developers create and update environments.
- Each environment belongs to one project and stores the organization directly
  for tenant scoping.
- Environment types are development, staging, production, and custom.
- Environment capture and retention settings may override the project defaults.
- Viewers have read-only access.

Main endpoints:

- `GET /api/v1/projects/`
- `POST /api/v1/projects/`
- `GET /api/v1/projects/{id}/`
- `PATCH /api/v1/projects/{id}/`
- `GET /api/v1/projects/{id}/environments/`
- `POST /api/v1/projects/{id}/environments/`
- `GET /api/v1/environments/{id}/`
- `PATCH /api/v1/environments/{id}/`

Minimal server-rendered project pages are available under `/projects/`.

Validation status: Phase 4 passes `make schema` and `make check`.

## API keys

API keys are scoped to one environment and authenticate SDK or ingestion-style
requests without reusing browser sessions.

API key behavior:

- Owners, administrators, and developers create and revoke keys.
- Viewers can list key metadata but cannot create or revoke keys.
- Key values use the `ap_live_<prefix>_<secret>` format.
- The plaintext key is returned only once when the key is created.
- Only the public prefix and a secure hash are stored.
- Revoked, expired, wrong-environment, and wrong-scope keys are rejected.
- `last_used_at` is updated outside the authentication critical path.

Main endpoints:

- `GET /api/v1/environments/{id}/api-keys/`
- `POST /api/v1/environments/{id}/api-keys/`
- `POST /api/v1/api-keys/{id}/revoke/`
- `POST /api/v1/environments/{id}/auth-check/`

Validation status: Phase 5 API-key management and authentication checks are
covered by `backend/tests/test_api_keys.py`; refresh `make schema` after API
changes and run `make check` before marking the phase complete.

## Telemetry domain

Telemetry is stored in a canonical internal model before any public ingestion
endpoint accepts provider-specific payloads.

Phase 6 adds:

- `Trace`, `Span`, `SpanEvent`, and `TraceAnnotation` database models.
- Native AgentProof Pydantic envelopes for trace and span payloads.
- A normalizer interface with native AgentProof and OpenTelemetry-style
  adapters.
- Trace-tree validation for duplicate spans, missing parents, cycles, invalid
  timestamps, child timing, and root-span detection.
- A service that validates and persists canonical traces without exposing an
  HTTP endpoint.

Validation status: Phase 6 passes `make check`. Public ingestion endpoints are
part of Phase 7.
