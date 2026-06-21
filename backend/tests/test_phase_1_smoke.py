"""Phase 1 backend smoke tests."""

import agentproof_backend


def test_backend_package_imports() -> None:
    """The backend package should be installed by the workspace."""
    assert agentproof_backend.__version__ == "0.1.0"
