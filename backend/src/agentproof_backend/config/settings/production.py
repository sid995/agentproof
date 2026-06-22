"""Production Django settings."""

from django.core.exceptions import ImproperlyConfigured

from agentproof_backend.config.env import DEFAULT_LOCAL_SECRET

from .base import *

if ENV.environment != "production":
    raise ImproperlyConfigured("AGENTPROOF_ENVIRONMENT must be set to 'production'.")

if SECRET_KEY == DEFAULT_LOCAL_SECRET:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be explicitly configured in production.")

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must contain at least one hostname.")

DEBUG = False

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

USE_X_FORWARDED_HOST = True

STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
}

if ENV.object_storage_backend == "s3":
    if not ENV.aws_storage_bucket_name:
        raise ImproperlyConfigured("AWS_STORAGE_BUCKET_NAME is required when OBJECT_STORAGE_BACKEND=s3.")

    access_key = ENV.aws_access_key_id.get_secret_value() if ENV.aws_access_key_id else None
    secret_key = ENV.aws_secret_access_key.get_secret_value() if ENV.aws_secret_access_key else None

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": access_key,
            "secret_key": secret_key,
            "bucket_name": ENV.aws_storage_bucket_name,
            "region_name": ENV.aws_s3_region_name,
            "endpoint_url": ENV.aws_s3_endpoint_url,
            "default_acl": None,
            "file_overwrite": False,
            "querystring_auth": True,
        },
    }
