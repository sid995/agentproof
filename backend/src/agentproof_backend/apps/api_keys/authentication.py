"""DRF authentication for AgentProof api keys"""

from dataclasses import dataclass

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.api_keys.exceptions import APIKeyAuthenticationFailed
from agentproof_backend.apps.api_keys.models import APIKeyScope
from agentproof_backend.apps.api_keys.services import VerifiedAPIKey, verify_api_key
from agentproof_backend.apps.api_keys.tasks import update_api_key_last_used


@dataclass(frozen=True, slots=True)
class APIKeyCredentials:
    """Typed request.auth payload for API-key-authenticated views"""

    verified: VerifiedAPIKey


class EnvironmentAPIKeyAuthentication(BaseAuthentication):
    """Authenticate `Authorization: Bearer <api_key>` requests"""

    required_scope = APIKeyScope.TRACES_WRITE

    def authenticate(self, request: Request) -> tuple[User, APIKeyCredentials] | None:
        raw_header = get_authorization_header(request).decode("utf-8")

        if not raw_header:
            return None

        scheme, _, token = raw_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None

        environment_id = (
            request.parser_context.get("kwargs", {}).get("environment_id") if request.parser_context else None
        )

        try:
            verified = verify_api_key(
                plaintext=token,
                required_scope=self.required_scope,
                environment_id=environment_id,
            )
        except APIKeyAuthenticationFailed as exc:
            raise AuthenticationFailed(str(exc)) from exc

        update_api_key_last_used.delay(str(verified.api_key.id))

        return verified.api_key.created_by, APIKeyCredentials(verified=verified)
