"""Dataset web routes."""

from django.urls import path

from agentproof_backend.apps.datasets import web

app_name = "dataset-web"

urlpatterns = [
    path("", web.dataset_list, name="dataset-list"),
    path("from-trace/<uuid:trace_id>/", web.trace_case_create, name="trace-case-create"),
    path("<uuid:dataset_id>/", web.dataset_detail, name="dataset-detail"),
    path("<uuid:dataset_id>/draft/", web.dataset_draft_update, name="dataset-draft-update"),
    path("<uuid:dataset_id>/cases/new/", web.dataset_case_create, name="dataset-case-create"),
    path("<uuid:dataset_id>/cases/<uuid:case_id>/edit/", web.dataset_case_edit, name="dataset-case-edit"),
    path("<uuid:dataset_id>/cases/<uuid:case_id>/delete/", web.dataset_case_delete, name="dataset-case-delete"),
    path("<uuid:dataset_id>/imports/", web.dataset_import_create, name="dataset-import-create"),
    path("<uuid:dataset_id>/imports/<uuid:job_id>/", web.dataset_import_detail, name="dataset-import-detail"),
    path("<uuid:dataset_id>/publish/", web.dataset_publish, name="dataset-publish"),
    path("<uuid:dataset_id>/versions/<uuid:version_id>/", web.dataset_version_detail, name="dataset-version-detail"),
    path(
        "<uuid:dataset_id>/versions/<uuid:version_id>/clone/",
        web.dataset_version_clone,
        name="dataset-version-clone",
    ),
    path(
        "<uuid:dataset_id>/versions/<uuid:version_id>/export/",
        web.dataset_version_export,
        name="dataset-version-export",
    ),
]
