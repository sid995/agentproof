"""Dataset domain exceptions."""


class DatasetError(Exception):
    """Base error for dataset operations."""

    code = "dataset_error"


class DatasetConflict(DatasetError):
    """Raised when dataset data conflicts with existing data."""

    code = "dataset_conflict"


class DatasetNotFound(DatasetError):
    """Raised when a tenant-scoped dataset does not exist."""

    code = "dataset_not_found"


class DatasetDraftNotFound(DatasetError):
    """Raised when a mutable dataset draft does not exist."""

    code = "dataset_draft_not_found"


class DatasetCaseNotFound(DatasetError):
    """Raised when a draft case does not exist."""

    code = "dataset_case_not_found"


class DatasetVersionNotFound(DatasetError):
    """Raised when a published dataset version does not exist."""

    code = "dataset_version_not_found"


class DatasetImportJobNotFound(DatasetError):
    """Raised when a dataset import job does not exist."""

    code = "dataset_import_job_not_found"


class DatasetPermissionDenied(DatasetError):
    """Raised when the actor lacks a required organization role."""

    code = "dataset_permission_denied"


class DatasetImmutable(DatasetError):
    """Raised when immutable dataset content is changed."""

    code = "dataset_immutable"


class DatasetValidationError(DatasetError):
    """Raised when dataset content fails validation."""

    code = "dataset_validation_error"
