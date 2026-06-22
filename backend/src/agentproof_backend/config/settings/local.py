"""Local-development Django settings."""

from .base import *

DEBUG = True

ALLOWED_HOSTS = [
    *ALLOWED_HOSTS,
    "testserver",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}
