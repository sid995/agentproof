"""Versioned dataset database models."""

from collections.abc import Iterable
from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.base import ModelBase
from django.db.models.constraints import BaseConstraint

from agentproof_backend.apps.common.models import TimeStampedUUIDModel
from agentproof_backend.apps.projects.models import Project
from agentproof_backend.apps.telemetry.models import Trace


class DatasetStatus(models.TextChoices):
    """Lifecycle state for a dataset container."""

    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class DatasetDraftStatus(models.TextChoices):
    """Lifecycle state for a mutable draft."""

    OPEN = "open", "Open"
    PUBLISHED = "published", "Published"
    ABANDONED = "abandoned", "Abandoned"


class DatasetImportStatus(models.TextChoices):
    """Lifecycle state for a JSONL import job."""

    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ImmutableQuerySet(models.QuerySet[Any]):
    """QuerySet that prevents application-level mutation."""

    def update(self, **_kwargs: object) -> int:
        raise RuntimeError("Published dataset content cannot be updated.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise RuntimeError("Published dataset content cannot be deleted.")


class ImmutableManager(models.Manager[Any]):
    """Manager returning immutable querysets."""

    def get_queryset(self) -> ImmutableQuerySet:
        return ImmutableQuerySet(model=self.model, using=self._db)


class Dataset(TimeStampedUUIDModel):
    """A tenant-scoped collection of evaluation cases."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="datasets")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="datasets")
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=63, allow_unicode=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=DatasetStatus.choices,
        default=DatasetStatus.ACTIVE,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_datasets",
    )

    class Meta:
        ordering = ("name", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.UniqueConstraint(fields=("project", "slug"), name="unique_dataset_slug_per_project"),
            models.CheckConstraint(condition=Q(status__in=DatasetStatus.values), name="dataset_status_valid"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organization", "status", "name"), name="dataset_org_status_name_idx"),
            models.Index(fields=("project", "status", "name"), name="dataset_project_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.project} / {self.name}"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.project_id is not None:
            if not self._state.adding and self.pk is not None:
                previous_project_id = type(self).objects.only("project_id").get(pk=self.pk).project_id
                if previous_project_id != self.project_id:
                    raise ValueError("Dataset project cannot be changed after creation.")

            project_scope = self._state.fields_cache.get("project")
            if project_scope is not None:
                self.organization_id = project_scope.organization_id
                if update_fields is not None:
                    update_fields = set(update_fields) | {"organization"}
            elif getattr(self, "organization_id", None) is None:
                project_scope = Project.objects.only("organization_id").get(pk=self.project_id)
                self.organization_id = project_scope.organization_id
                if update_fields is not None:
                    update_fields = set(update_fields) | {"organization"}

        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)


class DatasetDraft(TimeStampedUUIDModel):
    """A mutable working copy for one dataset."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="dataset_drafts",
    )
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="drafts")
    base_version = models.ForeignKey(
        "datasets.DatasetVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="derived_drafts",
    )
    status = models.CharField(
        max_length=20,
        choices=DatasetDraftStatus.choices,
        default=DatasetDraftStatus.OPEN,
        db_index=True,
    )
    tags = models.JSONField(default=list, blank=True)
    input_schema = models.JSONField(default=dict, blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_dataset_drafts",
    )

    class Meta:
        ordering = ("-created_at", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("dataset",),
                condition=Q(status=DatasetDraftStatus.OPEN),
                name="unique_open_dataset_draft",
            ),
            models.CheckConstraint(
                condition=Q(status__in=DatasetDraftStatus.values),
                name="dataset_draft_status_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organization", "status", "-created_at"), name="draft_org_status_created_idx"),
            models.Index(fields=("dataset", "status"), name="draft_dataset_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.dataset} draft"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.dataset_id is not None:
            if not self._state.adding and self.pk is not None:
                previous_dataset_id = type(self).objects.only("dataset_id").get(pk=self.pk).dataset_id
                if previous_dataset_id != self.dataset_id:
                    raise ValueError("Dataset draft parent cannot be changed after creation.")

            dataset_scope = self._state.fields_cache.get("dataset")
            if dataset_scope is not None:
                self.organization_id = dataset_scope.organization_id
                if update_fields is not None:
                    update_fields = set(update_fields) | {"organization"}
            elif getattr(self, "organization_id", None) is None:
                dataset_scope = Dataset.objects.only("organization_id").get(pk=self.dataset_id)
                self.organization_id = dataset_scope.organization_id
                if update_fields is not None:
                    update_fields = set(update_fields) | {"organization"}

        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)


