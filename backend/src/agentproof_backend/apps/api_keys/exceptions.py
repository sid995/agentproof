"""API key domain exceptions."""


class APIKeyError(Exception):
    """Base error for API key operations."""

    code = "api_key_error"


class APIKeyNotFound(APIKeyError):
    code = "api_key_not_found"


class APIKeyPermissionDenied(APIKeyError):
    code = "api_key_permission_denied"


class APIKeyConflict(APIKeyError):
    code = "api_key_conflict"


class InvalidAPIKeyConfiguration(APIKeyError):
    code = "invalid_api_key_configuration"


class APIKeyAuthenticationFailed(APIKeyError):
    code = "api_key_authentication_failed"
