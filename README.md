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
