"""Project domain exceptions."""


class ProjectError(Exception):
    """Base error for project operations."""

    code = "project_error"


class ProjectConflict(ProjectError):
    """Raised when project data conflicts with existing data."""

    code = "project_conflict"


class ProjectNotFound(ProjectError):
    """Raised when a tenant-scoped project does not exist."""

    code = "project_not_found"


class EnvironmentConflict(ProjectError):
    """Raised when environment data conflicts with existing data."""

    code = "environment_conflict"


class EnvironmentNotFound(ProjectError):
    """Raised when a tenant-scoped environment does not exist."""

    code = "environment_not_found"


class ProjectPermissionDenied(ProjectError):
    """Raised when the actor lacks a required organization role."""

    code = "project_permission_denied"


class ProjectInactive(ProjectError):
    """Raised when an operation requires an active project."""

    code = "project_inactive"


class EnvironmentInactive(ProjectError):
    """Raised when an operation requires an active environment."""

    code = "environment_inactive"


class InvalidProjectConfiguration(ProjectError):
    """Raised when project configuration is invalid."""

    code = "invalid_project_configuration"


class InvalidEnvironmentConfiguration(ProjectError):
    """Raised when environment configuration is invalid."""

    code = "invalid_environment_configuration"
