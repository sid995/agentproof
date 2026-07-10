# Contributing to AgentProof

First off, thank you for taking the time to contribute to AgentProof! We welcome and deeply appreciate community contributions. By contributing, you help us maximize the utility, efficiency, and reliability of AgentProof for everyone.

To ensure a smooth, high-quality development experience, please follow the guidelines below.

---

## Code of Conduct

We are committed to providing a welcoming, inclusive, and professional environment for all contributors. Please treat others with respect and constructive professionalism in all interactions.

Do not report security vulnerabilities through public issues. Refer to [SECURITY.md](SECURITY.md) for instructions on reporting security concerns.

---

## Development Setup

AgentProof leverages **`uv`** as its Python package and environment manager, and **Docker** for running local infrastructure (Postgres and Redis).

### Prerequisites

- **Python 3.12** or higher
- **`uv`** (fast Python package installer and resolver)
- **Docker** and **Docker Compose**

### Step-by-Step Installation

1. **Fork and Clone the Repository**
   ```bash
   git clone https://github.com/<your-username>/AgentProof.git
   cd AgentProof
   ```

2. **Configure Environment Variables**
   Copy the example environment template to create your local `.env` configuration:
   ```bash
   cp .env.example .env
   ```

3. **Install Dependencies and Pre-commit Hooks**
   The canonical `make install` command installs project dependencies across all packages and sets up pre-commit hooks to automate formatting and linting gates:
   ```bash
   make install
   ```

4. **Start Local Infrastructure**
   Launch Postgres and Redis in the background using Docker Compose:
   ```bash
   make infra-up
   ```

5. **Apply Database Migrations**
   Initialize or update the Django database schema:
   ```bash
   make migrate
   ```

6. **Create a Superuser (Optional)**
   If you need access to the Django admin panel:
   ```bash
   make superuser
   ```

7. **Start the Development Server**
   To start the ASGI development server with live reload:
   ```bash
   make server-asgi
   ```
   Or run the WSGI development server:
   ```bash
   make server
   ```

---

## Repository Map

Understanding the layout of our project is key to high-confidence contributions:

- `backend/src/agentproof_backend/`: Django backend codebase. Follows clean patterns of models, selectors, services, APIs, and permissions.
- `backend/tests/`: Django unit and integration tests using pytest.
- `packages/python-sdk/src/agentproof/`: Python SDK source code.
- `packages/python-sdk/tests/`: SDK unit and integration tests.
- `docs/plan/`: Product development tracker and phase definitions.
- `docs/architecture/`: Core system design records and concepts.
- `docs/api/openapi.yml`: Generated OpenAPI schema.
- `Makefile`: Unified build and automation commands.

---

## Commands and Quality Gates

We use standard commands via `Makefile` to run local checks. Always verify that your changes pass these checks before raising a pull request.

- **Full Validation Gate** (runs format, lint, type-check, migrations-check, and tests):
  ```bash
  make check
  ```
- **Code Formatting** (automatically formats python files using Ruff):
  ```bash
  make format
  ```
- **Linter Only**:
  ```bash
  make lint
  ```
- **Type Checking Only** (checks types using mypy):
  ```bash
  make type-check
  ```
- **Django System Checks**:
  ```bash
  make django-check
  ```
- **Migration Drift Check** (fails if there are uncreated migrations):
  ```bash
  make migrations-check
  ```
- **Run the Pytest Suite**:
  ```bash
  make test
  ```

### Fast Test Feedback
To iterate quickly, you can run focused tests using pytest:
```bash
# Run backend telemetry tests
uv run pytest backend/tests/test_telemetry.py -q

# Run backend API keys tests
uv run pytest backend/tests/test_api_keys.py -q

# Run python SDK tests
uv run pytest packages/python-sdk/tests -q
```

---

## Engineering Standards

To keep AgentProof robust and maintainable, we enforce the following engineering standards:

1. **Backend as Source of Truth**:
   The backend must authenticate and authorize all actions, scope tenants, and manage state transitions. Do not trust client-provided tenant or scope info when the server can derive it.
2. **Deterministic Migrations**:
   Never check in migrations that depend on dynamic states or have non-deterministic order. Run `make migrations-check` to verify database sanity.
3. **Write Logic in Services; Read Logic in Selectors**:
   Keep Django serializers and views thin. Place write behavior in service functions, and complex read/query logic in selectors.
4. **No Plaintext Secrets**:
   Never log or commit raw secrets, tokens, passwords, or API keys. Plaintext keys must only be shown once on creation.
5. **Secure by Default**:
   Fail closed on authentication and authorization paths. Return explicit, structured domain exceptions instead of exposing database-level details.

---

## Testing Standard

We aim for high test coverage that proves behavior, not just happy paths.

- **Always Add Tests**: Every code or logic change must be accompanied by new or updated unit/integration tests.
- **Tenant Isolation**: Cover boundary checks, permission rules, and multi-tenant access controls.
- **Error Handlers & Constraints**: Test invalid inputs, duplicate records, idempotency constraints, and persistence edge cases.
- **API and Schema**: If public endpoints are modified, regenerate the OpenAPI schema:
  ```bash
  make schema
  ```

---

## Pull Request Guidelines

1. **Keep Pull Requests Scoped**: Focus on a single bug or feature. Do not bundle unrelated changes.
2. **Branch Naming**: Use a prefix such as `feature/` or `bugfix/` followed by a concise description (e.g., `bugfix/telemetry-reconnect`).
3. **Commit Messages**: Write imperative, concise git commit messages (e.g., `Add validation for organization role transitions`).
4. **Pass all checks**: Ensure `make check` passes successfully on your machine.
5. **Update Documentation**: If your PR changes behavior, models, or APIs, ensure corresponding updates are made in the `docs/` folder (such as the OpenAPI schema or development logs).

---

## Licensing

By contributing to AgentProof, you agree that your contributions will be licensed under the project's [Apache 2.0 License](LICENSE).
