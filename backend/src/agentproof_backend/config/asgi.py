"""ASGI application for AgentProof"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "agentproof_backend.config.settings.local",
)

application = get_asgi_application()
