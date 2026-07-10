"""Admin registrations for datasets."""

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from agentproof_backend.apps.common.type_utils import allow_runtime_generic
from agentproof_backend.apps.datasets.models import (
    Dataset,
    DatasetDraft,
    DatasetDraftCase,
    DatasetImportJob,
    DatasetVersion,
    DatasetVersionCase,
)

allow_runtime_generic(admin.ModelAdmin)


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin[Dataset]):
    """Admin view for dataset containers."""

    list_display = ("name", "project", "organization", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "slug", "project__name", "organization__name")
    readonly_fields = ("id", "organization", "created_at", "updated_at")

    def get_queryset(self, request: HttpRequest) -> QuerySet[Dataset]:
        return super().get_queryset(request).select_related("organization", "project", "created_by")


@admin.register(DatasetDraft)
class DatasetDraftAdmin(admin.ModelAdmin[DatasetDraft]):
    """Admin view for mutable dataset drafts."""

    list_display = ("dataset", "status", "base_version", "created_by", "created_at")
    list_filter = ("status", "created_at")
    readonly_fields = ("id", "organization", "created_at", "updated_at")

    def get_queryset(self, request: HttpRequest) -> QuerySet[DatasetDraft]:
        return super().get_queryset(request).select_related("organization", "dataset", "base_version", "created_by")


@admin.register(DatasetDraftCase)
class DatasetDraftCaseAdmin(admin.ModelAdmin[DatasetDraftCase]):
    """Admin view for draft test cases."""

    list_display = ("logical_id", "draft", "organization", "source_trace", "created_at")
    search_fields = ("logical_id", "draft__dataset__name", "source_trace__external_trace_id")
    readonly_fields = ("id", "organization", "created_at", "updated_at")

    def get_queryset(self, request: HttpRequest) -> QuerySet[DatasetDraftCase]:
        return super().get_queryset(request).select_related("organization", "draft", "draft__dataset", "source_trace")


@admin.register(DatasetVersion)
class DatasetVersionAdmin(admin.ModelAdmin[DatasetVersion]):
    """Admin view for published dataset versions."""

    list_display = ("dataset", "version_number", "content_hash", "published_by", "created_at")
    search_fields = ("dataset__name", "content_hash")
    readonly_fields = (
        "id",
        "organization",
        "dataset",
        "source_draft",
        "version_number",
        "content_hash",
        "tags",
        "input_schema",
        "output_schema",
        "published_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, _request: HttpRequest, _obj: DatasetVersion | None = None) -> bool:
        return False

    def get_queryset(self, request: HttpRequest) -> QuerySet[DatasetVersion]:
        return super().get_queryset(request).select_related("organization", "dataset", "published_by")


@admin.register(DatasetVersionCase)
class DatasetVersionCaseAdmin(admin.ModelAdmin[DatasetVersionCase]):
    """Admin view for immutable version cases."""

    list_display = ("logical_id", "version", "position", "organization")
    search_fields = ("logical_id", "version__dataset__name")
    readonly_fields = (
        "id",
        "organization",
        "version",
        "source_draft_case",
        "source_trace",
        "position",
        "logical_id",
        "input",
        "expected_behavior",
        "expected_output",
        "expected_tool_calls",
        "forbidden_tool_calls",
        "reference_output",
        "reference_context",
        "metadata",
        "tags",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, _request: HttpRequest, _obj: DatasetVersionCase | None = None) -> bool:
        return False


@admin.register(DatasetImportJob)
class DatasetImportJobAdmin(admin.ModelAdmin[DatasetImportJob]):
    """Admin view for JSONL import jobs."""

    list_display = ("draft", "status", "total_rows", "imported_rows", "error_rows", "created_at")
    list_filter = ("status", "created_at", "cleanup_after")

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    readonly_fields = (
        "id",
        "organization",
        "draft",
        "requested_by",
        "storage_path",
        "status",
        "total_rows",
        "imported_rows",
        "error_rows",
        "row_errors",
        "last_error",
        "cleanup_after",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
