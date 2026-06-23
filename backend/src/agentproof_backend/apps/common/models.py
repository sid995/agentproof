"""Shared abstract database models"""

import uuid

from django.db import models


class UUIDModel(models.Model):
    """Abstract model using a UUID primary key"""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    class Meta:
        abstract = True


class TimeStampedUUIDModel(UUIDModel):
    """Abstract UUID model with creation and modification timestamps."""

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
