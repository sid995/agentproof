"""SDK configuration tests."""

import pytest

from agentproof import AgentProofConfig
from agentproof.exceptions import AgentProofConfigError


def test_config_prefers_explicit_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTPROOF_API_KEY", "env-key")
    monkeypatch.setenv("AGENTPROOF_ENDPOINT", "https://env.example")

    config = AgentProofConfig.from_sources(
        api_key="explicit-key",  # pragma: allowlist secret
        endpoint="https://explicit.example/",
        batch_size=10,
        error_mode="strict",
    )

    assert config.api_key == "explicit-key"  # pragma: allowlist secret
    assert config.endpoint == "https://explicit.example"
    assert config.batch_size == 10
    assert config.error_mode == "strict"
    assert config.ingest_url == "https://explicit.example/api/v1/ingest/traces"


def test_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTPROOF_API_KEY", "env-key")
    monkeypatch.setenv("AGENTPROOF_ENDPOINT", "https://env.example")
    monkeypatch.setenv("AGENTPROOF_BATCH_SIZE", "7")
    monkeypatch.setenv("AGENTPROOF_ERROR_MODE", "silent")

    config = AgentProofConfig.from_sources()

    assert config.api_key == "env-key"  # pragma: allowlist secret
    assert config.endpoint == "https://env.example"
    assert config.batch_size == 7
    assert config.error_mode == "silent"


def test_config_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTPROOF_API_KEY", raising=False)

    with pytest.raises(AgentProofConfigError, match="api_key is required"):
        AgentProofConfig.from_sources()


def test_config_rejects_unsupported_batch_size() -> None:
    with pytest.raises(AgentProofConfigError, match="batch_size"):
        AgentProofConfig.from_sources(api_key="key", batch_size=101)  # pragma: allowlist secret
