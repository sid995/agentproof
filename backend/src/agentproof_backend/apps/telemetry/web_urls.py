"""Trace explorer web routes."""

from django.urls import path

from agentproof_backend.apps.telemetry import web

app_name = "trace-web"

urlpatterns = [
    path("", web.trace_list, name="trace-list"),
    path("<uuid:trace_id>/", web.trace_detail, name="trace-detail"),
    path("<uuid:trace_id>/annotations/", web.trace_annotation_create, name="trace-annotation-create"),
]
