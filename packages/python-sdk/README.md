# AgentProof Python SDK

`agentproof-sdk` instruments Python applications and sends native
`agentproof.v1` trace batches to AgentProof ingestion.

## Quickstart

```bash
export AGENTPROOF_API_KEY=ap_live_...
```

```python
from agentproof import AgentProofClient

client = AgentProofClient(endpoint="http://127.0.0.1:8000")
with client.trace("support-agent") as trace:
    with trace.span("search-documents", span_type="retrieval"):
        run_work()
client.shutdown()
```

The SDK posts to `POST /api/v1/ingest/traces` using bearer API-key
authentication. Server-side organization, project, and environment scope is
derived from the environment API key.

## Configuration

Configuration precedence is explicit constructor arguments, environment
variables, then defaults.

- `AGENTPROOF_API_KEY`
- `AGENTPROOF_ENDPOINT`
- `AGENTPROOF_TIMEOUT_SECONDS`
- `AGENTPROOF_BATCH_SIZE`
- `AGENTPROOF_FLUSH_INTERVAL_SECONDS`
- `AGENTPROOF_CAPTURE_MODE`
- `AGENTPROOF_ERROR_MODE`

`error_mode` supports:

- `log`, the default: log telemetry failures and keep user code running.
- `silent`: swallow telemetry failures.
- `strict`: raise telemetry failures, intended for tests and development.

## Public API

- `AgentProofClient`
- `AgentProofConfig`
- `trace_agent`
- `trace_model`
- `trace_tool`
- `trace_retrieval`

The SDK supports sync and async trace/span context managers, context propagation
with `contextvars`, background batching, retry, `flush()` / `async_flush()`, and
`shutdown()` / `async_shutdown()`.

## Local validation

```bash
UV_CACHE_DIR=.uv-cache uv run pytest packages/python-sdk/tests -q
UV_CACHE_DIR=.uv-cache make build-sdk
UV_CACHE_DIR=.uv-cache make check
```
