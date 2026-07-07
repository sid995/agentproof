"""Telemetry domain exceptions"""


class TelemetryError(Exception):
    """Base error for telemetry domain operations"""

    code = "telemetry_error"


class TelemetryValidationError(TelemetryError):
    """Raised when canonical telemetry is structurally invalid."""

    code = "telemetry_validation_error"


class TelemetryPersistenceError(TelemetryError):
    """Raised when telemetry cannot be persisted safely."""

    code = "telemetry_persistence_error"


class UnsupportedTelemetryPayload(TelemetryError):
    """Raised when no normalizer supports a telemetry payload."""

    code = "unsupported_telemetry_payload"


class TraceNotFound(TelemetryError):
    """Raised when a tenant-scoped trace does not exist."""

    code = "trace_not_found"
