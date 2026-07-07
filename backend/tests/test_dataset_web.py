"""Web tests for Phase 11 datasets."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import AuditContext
from agentproof_backend.apps.datasets.models import DatasetDraftCase, DatasetImportJob, DatasetVersion
from agentproof_backend.apps.datasets.services import create_dataset, create_draft_case
from agentproof_backend.apps.organizations.constants import ACTIVE_ORGANIZATION_SESSION_KEY
from agentproof_backend.apps.projects.models import CaptureMode, Environment, Project
from agentproof_backend.apps.projects.services import create_project
from tests.organization_helpers import create_test_organization, create_user
from tests.test_datasets import create_trace

pytestmark = pytest.mark.django_db

AUDIT_CONTEXT = AuditContext(
    request_id="phase-eleven-web-test",
    source_ip="127.0.0.1",
    user_agent="pytest",
)


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_login(user)
    return client


def set_active_organization(*, client: APIClient, organization_id: object) -> None:
    session = client.session
    session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(organization_id)
    session.save()


def create_project_with_environment(*, owner: User, organization: object) -> tuple[Project, Environment]:
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


def create_dataset_with_case(*, owner: User, organization: object, project: Project) -> object:
    dataset = create_dataset(
        actor=owner,
        organization=organization,
        project_id=project.id,
        name="Regression Cases",
        requested_slug="regression-cases",
        description="",
        tags=[],
        input_schema={},
        output_schema={},
        audit_context=AUDIT_CONTEXT,
    ).dataset
    create_draft_case(
        actor=owner,
        organization=organization,
        dataset_id=dataset.id,
        logical_id="case-1",
        input_value={"question": "Refund?"},
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
    return dataset


def test_dataset_list_requires_login() -> None:
    response = APIClient().get("/datasets/")

    assert response.status_code == 302
    assert "/api-auth/login/" in response["Location"]


def test_dataset_pages_create_publish_clone_and_export() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, _environment = create_project_with_environment(owner=owner, organization=organization)
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.post(
        "/datasets/",
        {
            "project_id": str(project.id),
            "name": "Regression Cases",
            "slug": "regression-cases",
            "description": "",
            "tags": "support",
            "input_schema": "{}",
            "output_schema": "{}",
        },
    )

    assert response.status_code == 302
    dataset_id = response["Location"].rstrip("/").split("/")[-1]

    response = client.post(
        f"/datasets/{dataset_id}/cases/new/",
        {
            "logical_id": "case-1",
            "input": '{"question":"Refund?"}',
            "expected_behavior": "Answer clearly.",
            "expected_output": "{}",
            "expected_tool_calls": "[]",
            "forbidden_tool_calls": "[]",
            "reference_output": "{}",
            "reference_context": "{}",
            "metadata": "{}",
            "tags": "support",
        },
    )
    assert response.status_code == 302
    assert DatasetDraftCase.objects.filter(draft__dataset_id=dataset_id, logical_id="case-1").exists()

    response = client.post(f"/datasets/{dataset_id}/publish/")
    assert response.status_code == 302
    version = DatasetVersion.objects.get(dataset_id=dataset_id)

    response = client.get(f"/datasets/{dataset_id}/versions/{version.id}/export/")
    assert response.status_code == 200
    assert b'"logical_id":"case-1"' in response.content

    response = client.post(f"/datasets/{dataset_id}/versions/{version.id}/clone/")
    assert response.status_code == 302
    assert DatasetDraftCase.objects.filter(draft__dataset_id=dataset_id).count() == 2


def test_trace_add_to_dataset_flow_creates_case() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, environment = create_project_with_environment(owner=owner, organization=organization)
    dataset = create_dataset_with_case(owner=owner, organization=organization, project=project)
    trace = create_trace(organization=organization, project=project, environment=environment)
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)

    response = client.get(f"/traces/{trace.id}/")
    assert response.status_code == 200
    assert b"Add to dataset" in response.content

    response = client.post(
        f"/datasets/from-trace/{trace.id}/",
        {
            "dataset_id": str(dataset.id),
            "logical_id": "trace-case",
            "input": "{}",
            "expected_behavior": "Do not fail.",
            "expected_output": "{}",
            "expected_tool_calls": "[]",
            "forbidden_tool_calls": "[]",
            "reference_output": "{}",
            "reference_context": "{}",
            "metadata": "{}",
            "tags": "trace",
        },
    )

    assert response.status_code == 302
    assert DatasetDraftCase.objects.filter(draft__dataset=dataset, source_trace=trace, logical_id="trace-case").exists()


def test_import_status_page_renders_row_errors() -> None:
    owner = create_user(email="owner@example.com")
    organization, _membership = create_test_organization(owner=owner)
    project, _environment = create_project_with_environment(owner=owner, organization=organization)
    dataset = create_dataset(
        actor=owner,
        organization=organization,
        project_id=project.id,
        name="Regression Cases",
        requested_slug="regression-cases",
        description="",
        tags=[],
        input_schema={"type": "object", "required": ["question"]},
        output_schema={},
        audit_context=AUDIT_CONTEXT,
    ).dataset
    client = authenticated_client(owner)
    set_active_organization(client=client, organization_id=organization.id)
    uploaded = SimpleUploadedFile(
        "cases.jsonl",
        b'{"logical_id":"bad","input":{"message":"missing"},"expected_behavior":"Answer"}\n',
        content_type="application/x-ndjson",
    )

    response = client.post(f"/datasets/{dataset.id}/imports/", {"file": uploaded})

    assert response.status_code == 302
    job = DatasetImportJob.objects.get(draft__dataset=dataset)
    response = client.get(f"/datasets/{dataset.id}/imports/{job.id}/")
    assert response.status_code == 200
    assert b"Row 1" in response.content
