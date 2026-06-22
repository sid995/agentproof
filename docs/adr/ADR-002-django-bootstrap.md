# ADR-002: Django application bootstrap

## Status

Accepted

## Context

AgentProof requires:

- Browser authentication
- Administrative interfaces
- Multi-tenant relational models
- Public and internal APIs
- Background workflows
- Strong security defaults
- ASGI support

## Decision

Use Django as the primary application framework.

The application will use:

- A custom email-based user model
- Split local, test, and production settings
- Pydantic Settings for runtime configuration validation
- Django REST Framework for APIs
- drf-spectacular for OpenAPI generation
- PostgreSQL as the production database
- Redis for cache and background-work coordination
- ASGI as the primary web-server interface
- Structlog for structured logging
- WhiteNoise for static files
- Django storage backends for uploaded artifacts

## Consequences

Positive:

- Authentication and admin capabilities are available early.
- Django security defaults remain enabled.
- API documentation is generated from source code.
- Environment-specific configuration is explicit.
- The custom user model exists before initial migrations.

Negative:

- Some synchronous Django components require careful use under ASGI.
- Settings and framework integrations increase initial configuration.
- PostgreSQL-specific behaviour still requires integration tests.
