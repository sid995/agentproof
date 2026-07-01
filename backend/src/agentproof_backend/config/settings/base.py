"""Base Django settings shared by all environments."""

from pathlib import Path
from typing import Any

import dj_database_url

from agentproof_backend.config.env import get_runtime_settings
from agentproof_backend.config.logging import build_logging_config

ENV = get_runtime_settings()

SETTINGS_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = Path(__file__).resolve().parents[2]
SOURCE_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[4]
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]

SECRET_KEY = ENV.django_secret_key.get_secret_value()
DEBUG = ENV.django_debug

ALLOWED_HOSTS = ENV.allowed_hosts
CSRF_TRUSTED_ORIGINS = ENV.csrf_trusted_origins

INSTALLED_APPS = [
    # Django applications
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party applications
    "rest_framework",
    "drf_spectacular",
    # AgentProof applications
    "agentproof_backend.apps.accounts.apps.AccountsConfig",
    "agentproof_backend.apps.common.apps.CommonConfig",
    "agentproof_backend.apps.organizations.apps.OrganizationsConfig",
    "agentproof_backend.apps.audit.apps.AuditConfig",
    "agentproof_backend.apps.projects.apps.ProjectsConfig",
    "agentproof_backend.apps.api_keys.apps.APIKeysConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "agentproof_backend.apps.common.middleware.RequestIDMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "agentproof_backend.apps.organizations.middleware.CurrentOrganizationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "agentproof_backend.config.urls"

TEMPLATES: list[dict[str, Any]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PACKAGE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "agentproof_backend.config.wsgi.application"
ASGI_APPLICATION = "agentproof_backend.config.asgi.application"

DATABASES = {
    "default": dj_database_url.parse(
        ENV.database_url,
        conn_max_age=60,
        conn_health_checks=True,
    ),
}

DATABASES["default"]["ATOMIC_REQUESTS"] = False

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"

USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BACKEND_DIR / "var" / "static"

MEDIA_URL = "/media/"
MEDIA_ROOT = BACKEND_DIR / "var" / "media"

STORAGES: dict[str, dict[str, Any]] = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": MEDIA_ROOT,
            "base_url": MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": ENV.redis_url,
        "TIMEOUT": 300,
        "KEY_PREFIX": "agentproof",
        "OPTIONS": {
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
        },
    },
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": ("rest_framework.pagination.PageNumberPagination"),
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": ("agentproof_backend.apps.common.exceptions.api_exception_handler"),
    "DEFAULT_THROTTLE_RATES": {
        "api_key": "60/minute",  # pragma: allowlist secret
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AgentProof API",
    "DESCRIPTION": ("Reliability, evaluation, observability, and governance API for AI applications."),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": True,
    "ENUM_NAME_OVERRIDES": {
        "InvitationRoleEnum": "agentproof_backend.apps.organizations.models.InvitationRole.choices",
        "MembershipRoleEnum": "agentproof_backend.apps.organizations.models.MembershipRole.choices",
        "OrganizationStatusEnum": "agentproof_backend.apps.organizations.models.OrganizationStatus.choices",
        "CaptureModeEnum": "agentproof_backend.apps.projects.models.CaptureMode.choices",
        "EnvironmentTypeEnum": "agentproof_backend.apps.projects.models.EnvironmentType.choices",
        "ResourceStatusEnum": "agentproof_backend.apps.projects.models.ResourceStatus.choices",
        "APIKeyScopeEnum": "agentproof_backend.apps.api_keys.models.APIKeyScope.choices",  # pragma: allowlist secret
    },
}

CELERY_BROKER_URL = ENV.celery_broker_url
CELERY_RESULT_BACKEND = ENV.celery_result_backend

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 15 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 14 * 60
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "AgentProof <noreply@agentproof.local>"

APP_BASE_URL = ENV.app_base_url
LOGIN_URL = "/api-auth/login/"
LOGIN_REDIRECT_URL = "/api/docs/"
LOGOUT_REDIRECT_URL = "/api-auth/login/"

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2_000

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

LOGGING = build_logging_config(
    level=ENV.django_log_level.upper(),
    json_logs=ENV.environment == "production",
)
