"""Background tasks for API keys"""

from celery import shared_task
from django.utils import timezone

from agentproof_backend.apps.api_keys.models import APIKey


@shared_task(name="api_keys.update_last_used")
def update_api_key_last_used(api_key_id: str) -> None:
    """Update usage metadata outside the authentiction critical path"""
    APIKey.objects.filter(id=api_key_id, revoked_at__isnull=True).update(last_used_at=timezone.now())
