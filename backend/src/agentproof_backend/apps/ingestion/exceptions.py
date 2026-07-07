"""Ingestion domain exceptions."""


class IngestionError(Exception):
    """Base error for ingestion operations."""

    code = "ingestion_error"


class BatchEnvelopeInvalid(IngestionError):
    """Raised when the outer batch envelope is malformed or unsupported."""

    code = "batch_envelope_invalid"


class BatchLimitExceeded(IngestionError):
    """Raised when the batch exceeds record or span limits."""

    code = "batch_limit_exceeded"
