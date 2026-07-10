"""Tests for Phase 11 versioned datasets."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile
from django.db import connection, models
from django.db.models.deletion import ProtectedError
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.datasets.exceptions import (
    DatasetConflict,
    DatasetPermissionDenied,
    DatasetValidationError,
)
from agentproof_backend.apps.datasets.models import (
    Dataset,
    DatasetDraftCase,
    DatasetImportJob,
    DatasetImportStatus,
    DatasetVersion,
    DatasetVersionCase,
)
from agentproof_backend.apps.datasets.selectors import DatasetFilters, datasets_for_organization
from agentproof_backend.apps.datasets.services import (
    cleanup_import_files,
    clone_version_to_draft,
    create_case_from_trace,
    create_dataset,
    create_draft_case,
    create_import_job,
    process_import_job,
    publish_dataset_version,
    update_draft_case,
    update_draft_metadata,
    version_cases_jsonl,
)
from agentproof_backend.apps.organizations.models import MembershipRole
from agentproof_backend.apps.projects.models import CaptureMode, Environment, Project
from agentproof_backend.apps.projects.services import create_project
from agentproof_backend.apps.telemetry.domain import CanonicalSpan, CanonicalTrace, TokenUsage
from agentproof_backend.apps.telemetry.models import SpanType, Trace, TraceStatus
from agentproof_backend.apps.telemetry.services import persist_canonical_trace
from tests.organization_helpers import add_member, create_test_organization, create_user

pytestmark = pytest.mark.django_db

AUDIT_CONTEXT = AuditContext(
    request_id="phase-eleven-test",
    source_ip="127.0.0.1",
    user_agent="pytest",
)


def create_project_with_environment(*, owner: object, organization: object) -> tuple[Project, Environment]:
    result = create_project(
        actor=owner,
        organization=organization,
        name="Support Agent",
        requested_slug="support-agent",
        description="Customer support workflow",
        capture_mode=CaptureMode.FULL,
        retention_days=30,
        audit_context=AUDIT_CONTEXT,
    )
    return result.project, result.default_environment


def create_dataset_with_draft(*, owner: object, organization: object, project: Project) -> Dataset:
    return create_dataset(
        actor=owner,
        organization=organization,
        project_id=project.id,
        name="Regression Cases",
        requested_slug="regression-cases",
        description="Failures promoted from traces",
        tags=["support"],
        input_schema={"type": "object", "required": ["question"]},
        output_schema={"type": "object"},
        audit_context=AUDIT_CONTEXT,
    ).dataset


def create_case(
    *,
    owner: object,
    organization: object,
    dataset: Dataset,
    logical_id: str = "case-1",
) -> DatasetDraftCase:
    return create_draft_case(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        logical_id=logical_id,
        input_value={"question": "Why did this fail?"},
        expected_behavior="Answer the user without timing out.",
        expected_output={},
        expected_tool_calls=[],
        forbidden_tool_calls=["timeout"],
        reference_output={"answer": "retry"},
        reference_context={"documents": ["refund policy"]},
        metadata={"severity": "high"},
        tags=["support", "failure"],
        audit_context=AUDIT_CONTEXT,
    )


def create_trace(*, organization: object, project: Project, environment: Environment) -> Trace:
    started_at = timezone.now()
    return persist_canonical_trace(
        organization=organization,
        project=project,
        environment=environment,
        canonical_trace=CanonicalTrace(
            external_trace_id="trace-1",
            schema_version="agentproof.v1",
            name="Failed support run",
            status=TraceStatus.ERROR,
            started_at=started_at,
            ended_at=started_at + timedelta(milliseconds=500),
            duration_ms=500,
            input={"question": "Refund?"},
            output={"answer": "Tool failed"},
            attributes={"workflow": "support"},
            tags=("support", "failure"),
            token_usage=TokenUsage(input_tokens=10, output_tokens=5, estimated_cost=Decimal("0.001000")),
            spans=(
                CanonicalSpan(
                    external_span_id="root",
                    name="Support agent",
                    span_type=SpanType.AGENT,
                    status="error",
                    started_at=started_at,
                    ended_at=started_at + timedelta(milliseconds=500),
                    duration_ms=500,
                    input={"question": "Refund?"},
                    output={"answer": "Tool failed"},
                ),
            ),
        ),
    )


def test_create_dataset_creates_one_open_draft_and_is_tenant_scoped() -> None:
    owner = create_user(email="owner@example.com")
    other_owner = create_user(email="other-owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    other_organization, _other_membership = create_test_organization(owner=other_owner, name="Other Org")
    project, _environment = create_project_with_environment(owner=owner, organization=organization)
    other_project, _other_environment = create_project_with_environment(
        owner=other_owner,
        organization=other_organization,
    )

    dataset = create_dataset_with_draft(owner=owner, organization=organization, project=project)
    create_dataset(
        actor=other_owner,
        organization=other_organization,
        project_id=other_project.id,
        name="Other Cases",
        requested_slug="other-cases",
        description="Other",
        tags=[],
        input_schema={},
        output_schema={},
        audit_context=AUDIT_CONTEXT,
    )

    assert dataset.organization == organization
    assert dataset.drafts.count() == 1
    assert [item.id for item in datasets_for_organization(organization=organization, filters=DatasetFilters())] == [
        dataset.id
    ]


def test_viewer_cannot_create_dataset() -> None:
    owner = create_user(email="owner@example.com")
    viewer = create_user(email="viewer@example.com")
    organization, _membership = create_test_organization(owner=owner)
    add_member(organization=organization, user=viewer, role=MembershipRole.VIEWER)
    project, _environment = create_project_with_environment(owner=owner, organization=organization)

    with pytest.raises(DatasetPermissionDenied):
        create_dataset(
            actor=viewer,
            organization=organization,
            project_id=project.id,
            name="Viewer Dataset",
            requested_slug="viewer-dataset",
            description="",
            tags=[],
            input_schema={},
            output_schema={},
            audit_context=AUDIT_CONTEXT,
        )


def test_case_validation_uses_draft_schema() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, _environment = create_project_with_environment(owner=owner, organization=organization)
    dataset = create_dataset_with_draft(owner=owner, organization=organization, project=project)

    with pytest.raises(DatasetValidationError):
        create_draft_case(
            actor=owner,
            organization=organization,
            dataset_id=dataset.id,
            logical_id="missing-question",
            input_value={"message": "no question"},
            expected_behavior="Answer.",
            expected_output={},
            expected_tool_calls=[],
            forbidden_tool_calls=[],
            reference_output={},
            reference_context={},
            metadata={},
            tags=[],
            audit_context=AUDIT_CONTEXT,
        )


def test_publish_creates_immutable_version_and_rejects_duplicate_content() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, _environment = create_project_with_environment(owner=owner, organization=organization)
    dataset = create_dataset_with_draft(owner=owner, organization=organization, project=project)
    create_case(owner=owner, organization=organization, dataset=dataset)

    version = publish_dataset_version(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        audit_context=AUDIT_CONTEXT,
    )

    assert version.version_number == 1
    assert len(version.content_hash) == 64
    assert DatasetVersionCase.objects.filter(version=version).count() == 1
    version.content_hash = "x" * 64
    with pytest.raises(RuntimeError):
        version.save()
    with pytest.raises(RuntimeError):
        DatasetVersion.objects.filter(id=version.id).update(content_hash="y" * 64)

    clone_version_to_draft(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        version_id=version.id,
        audit_context=AUDIT_CONTEXT,
    )
    with pytest.raises(DatasetConflict):
        publish_dataset_version(
            actor=owner,
            organization=organization,
            dataset_id=dataset.id,
            audit_context=AUDIT_CONTEXT,
        )


def test_published_versions_are_protected_from_parent_deletes() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, _environment = create_project_with_environment(owner=owner, organization=organization)
    dataset = create_dataset_with_draft(owner=owner, organization=organization, project=project)
    create_case(owner=owner, organization=organization, dataset=dataset)
    version = publish_dataset_version(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        audit_context=AUDIT_CONTEXT,
    )

    assert DatasetVersion._meta.get_field("organization").remote_field.on_delete is models.PROTECT
    assert DatasetVersion._meta.get_field("dataset").remote_field.on_delete is models.PROTECT
    assert DatasetVersionCase._meta.get_field("organization").remote_field.on_delete is models.PROTECT
    assert DatasetVersionCase._meta.get_field("version").remote_field.on_delete is models.PROTECT
    with pytest.raises(ProtectedError):
        dataset.delete()
    assert DatasetVersion.objects.filter(id=version.id).exists()


def test_update_delete_and_clone_draft_case() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, _environment = create_project_with_environment(owner=owner, organization=organization)
    dataset = create_dataset_with_draft(owner=owner, organization=organization, project=project)
    case = create_case(owner=owner, organization=organization, dataset=dataset)

    updated = update_draft_case(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        case_id=case.id,
        logical_id="case-updated",
        input_value={"question": "Still broken?"},
        expected_behavior="Recover cleanly.",
        expected_output={},
        expected_tool_calls=[],
        forbidden_tool_calls=["timeout"],
        reference_output={},
        reference_context={},
        metadata={},
        tags=["updated"],
        audit_context=AUDIT_CONTEXT,
    )

    assert updated.logical_id == "case-updated"
    version = publish_dataset_version(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        audit_context=AUDIT_CONTEXT,
    )
    draft = clone_version_to_draft(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        version_id=version.id,
        audit_context=AUDIT_CONTEXT,
    )
    assert draft.cases.get().logical_id == "case-updated"


def test_trace_can_become_draft_case() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, environment = create_project_with_environment(owner=owner, organization=organization)
    dataset = create_dataset_with_draft(owner=owner, organization=organization, project=project)
    update_draft_metadata(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        tags=[],
        input_schema={},
        output_schema={},
        audit_context=AUDIT_CONTEXT,
    )
    trace = create_trace(organization=organization, project=project, environment=environment)

    case = create_case_from_trace(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        trace_id=trace.id,
        logical_id="trace-case",
        expected_behavior="Do not fail.",
        tags=["trace"],
        audit_context=AUDIT_CONTEXT,
    )

    assert case.source_trace == trace
    assert case.input == trace.input
    assert case.reference_output == trace.output


def test_jsonl_import_accumulates_row_errors_and_export_is_stable() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, _environment = create_project_with_environment(owner=owner, organization=organization)
    dataset = create_dataset_with_draft(owner=owner, organization=organization, project=project)
    content = (
        '{"logical_id":"case-1","input":{"question":"ok"},"expected_behavior":"Answer"}\n'
        '{"logical_id":"bad","input":{"message":"missing question"},"expected_behavior":"Answer"}\n'
    )
    job = create_import_job(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        uploaded_file=ContentFile(content.encode(), name="cases.jsonl"),
        audit_context=AUDIT_CONTEXT,
    )

    result = process_import_job(job_id=job.id)
    job.refresh_from_db()

    assert result.total_rows == 2
    assert result.imported_rows == 1
    assert job.status == DatasetImportStatus.FAILED
    assert job.row_errors[0]["row"] == 2
    version = publish_dataset_version(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        audit_context=AUDIT_CONTEXT,
    )
    assert '"logical_id":"case-1"' in version_cases_jsonl(version)


def test_import_cleanup_deletes_temp_file() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, _environment = create_project_with_environment(owner=owner, organization=organization)
    dataset = create_dataset_with_draft(owner=owner, organization=organization, project=project)
    job = create_import_job(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        uploaded_file=ContentFile(b"", name="cases.jsonl"),
        audit_context=AUDIT_CONTEXT,
    )
    DatasetImportJob.objects.filter(id=job.id).update(
        status=DatasetImportStatus.COMPLETED,
        cleanup_after=timezone.now() - timedelta(days=1),
    )

    assert cleanup_import_files() == 1
    job.refresh_from_db()
    assert job.storage_path == ""


def test_dataset_list_query_count_is_bounded() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, _environment = create_project_with_environment(owner=owner, organization=organization)
    create_dataset_with_draft(owner=owner, organization=organization, project=project)

    with CaptureQueriesContext(connection) as queries:
        datasets = list(datasets_for_organization(organization=organization, filters=DatasetFilters()))

    assert len(datasets) == 1
    assert len(queries) <= 2
