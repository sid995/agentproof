"""OpenAPI schema helpers for API key authentication"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema

from agentproof_backend.apps.common.type_utils import allow_runtime_generic

allow_runtime_generic(OpenApiAuthenticationExtension)


class EnvironmentAPIKeyAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    """Document AgentProof environment API keys as bearer token"""

    target_class = "agentproof_backend.apps.api_keys.authentication.EnvironmentAPIKeyAuthentication"
    name = "EnvironmentAPIKeyAuth"

    def get_security_definition(self, _auto_schema: AutoSchema) -> dict[str, str]:
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "AgentProof API key",
        }
