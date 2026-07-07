"""Structured exceptions raised by the AgentProof SDK."""


class AgentProofError(Exception):
    """Base class for SDK errors."""


class AgentProofConfigError(AgentProofError):
    """Raised when SDK configuration is invalid."""


class AgentProofTransportError(AgentProofError):
    """Raised when telemetry export fails."""


class AgentProofQueueFullError(AgentProofError):
    """Raised in strict mode when telemetry cannot be queued."""