class DatasetDraftCase(TimeStampedUUIDModel):
    """Editable test case inside an open draft."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="dataset_draft_cases",
    )
    draft = models.ForeignKey(DatasetDraft, on_delete=models.CASCADE, related_name="cases")
    source_trace = models.ForeignKey(
        "telemetry.Trace",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dataset_draft_cases",
    )
    logical_id = models.SlugField(max_length=120, allow_unicode=True)
    input = models.JSONField(default=dict, blank=True)
    expected_behavior = models.TextField(blank=True)
    expected_output = models.JSONField(default=dict, blank=True)
    expected_tool_calls = models.JSONField(default=list, blank=True)
    forbidden_tool_calls = models.JSONField(default=list, blank=True)
    reference_output = models.JSONField(default=dict, blank=True)
    reference_context = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_dataset_cases",
    )

    class Meta:
        ordering = ("logical_id", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.UniqueConstraint(fields=("draft", "logical_id"), name="unique_draft_case_logical_id"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organization", "logical_id"), name="draft_case_org_logical_idx"),
            models.Index(fields=("draft", "created_at"), name="draft_case_draft_created_idx"),
            models.Index(fields=("source_trace",), name="draft_case_source_trace_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.draft.dataset.name} / {self.logical_id}"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.draft_id is not None:
            if not self._state.adding and self.pk is not None:
                previous_draft_id = type(self).objects.only("draft_id").get(pk=self.pk).draft_id
                if previous_draft_id != self.draft_id:
                    raise ValueError("Dataset case draft cannot be changed after creation.")

            draft_scope = self._state.fields_cache.get("draft")
            if draft_scope is not None:
                self.organization_id = draft_scope.organization_id
                if update_fields is not None:
                    update_fields = set(update_fields) | {"organization"}
            elif getattr(self, "organization_id", None) is None:
                draft_scope = DatasetDraft.objects.only("organization_id").get(pk=self.draft_id)
                self.organization_id = draft_scope.organization_id
                if update_fields is not None:
                    update_fields = set(update_fields) | {"organization"}

        if self.source_trace_id is not None:
            trace_scope = self._state.fields_cache.get("source_trace")
            if trace_scope is not None and trace_scope.organization_id != self.organization_id:
                raise ValueError("Source trace must belong to the same organization as the dataset case.")
            if trace_scope is None:
                source_trace = Trace.objects.only("organization_id").get(pk=self.source_trace_id)
                if source_trace.organization_id != self.organization_id:
                    raise ValueError("Source trace must belong to the same organization as the dataset case.")

        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)


class DatasetVersion(TimeStampedUUIDModel):
    """Immutable published snapshot of a dataset."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="dataset_versions",
    )
    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="versions")
    source_draft = models.OneToOneField(DatasetDraft, on_delete=models.PROTECT, related_name="published_version")
    version_number = models.PositiveIntegerField()
    content_hash = models.CharField(max_length=64)
    tags = models.JSONField(default=list, blank=True)
    input_schema = models.JSONField(default=dict, blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="published_dataset_versions",
    )

    objects = ImmutableManager()

    class Meta:
        ordering = ("dataset", "-version_number", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.UniqueConstraint(fields=("dataset", "version_number"), name="unique_dataset_version_number"),
            models.UniqueConstraint(fields=("dataset", "content_hash"), name="unique_dataset_version_hash"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organization", "-created_at"), name="version_org_created_idx"),
            models.Index(fields=("dataset", "-version_number"), name="version_dataset_number_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.dataset.name} v{self.version_number}"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding:
            raise RuntimeError("Published dataset versions cannot be updated.")

        if self.dataset_id is not None:
            dataset_scope = self._state.fields_cache.get("dataset")
            if dataset_scope is not None:
                self.organization_id = dataset_scope.organization_id
            elif getattr(self, "organization_id", None) is None:
                dataset_scope = Dataset.objects.only("organization_id").get(pk=self.dataset_id)
                self.organization_id = dataset_scope.organization_id

        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)

    def delete(
        self,
        _using: str | None = None,
        _keep_parents: bool = False,
    ) -> tuple[int, dict[str, int]]:
        raise RuntimeError("Published dataset versions cannot be deleted.")


class DatasetVersionCase(TimeStampedUUIDModel):
    """Immutable case copied into a published version."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="dataset_version_cases",
    )
    version = models.ForeignKey(DatasetVersion, on_delete=models.PROTECT, related_name="cases")
    source_draft_case = models.ForeignKey(
        DatasetDraftCase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_cases",
    )
    source_trace = models.ForeignKey(
        "telemetry.Trace",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dataset_version_cases",
    )
    position = models.PositiveIntegerField()
    logical_id = models.SlugField(max_length=120, allow_unicode=True)
    input = models.JSONField(default=dict, blank=True)
    expected_behavior = models.TextField(blank=True)
    expected_output = models.JSONField(default=dict, blank=True)
    expected_tool_calls = models.JSONField(default=list, blank=True)
    forbidden_tool_calls = models.JSONField(default=list, blank=True)
    reference_output = models.JSONField(default=dict, blank=True)
    reference_context = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)

    objects = ImmutableManager()

    class Meta:
        ordering = ("position", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.UniqueConstraint(fields=("version", "logical_id"), name="unique_version_case_logical_id"),
            models.UniqueConstraint(fields=("version", "position"), name="unique_version_case_position"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organization", "logical_id"), name="version_case_org_logical_idx"),
            models.Index(fields=("version", "position"), name="version_case_position_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.version} / {self.logical_id}"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding:
            raise RuntimeError("Published dataset cases cannot be updated.")

        if self.version_id is not None:
            version_scope = self._state.fields_cache.get("version")
            if version_scope is not None:
                self.organization_id = version_scope.organization_id
            elif getattr(self, "organization_id", None) is None:
                version_scope = DatasetVersion.objects.only("organization_id").get(pk=self.version_id)
                self.organization_id = version_scope.organization_id

        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)

    def delete(
        self,
        _using: str | None = None,
        _keep_parents: bool = False,
    ) -> tuple[int, dict[str, int]]:
        raise RuntimeError("Published dataset cases cannot be deleted.")


class DatasetImportJob(TimeStampedUUIDModel):
    """Async JSONL import job for one open draft."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="dataset_import_jobs",
    )
    draft = models.ForeignKey(DatasetDraft, on_delete=models.CASCADE, related_name="import_jobs")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dataset_import_jobs",
    )
    status = models.CharField(
        max_length=20,
        choices=DatasetImportStatus.choices,
        default=DatasetImportStatus.PENDING,
        db_index=True,
    )
    storage_path = models.CharField(max_length=500, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    imported_rows = models.PositiveIntegerField(default=0)
    error_rows = models.PositiveIntegerField(default=0)
    row_errors = models.JSONField(default=list, blank=True)
    last_error = models.TextField(blank=True)
    cleanup_after = models.DateTimeField(db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "id")
        constraints: ClassVar[list[BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(status__in=DatasetImportStatus.values),
                name="dataset_import_status_valid",
            ),
            models.CheckConstraint(condition=Q(total_rows__gte=0), name="dataset_import_total_non_negative"),
            models.CheckConstraint(condition=Q(imported_rows__gte=0), name="dataset_import_imported_non_negative"),
            models.CheckConstraint(condition=Q(error_rows__gte=0), name="dataset_import_errors_non_negative"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organization", "status", "-created_at"), name="import_org_status_created_idx"),
            models.Index(fields=("draft", "-created_at"), name="import_draft_created_idx"),
            models.Index(fields=("cleanup_after", "status"), name="import_cleanup_idx"),
        ]

    def __str__(self) -> str:
        return f"DatasetImportJob({self.draft_id}, {self.status})"

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if self.draft_id is not None:
            draft_scope = self._state.fields_cache.get("draft")
            if draft_scope is not None:
                self.organization_id = draft_scope.organization_id
                if update_fields is not None:
                    update_fields = set(update_fields) | {"organization"}
            elif getattr(self, "organization_id", None) is None:
                draft_scope = DatasetDraft.objects.only("organization_id").get(pk=self.draft_id)
                self.organization_id = draft_scope.organization_id
                if update_fields is not None:
                    update_fields = set(update_fields) | {"organization"}

        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)
