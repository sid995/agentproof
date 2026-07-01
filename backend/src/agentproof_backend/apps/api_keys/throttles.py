"""API key throttling"""

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle

from agentproof_backend.apps.api_keys.authentication import APIKeyCredentials


class APIKeyRateThrottle(SimpleRateThrottle):
    """Throttle SDK/ingestion class per API key prefix"""

    scope = "api_key"

    def get_cache_key(self, request: Request, _view: object) -> str | None:
        auth = request.auth

        if not isinstance(auth, APIKeyCredentials):
            return None

        return self.cache_format % {"scope": self.scope, "ident": auth.verified.api_key.prefix}
