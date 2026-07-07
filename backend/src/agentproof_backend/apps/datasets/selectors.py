"""Read-focused dataset queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from django.db.models import Count, Prefetch, QuerySet

from agentproof_backend.apps.datasets.exceptions import (
    DatasetCaseNotFound,
    DatasetDraftNotFound,
    DatasetImportJobNotFound,
    DatasetNotFound,
    DatasetVersionNotFound,
)
from agentproof_backend.apps.datasets.models import (
    Dataset,
    DatasetDraft,
    DatasetDraftCase,
    DatasetDraftStatus,
    DatasetImportJob,
    DatasetVersion,
    DatasetVersionCase,
)
from agentproof_backend.apps.organizations.models import Organization
from agentproof_backend.apps.projects.models import Project


@dataclass(frozen=True)
class DatasetFilters:
    """Dataset list filters from web query parameters."""

    project_id: UUID | str | None = None
    search: str = ""
    tag: str = ""


def datasets_for_organization(
    *,
    organization: Organization,
    filters: DatasetFilters | None = None,
) -> QuerySet[Dataset]:
    """Return tenant-scoped datasets with display counts."""

    queryset = (
        Dataset.objects.filter(organization=organization)
        .select_related("organization", "project", "created_by")
        .annotate(version_count=Count("versions", distinct=True), draft_count=Count("drafts", distinct=True))
        .order_by("name", "id")
    )
    if filters is None:
        return queryset

    if filters.project_id:
        queryset = queryset.filter(project_id=filters.project_id)
    if filters.search:
        queryset = queryset.filter(name__icontains=filters.search)
    if filters.tag:
        queryset = queryset.filter(drafts__tags__icontains=filters.tag).distinct()

    return queryset


def get_dataset_for_organization(
    *,
    organization: Organization,
    dataset_id: UUID | str,
) -> Dataset:
    """Return one tenant-scoped dataset."""

    open_drafts = DatasetDraft.objects.filter(status=DatasetDraftStatus.OPEN).prefetch_related("cases")
    try:
        return (
            Dataset.objects.filter(organization=organization)
            .select_related("organization", "project", "created_by")
            .prefetch_related(
                Prefetch("drafts", queryset=open_drafts, to_attr="open_drafts"),
                Prefetch("versions", queryset=DatasetVersion.objects.order_by("-version_number", "id")),
            )
            .get(id=dataset_id)
        )
    except Dataset.DoesNotExist as exc:
        raise DatasetNotFound("The dataset does not exist.") from exc


def get_dataset_for_project(
    *,
    organization: Organization,
    project: Project,
    dataset_id: UUID | str,
) -> Dataset:
    """Return one dataset under one tenant project."""

    try:
        return Dataset.objects.select_related("project", "created_by").get(
            organization=organization,
            project=project,
            id=dataset_id,
        )
    except Dataset.DoesNotExist as exc:
        raise DatasetNotFound("The dataset does not exist.") from exc


def get_open_draft(
    *,
    organization: Organization,
    dataset: Dataset,
) -> DatasetDraft:
    """Return the open draft for a dataset."""

    try:
        return (
            DatasetDraft.objects.filter(organization=organization, dataset=dataset, status=DatasetDraftStatus.OPEN)
            .select_related("dataset", "dataset__project", "base_version", "created_by")
            .prefetch_related("cases")
            .get()
        )
    except DatasetDraft.DoesNotExist as exc:
        raise DatasetDraftNotFound("The dataset does not have an open draft.") from exc


def get_draft_case(
    *,
    organization: Organization,
    draft: DatasetDraft,
    case_id: UUID | str,
) -> DatasetDraftCase:
    """Return one draft case."""

    try:
        return DatasetDraftCase.objects.select_related("draft", "source_trace", "created_by").get(
            organization=organization,
            draft=draft,
            id=case_id,
        )
    except DatasetDraftCase.DoesNotExist as exc:
        raise DatasetCaseNotFound("The dataset case does not exist.") from exc


def get_dataset_version(
    *,
    organization: Organization,
    dataset: Dataset,
    version_id: UUID | str,
) -> DatasetVersion:
    """Return one published version."""

    try:
        return cast(
            DatasetVersion,
            DatasetVersion.objects.filter(organization=organization, dataset=dataset, id=version_id)
            .select_related("dataset", "dataset__project", "published_by", "source_draft")
            .prefetch_related(
                Prefetch(
                    "cases",
                    queryset=DatasetVersionCase.objects.select_related("source_trace").order_by("position", "id"),
                )
            )
            .get(),
        )
    except DatasetVersion.DoesNotExist as exc:
        raise DatasetVersionNotFound("The dataset version does not exist.") from exc


def get_import_job(
    *,
    organization: Organization,
    dataset: Dataset,
    job_id: UUID | str,
) -> DatasetImportJob:
    """Return one import job for a dataset."""

    try:
        return DatasetImportJob.objects.select_related("draft", "draft__dataset", "requested_by").get(
            organization=organization,
            draft__dataset=dataset,
            id=job_id,
        )
    except DatasetImportJob.DoesNotExist as exc:
        raise DatasetImportJobNotFound("The dataset import job does not exist.") from exc
