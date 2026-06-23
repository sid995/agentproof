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
