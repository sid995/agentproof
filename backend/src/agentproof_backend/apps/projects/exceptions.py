"""Project domain exceptions."""


class ProjectError(Exception):
    """Base project exception."""

    code = "project_error"


class ProjectPermissionDenied(ProjectError):
    """Raised when an actor cannot perform a project action."""

    code = "project_permission_denied"


class ProjectNotFound(ProjectError):
    """Raised when a scoped project lookup fails."""

    code = "project_not_found"


class EnvironmentNotFound(ProjectError):
    """Raised when a scoped environment lookup fails."""

    code = "environment_not_found"


class ProjectConflict(ProjectError):
    """Raised for uniqueness conflicts."""

    code = "project_conflict"
