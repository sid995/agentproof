"""State-changing dataset use cases."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

from django.core.files.base import File
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.text import slugify
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError  # type: ignore[import-untyped]
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.audit.services import record_audit_event
from agentproof_backend.apps.datasets.exceptions import (
    DatasetCaseNotFound,
    DatasetConflict,
    DatasetDraftNotFound,
    DatasetError,
    DatasetImmutable,
    DatasetImportJobNotFound,
    DatasetNotFound,
    DatasetPermissionDenied,
    DatasetValidationError,
    DatasetVersionNotFound,
)
from agentproof_backend.apps.datasets.models import (
    Dataset,
    DatasetDraft,
    DatasetDraftCase,
    DatasetDraftStatus,
    DatasetImportJob,
    DatasetImportStatus,
    DatasetStatus,
    DatasetVersion,
    DatasetVersionCase,
)
from agentproof_backend.apps.organizations.models import (
    Membership,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from agentproof_backend.apps.projects.exceptions import ProjectNotFound
from agentproof_backend.apps.projects.models import Project, ResourceStatus
from agentproof_backend.apps.telemetry.exceptions import TraceNotFound
from agentproof_backend.apps.telemetry.models import Trace

DATASET_MANAGER_ROLES = {
    MembershipRole.OWNER,
    MembershipRole.ADMINISTRATOR,
    MembershipRole.DEVELOPER,
}
IMPORT_RETENTION_DAYS = 7
MAX_ROW_ERRORS = 200


@dataclass(frozen=True, slots=True)
class CreatedDataset:
    """New dataset and its first mutable draft."""

    dataset: Dataset
    draft: DatasetDraft


@dataclass(frozen=True, slots=True)
class ImportResult:
    """Counts from a JSONL import processing pass."""

    total_rows: int
    imported_rows: int
    error_rows: int


def dataset_snapshot(dataset: Dataset) -> dict[str, Any]:
    """Create a serializable dataset audit snapshot."""

    return {
        "id": str(dataset.id),
        "organization_id": str(dataset.organization_id),
        "project_id": str(dataset.project_id),
        "name": dataset.name,
        "slug": dataset.slug,
        "description": dataset.description,
        "status": dataset.status,
    }


def draft_snapshot(draft: DatasetDraft) -> dict[str, Any]:
    """Create a serializable draft audit snapshot."""

    return {
        "id": str(draft.id),
        "dataset_id": str(draft.dataset_id),
        "base_version_id": str(draft.base_version_id) if draft.base_version_id else "",
        "status": draft.status,
        "tags": list(draft.tags),
        "input_schema": dict(draft.input_schema),
        "output_schema": dict(draft.output_schema),
    }


def case_snapshot(case: DatasetDraftCase) -> dict[str, Any]:
    """Create a serializable case audit snapshot."""

    return {
        "id": str(case.id),
        "draft_id": str(case.draft_id),
        "logical_id": case.logical_id,
        "source_trace_id": str(case.source_trace_id) if case.source_trace_id else "",
        "input": case.input,
        "expected_behavior": case.expected_behavior,
        "expected_output": case.expected_output,
        "expected_tool_calls": case.expected_tool_calls,
        "forbidden_tool_calls": case.forbidden_tool_calls,
        "reference_output": case.reference_output,
        "reference_context": case.reference_context,
        "metadata": case.metadata,
        "tags": case.tags,
    }


def _get_actor_membership(
    *,
    actor: User,
    organization: Organization,
) -> Membership:
    if organization.status != OrganizationStatus.ACTIVE:
        raise DatasetPermissionDenied("The organization is not active.")

    try:
        return Membership.objects.get(organization=organization, user=actor, status=MembershipStatus.ACTIVE)
    except Membership.DoesNotExist as exc:
        raise DatasetPermissionDenied("You are not an active organization member.") from exc


def _require_dataset_manager(
    *,
    actor: User,
    organization: Organization,
) -> Membership:
    membership = _get_actor_membership(actor=actor, organization=organization)
    if membership.role not in DATASET_MANAGER_ROLES:
        raise DatasetPermissionDenied("Owner, administrator, or developer access is required.")
    return membership


def _get_locked_project(
    *,
    organization: Organization,
    project_id: UUID | str,
) -> Project:
    try:
        return Project.objects.select_for_update().get(id=project_id, organization=organization)
    except Project.DoesNotExist as exc:
        raise ProjectNotFound("The project does not exist.") from exc


def _get_locked_dataset(
    *,
    organization: Organization,
    dataset_id: UUID | str,
) -> Dataset:
    try:
        return (
            Dataset.objects.select_for_update()
            .select_related("project", "created_by")
            .get(id=dataset_id, organization=organization)
        )
    except Dataset.DoesNotExist as exc:
        raise DatasetNotFound("The dataset does not exist.") from exc


def _get_locked_open_draft(
    *,
    organization: Organization,
    dataset: Dataset,
) -> DatasetDraft:
    try:
        return (
            DatasetDraft.objects.select_for_update()
            .select_related("dataset", "dataset__project", "base_version")
            .get(organization=organization, dataset=dataset, status=DatasetDraftStatus.OPEN)
        )
    except DatasetDraft.DoesNotExist as exc:
        raise DatasetDraftNotFound("The dataset does not have an open draft.") from exc


def _get_locked_case(
    *,
    organization: Organization,
    draft: DatasetDraft,
    case_id: UUID | str,
) -> DatasetDraftCase:
    try:
        return (
            DatasetDraftCase.objects.select_for_update()
            .select_related("draft", "source_trace")
            .get(
                organization=organization,
                draft=draft,
                id=case_id,
            )
        )
    except DatasetDraftCase.DoesNotExist as exc:
        raise DatasetCaseNotFound("The dataset case does not exist.") from exc


def _get_locked_version(
    *,
    organization: Organization,
    dataset: Dataset,
    version_id: UUID | str,
) -> DatasetVersion:
    try:
        return cast(
            DatasetVersion,
            DatasetVersion.objects.select_for_update()
            .select_related("dataset", "source_draft", "published_by")
            .get(organization=organization, dataset=dataset, id=version_id),
        )
    except DatasetVersion.DoesNotExist as exc:
        raise DatasetVersionNotFound("The dataset version does not exist.") from exc


def _build_available_dataset_slug(
    *,
    project: Project,
    name: str,
    requested_slug: str | None,
) -> str:
    source = requested_slug or name
    base_slug = slugify(source, allow_unicode=True)[:63].strip("-")
    if not base_slug:
        base_slug = f"dataset-{uuid.uuid4().hex[:8]}"

    candidate = base_slug
    while Dataset.objects.filter(project=project, slug=candidate).exists():
        suffix = uuid.uuid4().hex[:8]
        candidate = f"{base_slug[:54]}-{suffix}"
    return candidate


def _normalize_tags(tags: list[str]) -> list[str]:
    return sorted({tag.strip() for tag in tags if tag.strip()})


def _validate_json_object(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DatasetValidationError(f"{field_name} must be a JSON object.")
    return value


def _validate_json_array(value: object, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise DatasetValidationError(f"{field_name} must be a JSON array.")
    return value


def _validate_schema(schema: object, field_name: str) -> dict[str, Any]:
    normalized = _validate_json_object(schema, field_name)
    if not normalized:
        return normalized

    try:
        Draft202012Validator.check_schema(normalized)
    except SchemaError as exc:
        raise DatasetValidationError(f"{field_name} is not a valid JSON Schema: {exc.message}") from exc

    return normalized


def _validate_value_against_schema(*, value: object, schema: dict[str, Any], field_name: str) -> None:
    if not schema:
        return

    try:
        Draft202012Validator(schema).validate(value)
    except JSONSchemaValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path)
        location = f" at {path}" if path else ""
        raise DatasetValidationError(f"{field_name}{location} does not match schema: {exc.message}") from exc


def _validate_case_payload(
    *,
    draft: DatasetDraft,
    input_value: object,
    expected_behavior: str,
    expected_output: object,
    expected_tool_calls: object,
    forbidden_tool_calls: object,
    reference_output: object,
    reference_context: object,
    metadata: object,
    tags: object,
    require_expectation: bool,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[Any],
    list[Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[str],
]:
    normalized_input = _validate_json_object(input_value, "input")
    normalized_expected_output = _validate_json_object(expected_output, "expected_output")
    normalized_expected_tool_calls = _validate_json_array(expected_tool_calls, "expected_tool_calls")
    normalized_forbidden_tool_calls = _validate_json_array(forbidden_tool_calls, "forbidden_tool_calls")
    normalized_reference_output = _validate_json_object(reference_output, "reference_output")
    normalized_reference_context = _validate_json_object(reference_context, "reference_context")
    normalized_metadata = _validate_json_object(metadata, "metadata")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise DatasetValidationError("tags must be a JSON array of strings.")
    normalized_tags = _normalize_tags(tags)

    _validate_value_against_schema(value=normalized_input, schema=draft.input_schema, field_name="input")
    if normalized_expected_output:
        _validate_value_against_schema(
            value=normalized_expected_output,
            schema=draft.output_schema,
            field_name="expected_output",
        )

    if require_expectation and not any(
        (
            expected_behavior.strip(),
            normalized_expected_output,
            normalized_expected_tool_calls,
            normalized_forbidden_tool_calls,
        )
    ):
        raise DatasetValidationError("A test case requires at least one expectation before publishing.")

    return (
        normalized_input,
        normalized_expected_output,
        normalized_expected_tool_calls,
        normalized_forbidden_tool_calls,
        normalized_reference_output,
        normalized_reference_context,
        normalized_metadata,
        normalized_tags,
    )


def _case_hash_payload(case: DatasetDraftCase, position: int) -> dict[str, Any]:
    return {
        "position": position,
        "logical_id": case.logical_id,
        "input": case.input,
        "expected_behavior": case.expected_behavior,
        "expected_output": case.expected_output,
        "expected_tool_calls": case.expected_tool_calls,
        "forbidden_tool_calls": case.forbidden_tool_calls,
        "reference_output": case.reference_output,
        "reference_context": case.reference_context,
        "metadata": case.metadata,
        "tags": case.tags,
        "source_trace_id": str(case.source_trace_id) if case.source_trace_id else "",
    }


def _draft_hash_payload(*, draft: DatasetDraft, cases: list[DatasetDraftCase]) -> dict[str, Any]:
    return {
        "schema_version": "agentproof.dataset.v1",
        "dataset_id": str(draft.dataset_id),
        "tags": draft.tags,
        "input_schema": draft.input_schema,
        "output_schema": draft.output_schema,
        "cases": [_case_hash_payload(case, position) for position, case in enumerate(cases, start=1)],
    }


def _content_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


@transaction.atomic
def create_dataset(
    *,
    actor: User,
    organization: Organization,
    project_id: UUID | str,
    name: str,
    requested_slug: str | None,
    description: str,
    tags: list[str],
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    audit_context: AuditContext,
) -> CreatedDataset:
    """Create a dataset and its first draft."""

    _require_dataset_manager(actor=actor, organization=organization)
    project = _get_locked_project(organization=organization, project_id=project_id)
    if project.status != ResourceStatus.ACTIVE:
        raise DatasetValidationError("Datasets can only be created in active projects.")

    normalized_name = name.strip()
    if not normalized_name:
        raise DatasetValidationError("Dataset name cannot be empty.")

    normalized_input_schema = _validate_schema(input_schema, "input_schema")
    normalized_output_schema = _validate_schema(output_schema, "output_schema")
    slug = _build_available_dataset_slug(project=project, name=normalized_name, requested_slug=requested_slug)

    try:
        dataset = Dataset.objects.create(
            organization=organization,
            project=project,
            name=normalized_name,
            slug=slug,
            description=description.strip(),
            status=DatasetStatus.ACTIVE,
            created_by=actor,
        )
        draft = DatasetDraft.objects.create(
            organization=organization,
            dataset=dataset,
            tags=_normalize_tags(tags),
            input_schema=normalized_input_schema,
            output_schema=normalized_output_schema,
            created_by=actor,
        )
    except IntegrityError as exc:
        raise DatasetConflict("A dataset with this slug already exists in the project.") from exc

    record_audit_event(
        organization=organization,
        actor=actor,
        action="dataset.created",
        resource_type="dataset",
        resource_id=dataset.id,
        context=audit_context,
        after_state=dataset_snapshot(dataset),
    )
    record_audit_event(
        organization=organization,
        actor=actor,
        action="dataset_draft.created",
        resource_type="dataset_draft",
        resource_id=draft.id,
        context=audit_context,
        after_state=draft_snapshot(draft),
    )
    return CreatedDataset(dataset=dataset, draft=draft)


@transaction.atomic
def update_draft_metadata(
    *,
    actor: User,
    organization: Organization,
    dataset_id: UUID | str,
    tags: list[str],
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    audit_context: AuditContext,
) -> DatasetDraft:
    """Update version-affecting metadata for an open draft."""

    _require_dataset_manager(actor=actor, organization=organization)
    dataset = _get_locked_dataset(organization=organization, dataset_id=dataset_id)
    draft = _get_locked_open_draft(organization=organization, dataset=dataset)
    before_state = draft_snapshot(draft)

    draft.tags = _normalize_tags(tags)
    draft.input_schema = _validate_schema(input_schema, "input_schema")
    draft.output_schema = _validate_schema(output_schema, "output_schema")
    draft.save(update_fields=("tags", "input_schema", "output_schema", "updated_at"))

    record_audit_event(
        organization=organization,
        actor=actor,
        action="dataset_draft.updated",
        resource_type="dataset_draft",
        resource_id=draft.id,
        context=audit_context,
        before_state=before_state,
        after_state=draft_snapshot(draft),
    )
    return draft


@transaction.atomic
def create_draft_case(
    *,
    actor: User,
    organization: Organization,
    dataset_id: UUID | str,
    logical_id: str,
    input_value: dict[str, Any],
    expected_behavior: str,
    expected_output: dict[str, Any],
    expected_tool_calls: list[Any],
    forbidden_tool_calls: list[Any],
    reference_output: dict[str, Any],
    reference_context: dict[str, Any],
    metadata: dict[str, Any],
    tags: list[str],
    audit_context: AuditContext,
    source_trace: Trace | None = None,
) -> DatasetDraftCase:
    """Create an editable test case in an open draft."""

    _require_dataset_manager(actor=actor, organization=organization)
    dataset = _get_locked_dataset(organization=organization, dataset_id=dataset_id)
    draft = _get_locked_open_draft(organization=organization, dataset=dataset)
    normalized_logical_id = logical_id.strip()
    if not normalized_logical_id:
        raise DatasetValidationError("Case logical ID cannot be empty.")
    if source_trace is not None and source_trace.organization_id != organization.id:
        raise DatasetValidationError("Source trace does not belong to the organization.")

    (
        normalized_input,
        normalized_expected_output,
        normalized_expected_tool_calls,
        normalized_forbidden_tool_calls,
        normalized_reference_output,
        normalized_reference_context,
        normalized_metadata,
        normalized_tags,
    ) = _validate_case_payload(
        draft=draft,
        input_value=input_value,
        expected_behavior=expected_behavior,
        expected_output=expected_output,
        expected_tool_calls=expected_tool_calls,
        forbidden_tool_calls=forbidden_tool_calls,
        reference_output=reference_output,
        reference_context=reference_context,
        metadata=metadata,
        tags=tags,
        require_expectation=False,
    )

    try:
        case = DatasetDraftCase.objects.create(
            organization=organization,
            draft=draft,
            source_trace=source_trace,
            logical_id=normalized_logical_id,
            input=normalized_input,
            expected_behavior=expected_behavior.strip(),
            expected_output=normalized_expected_output,
            expected_tool_calls=normalized_expected_tool_calls,
            forbidden_tool_calls=normalized_forbidden_tool_calls,
            reference_output=normalized_reference_output,
            reference_context=normalized_reference_context,
            metadata=normalized_metadata,
            tags=normalized_tags,
            created_by=actor,
        )
    except IntegrityError as exc:
        raise DatasetConflict("A case with this logical ID already exists in the draft.") from exc

    record_audit_event(
        organization=organization,
        actor=actor,
        action="dataset_case.created",
        resource_type="dataset_case",
        resource_id=case.id,
        context=audit_context,
        after_state=case_snapshot(case),
    )
    return case


@transaction.atomic
def update_draft_case(
    *,
    actor: User,
    organization: Organization,
    dataset_id: UUID | str,
    case_id: UUID | str,
    logical_id: str,
    input_value: dict[str, Any],
    expected_behavior: str,
    expected_output: dict[str, Any],
    expected_tool_calls: list[Any],
    forbidden_tool_calls: list[Any],
    reference_output: dict[str, Any],
    reference_context: dict[str, Any],
    metadata: dict[str, Any],
    tags: list[str],
    audit_context: AuditContext,
) -> DatasetDraftCase:
    """Update an editable test case in an open draft."""

    _require_dataset_manager(actor=actor, organization=organization)
    dataset = _get_locked_dataset(organization=organization, dataset_id=dataset_id)
    draft = _get_locked_open_draft(organization=organization, dataset=dataset)
    case = _get_locked_case(organization=organization, draft=draft, case_id=case_id)
    before_state = case_snapshot(case)
    normalized_logical_id = logical_id.strip()
    if not normalized_logical_id:
        raise DatasetValidationError("Case logical ID cannot be empty.")

    (
        normalized_input,
        normalized_expected_output,
        normalized_expected_tool_calls,
        normalized_forbidden_tool_calls,
        normalized_reference_output,
        normalized_reference_context,
        normalized_metadata,
        normalized_tags,
    ) = _validate_case_payload(
        draft=draft,
        input_value=input_value,
        expected_behavior=expected_behavior,
        expected_output=expected_output,
        expected_tool_calls=expected_tool_calls,
        forbidden_tool_calls=forbidden_tool_calls,
        reference_output=reference_output,
        reference_context=reference_context,
        metadata=metadata,
        tags=tags,
        require_expectation=False,
    )

    case.logical_id = normalized_logical_id
    case.input = normalized_input
    case.expected_behavior = expected_behavior.strip()
    case.expected_output = normalized_expected_output
    case.expected_tool_calls = normalized_expected_tool_calls
    case.forbidden_tool_calls = normalized_forbidden_tool_calls
    case.reference_output = normalized_reference_output
    case.reference_context = normalized_reference_context
    case.metadata = normalized_metadata
    case.tags = normalized_tags
    try:
        case.save(
            update_fields=(
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
                "updated_at",
            )
        )
    except IntegrityError as exc:
        raise DatasetConflict("A case with this logical ID already exists in the draft.") from exc

    record_audit_event(
        organization=organization,
        actor=actor,
        action="dataset_case.updated",
        resource_type="dataset_case",
        resource_id=case.id,
        context=audit_context,
        before_state=before_state,
        after_state=case_snapshot(case),
    )
    return case


@transaction.atomic
def delete_draft_case(
    *,
    actor: User,
    organization: Organization,
    dataset_id: UUID | str,
    case_id: UUID | str,
    audit_context: AuditContext,
) -> None:
    """Delete a case from an open draft."""

    _require_dataset_manager(actor=actor, organization=organization)
    dataset = _get_locked_dataset(organization=organization, dataset_id=dataset_id)
    draft = _get_locked_open_draft(organization=organization, dataset=dataset)
    case = _get_locked_case(organization=organization, draft=draft, case_id=case_id)
    before_state = case_snapshot(case)
    case.delete()
    record_audit_event(
        organization=organization,
        actor=actor,
        action="dataset_case.deleted",
        resource_type="dataset_case",
        resource_id=case_id,
        context=audit_context,
        before_state=before_state,
    )


@transaction.atomic
def create_case_from_trace(
    *,
    actor: User,
    organization: Organization,
    dataset_id: UUID | str,
    trace_id: UUID | str,
    logical_id: str,
    expected_behavior: str,
    tags: list[str],
    audit_context: AuditContext,
) -> DatasetDraftCase:
    """Create a draft case by copying trace input and reference output."""

    try:
        trace = Trace.objects.select_related("project", "environment").get(id=trace_id, organization=organization)
    except Trace.DoesNotExist as exc:
        raise TraceNotFound("The trace does not exist.") from exc

    metadata = {
        "source": "trace",
        "trace_id": str(trace.id),
        "external_trace_id": trace.external_trace_id,
        "trace_name": trace.name,
        "trace_status": trace.status,
        "environment_id": str(trace.environment_id),
        "started_at": trace.started_at.isoformat(),
    }
    return create_draft_case(
        actor=actor,
        organization=organization,
        dataset_id=dataset_id,
        logical_id=logical_id,
        input_value=dict(trace.input),
        expected_behavior=expected_behavior,
        expected_output={},
        expected_tool_calls=[],
        forbidden_tool_calls=[],
        reference_output=dict(trace.output),
        reference_context={"attributes": trace.attributes, "tags": trace.tags},
        metadata=metadata,
        tags=tags,
        audit_context=audit_context,
        source_trace=trace,
    )


@transaction.atomic
def publish_dataset_version(
    *,
    actor: User,
    organization: Organization,
    dataset_id: UUID | str,
    audit_context: AuditContext,
) -> DatasetVersion:
    """Publish an immutable dataset version from the open draft."""

    _require_dataset_manager(actor=actor, organization=organization)
    dataset = _get_locked_dataset(organization=organization, dataset_id=dataset_id)
    draft = _get_locked_open_draft(organization=organization, dataset=dataset)
    cases = list(
        DatasetDraftCase.objects.select_for_update()
        .filter(organization=organization, draft=draft)
        .select_related("source_trace")
        .order_by("logical_id", "id")
    )
    if not cases:
        raise DatasetValidationError("A dataset version requires at least one test case.")

    _validate_schema(draft.input_schema, "input_schema")
    _validate_schema(draft.output_schema, "output_schema")
    for case in cases:
        _validate_case_payload(
            draft=draft,
            input_value=case.input,
            expected_behavior=case.expected_behavior,
            expected_output=case.expected_output,
            expected_tool_calls=case.expected_tool_calls,
            forbidden_tool_calls=case.forbidden_tool_calls,
            reference_output=case.reference_output,
            reference_context=case.reference_context,
            metadata=case.metadata,
            tags=case.tags,
            require_expectation=True,
        )

    payload = _draft_hash_payload(draft=draft, cases=cases)
    content_hash = _content_hash(payload)
    latest_version = DatasetVersion.objects.filter(dataset=dataset).aggregate(max_version=Max("version_number"))[
        "max_version"
    ]
    version_number = int(latest_version or 0) + 1

    try:
        version = cast(
            DatasetVersion,
            DatasetVersion.objects.create(
                organization=organization,
                dataset=dataset,
                source_draft=draft,
                version_number=version_number,
                content_hash=content_hash,
                tags=list(draft.tags),
                input_schema=dict(draft.input_schema),
                output_schema=dict(draft.output_schema),
                published_by=actor,
            ),
        )
        DatasetVersionCase.objects.bulk_create(
            [
                DatasetVersionCase(
                    organization=organization,
                    version=version,
                    source_draft_case=case,
                    source_trace=case.source_trace,
                    position=position,
                    logical_id=case.logical_id,
                    input=case.input,
                    expected_behavior=case.expected_behavior,
                    expected_output=case.expected_output,
                    expected_tool_calls=case.expected_tool_calls,
                    forbidden_tool_calls=case.forbidden_tool_calls,
                    reference_output=case.reference_output,
                    reference_context=case.reference_context,
                    metadata=case.metadata,
                    tags=case.tags,
                )
                for position, case in enumerate(cases, start=1)
            ]
        )
    except IntegrityError as exc:
        raise DatasetConflict("This dataset content has already been published.") from exc

    draft.status = DatasetDraftStatus.PUBLISHED
    draft.save(update_fields=("status", "updated_at"))
    record_audit_event(
        organization=organization,
        actor=actor,
        action="dataset_version.published",
        resource_type="dataset_version",
        resource_id=version.id,
        context=audit_context,
        after_state={
            "id": str(version.id),
            "dataset_id": str(dataset.id),
            "version_number": version.version_number,
            "content_hash": version.content_hash,
            "case_count": len(cases),
        },
    )
    return version


@transaction.atomic
def clone_version_to_draft(
    *,
    actor: User,
    organization: Organization,
    dataset_id: UUID | str,
    version_id: UUID | str,
    audit_context: AuditContext,
) -> DatasetDraft:
    """Create a new open draft from a published version."""

    _require_dataset_manager(actor=actor, organization=organization)
    dataset = _get_locked_dataset(organization=organization, dataset_id=dataset_id)
    if DatasetDraft.objects.filter(dataset=dataset, status=DatasetDraftStatus.OPEN).exists():
        raise DatasetConflict("This dataset already has an open draft.")
    version = _get_locked_version(organization=organization, dataset=dataset, version_id=version_id)
    version_cases = list(
        DatasetVersionCase.objects.filter(organization=organization, version=version)
        .select_related("source_trace")
        .order_by("position", "id")
    )

    try:
        draft = DatasetDraft.objects.create(
            organization=organization,
            dataset=dataset,
            base_version=version,
            tags=list(version.tags),
            input_schema=dict(version.input_schema),
            output_schema=dict(version.output_schema),
            created_by=actor,
        )
        DatasetDraftCase.objects.bulk_create(
            [
                DatasetDraftCase(
                    organization=organization,
                    draft=draft,
                    source_trace=version_case.source_trace,
                    logical_id=version_case.logical_id,
                    input=version_case.input,
                    expected_behavior=version_case.expected_behavior,
                    expected_output=version_case.expected_output,
                    expected_tool_calls=version_case.expected_tool_calls,
                    forbidden_tool_calls=version_case.forbidden_tool_calls,
                    reference_output=version_case.reference_output,
                    reference_context=version_case.reference_context,
                    metadata=version_case.metadata,
                    tags=version_case.tags,
                    created_by=actor,
                )
                for version_case in version_cases
            ]
        )
    except IntegrityError as exc:
        raise DatasetConflict("A new draft could not be created for this dataset.") from exc

    record_audit_event(
        organization=organization,
        actor=actor,
        action="dataset_draft.cloned",
        resource_type="dataset_draft",
        resource_id=draft.id,
        context=audit_context,
        after_state=draft_snapshot(draft),
        metadata={"base_version_id": str(version.id)},
    )
    return draft


@transaction.atomic
def create_import_job(
    *,
    actor: User,
    organization: Organization,
    dataset_id: UUID | str,
    uploaded_file: File[Any],
    audit_context: AuditContext,
) -> DatasetImportJob:
    """Store an uploaded JSONL file and create an import job."""

    _require_dataset_manager(actor=actor, organization=organization)
    dataset = _get_locked_dataset(organization=organization, dataset_id=dataset_id)
    draft = _get_locked_open_draft(organization=organization, dataset=dataset)
    storage_path = default_storage.save(
        f"dataset-imports/{organization.id}/{draft.id}/{uuid.uuid4().hex}.jsonl",
        uploaded_file,
    )
    job = DatasetImportJob.objects.create(
        organization=organization,
        draft=draft,
        requested_by=actor,
        storage_path=storage_path,
        cleanup_after=timezone.now() + timedelta(days=IMPORT_RETENTION_DAYS),
    )
    record_audit_event(
        organization=organization,
        actor=actor,
        action="dataset_import.created",
        resource_type="dataset_import",
        resource_id=job.id,
        context=audit_context,
        after_state={"id": str(job.id), "draft_id": str(draft.id), "storage_path": storage_path},
    )
    return job


def _row_error(*, row_number: int, message: str) -> dict[str, Any]:
    return {"row": row_number, "error": message}


def _case_kwargs_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "logical_id": str(row.get("logical_id", "")).strip(),
        "input_value": row.get("input", {}),
        "expected_behavior": str(row.get("expected_behavior", "")).strip(),
        "expected_output": row.get("expected_output", {}),
        "expected_tool_calls": row.get("expected_tool_calls", []),
        "forbidden_tool_calls": row.get("forbidden_tool_calls", []),
        "reference_output": row.get("reference_output", {}),
        "reference_context": row.get("reference_context", {}),
        "metadata": row.get("metadata", {}),
        "tags": row.get("tags", []),
    }


@transaction.atomic
def _claim_import_job(job_id: UUID | str) -> DatasetImportJob:
    try:
        job = DatasetImportJob.objects.select_for_update().select_related("draft", "draft__dataset").get(id=job_id)
    except DatasetImportJob.DoesNotExist as exc:
        raise DatasetImportJobNotFound("The dataset import job does not exist.") from exc
    if job.status != DatasetImportStatus.PENDING:
        raise DatasetImmutable("This import job is not pending.")
    job.status = DatasetImportStatus.PROCESSING
    job.started_at = timezone.now()
    job.save(update_fields=("status", "started_at", "updated_at"))
    return job


def process_import_job(*, job_id: UUID | str) -> ImportResult:
    """Process one JSONL import job."""

    job = _claim_import_job(job_id)
    total_rows = 0
    imported_rows = 0
    row_errors: list[dict[str, Any]] = []

    try:
        with default_storage.open(job.storage_path, "rb") as storage_file:
            raw_content = storage_file.read()
        content = raw_content.decode() if isinstance(raw_content, bytes) else str(raw_content)
        lines = content.splitlines()
        for row_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            total_rows += 1
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise DatasetValidationError("Row must be a JSON object.")
                kwargs = _case_kwargs_from_row(row)
                if not kwargs["logical_id"]:
                    raise DatasetValidationError("logical_id is required.")
                create_draft_case(
                    actor=job.requested_by,
                    organization=job.organization,
                    dataset_id=job.draft.dataset_id,
                    audit_context=AuditContext(request_id="", source_ip=None, user_agent="dataset-import"),
                    **kwargs,
                )
            except (json.JSONDecodeError, DatasetError, IntegrityError) as exc:
                if len(row_errors) < MAX_ROW_ERRORS:
                    row_errors.append(_row_error(row_number=row_number, message=str(exc)))
            else:
                imported_rows += 1
    except Exception as exc:
        DatasetImportJob.objects.filter(id=job.id).update(
            status=DatasetImportStatus.FAILED,
            total_rows=total_rows,
            imported_rows=imported_rows,
            error_rows=total_rows - imported_rows,
            row_errors=row_errors,
            last_error=f"{type(exc).__name__}: {exc}"[:4_000],
            completed_at=timezone.now(),
        )
        raise

    error_rows = total_rows - imported_rows
    DatasetImportJob.objects.filter(id=job.id).update(
        status=DatasetImportStatus.COMPLETED if error_rows == 0 else DatasetImportStatus.FAILED,
        total_rows=total_rows,
        imported_rows=imported_rows,
        error_rows=error_rows,
        row_errors=row_errors,
        last_error="",
        completed_at=timezone.now(),
    )
    return ImportResult(total_rows=total_rows, imported_rows=imported_rows, error_rows=error_rows)


def cleanup_import_files(*, now: Any | None = None) -> int:
    """Delete expired temporary import files."""

    cutoff = now or timezone.now()
    jobs = DatasetImportJob.objects.filter(
        cleanup_after__lte=cutoff,
        storage_path__gt="",
        status__in=(DatasetImportStatus.COMPLETED, DatasetImportStatus.FAILED),
    )
    cleaned = 0
    for job in jobs:
        if default_storage.exists(job.storage_path):
            default_storage.delete(job.storage_path)
        job.storage_path = ""
        job.save(update_fields=("storage_path", "updated_at"))
        cleaned += 1
    return cleaned


def version_cases_jsonl(version: DatasetVersion) -> str:
    """Return stable JSONL export content for a published version."""

    lines: list[str] = []
    cases = DatasetVersionCase.objects.filter(version=version).order_by("position", "id")
    for case in cases:
        row = {
            "logical_id": case.logical_id,
            "input": case.input,
            "expected_behavior": case.expected_behavior,
            "expected_output": case.expected_output,
            "expected_tool_calls": case.expected_tool_calls,
            "forbidden_tool_calls": case.forbidden_tool_calls,
            "reference_output": case.reference_output,
            "reference_context": case.reference_context,
            "metadata": case.metadata,
            "tags": case.tags,
        }
        lines.append(json.dumps(row, sort_keys=True, separators=(",", ":"), default=str))
    return "\n".join(lines) + ("\n" if lines else "")
