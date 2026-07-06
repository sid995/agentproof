"""Phase 1 SDK smoke tests."""

import agentproof


def test_sdk_package_imports() -> None:
    """The SDK should expose its package version."""
    assert agentproof.__version__ == "0.1.0"


def test_sdk_exports_version_string() -> None:
    """The SDK package should expose a stable string version."""
    assert isinstance(agentproof.__version__, str)
    assert agentproof.__version__
