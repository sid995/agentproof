"""Phase 1 backend smoke tests."""

import agentproof_backend
from agentproof_backend.config.settings import base


def test_backend_package_imports() -> None:
    """The backend package should be installed by the workspace."""
    assert agentproof_backend.__version__ == "0.1.0"


def test_backend_settings_include_expected_core_apps() -> None:
    """Core app wiring should survive packaging and settings refactors."""
    assert "agentproof_backend.apps.accounts.apps.AccountsConfig" in base.INSTALLED_APPS
    assert "agentproof_backend.apps.organizations.apps.OrganizationsConfig" in base.INSTALLED_APPS
    assert "agentproof_backend.apps.projects.apps.ProjectsConfig" in base.INSTALLED_APPS
    assert "agentproof_backend.apps.telemetry.apps.TelemetryConfig" in base.INSTALLED_APPS
