"""Phase 1 SDK smoke tests."""

import agentproof


def test_sdk_package_imports() -> None:
    """The SDK should expose its package version."""
    assert agentproof.__version__ == "0.1.0"
