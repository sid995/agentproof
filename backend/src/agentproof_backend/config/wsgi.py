"""WSGI application for AgentProof"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "agentproof_backend.config.settings.local",
)

application = get_wsgi_application()
