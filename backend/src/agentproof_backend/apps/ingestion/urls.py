"""Ingestion URL routes."""

from django.urls import path

from agentproof_backend.apps.ingestion.api import IngestTraceBatchAPIView

app_name = "ingestion"

urlpatterns = [
    path("ingest/traces", IngestTraceBatchAPIView.as_view(), name="ingest-traces"),
]
