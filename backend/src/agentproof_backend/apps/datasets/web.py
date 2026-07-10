"""Dataset web views."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from agentproof_backend.apps.accounts.models import User
from agentproof_backend.apps.audit.context import audit_context_from_request
from agentproof_backend.apps.datasets.exceptions import DatasetError
from agentproof_backend.apps.datasets.forms import (
    DatasetCaseForm,
    DatasetCreateForm,
    DatasetDraftMetadataForm,
    DatasetImportForm,
    TraceDatasetCaseForm,
    json_initial,
    tags_initial,
)
from agentproof_backend.apps.datasets.models import DatasetDraftStatus
from agentproof_backend.apps.datasets.selectors import (
    DatasetFilters,
    datasets_for_organization,
    get_dataset_for_organization,
    get_dataset_version,
    get_draft_case,
    get_import_job,
    get_open_draft,
)
from agentproof_backend.apps.datasets.services import (
    clone_version_to_draft,
    create_case_from_trace,
    create_dataset,
    create_draft_case,
    create_import_job,
    delete_draft_case,
    publish_dataset_version,
    update_draft_case,
    update_draft_metadata,
    version_cases_jsonl,
)
from agentproof_backend.apps.datasets.tasks import process_import_job
from agentproof_backend.apps.organizations.models import Membership, MembershipRole, Organization
from agentproof_backend.apps.projects.selectors import projects_for_organization
from agentproof_backend.apps.telemetry.exceptions import TraceNotFound
from agentproof_backend.apps.telemetry.models import Trace


def _current_organization(request: HttpRequest) -> Organization:
    organization = getattr(request, "organization", None)
    if not isinstance(organization, Organization):
        raise PermissionDenied("Select an active organization first.")
    return organization


def _current_user(request: HttpRequest) -> User:
    if not isinstance(request.user, User):
        raise PermissionDenied("Authentication is required.")
    return request.user


def _can_manage_datasets(request: HttpRequest) -> bool:
    membership = getattr(request, "organization_membership", None)
    if not isinstance(membership, Membership):
        return False
    return membership.role in {MembershipRole.OWNER, MembershipRole.ADMINISTRATOR, MembershipRole.DEVELOPER}


def _query_value(request: HttpRequest, key: str) -> str:
    value = request.GET.get(key, "")
    return value.strip()


def _dataset_context(
    *,
    request: HttpRequest,
    dataset_id: str,
    extra: dict[str, Any] | None = None,
    status: int = 200,
) -> HttpResponse:
    organization = _current_organization(request)
    try:
        dataset = get_dataset_for_organization(organization=organization, dataset_id=dataset_id)
    except DatasetError as exc:
        raise Http404("Dataset not found.") from exc

    open_drafts = getattr(dataset, "open_drafts", [])
    draft = open_drafts[0] if open_drafts else None
    context: dict[str, Any] = {
        "dataset": dataset,
        "draft": draft,
        "versions": dataset.versions.all(),
        "can_manage": _can_manage_datasets(request),
        "metadata_form": DatasetDraftMetadataForm.from_draft(data=None, draft=draft) if draft else None,
        "case_form": DatasetCaseForm(),
        "import_form": DatasetImportForm(),
        "imports": draft.import_jobs.all().order_by("-created_at", "id") if draft else (),
    }
    if extra:
        context.update(extra)
    return render(request, "datasets/dataset_detail.html", context, status=status)


def _handle_dataset_error(
    *,
    request: HttpRequest,
    dataset_id: str,
    error: DatasetError,
    extra: dict[str, Any] | None = None,
) -> HttpResponse:
    context = {"form_error": str(error)}
    if extra:
        context.update(extra)
    return _dataset_context(request=request, dataset_id=dataset_id, extra=context, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def dataset_list(request: HttpRequest) -> HttpResponse:
    """Render tenant-scoped datasets and creation form."""

    organization = _current_organization(request)
    projects = tuple(projects_for_organization(organization=organization))
    filters = DatasetFilters(
        project_id=_query_value(request, "project") or None,
        search=_query_value(request, "q"),
        tag=_query_value(request, "tag"),
    )
    form = DatasetCreateForm(request.POST or None)
    form_error = ""

    if request.method == "POST":
        if not _can_manage_datasets(request):
            raise PermissionDenied("Owner, administrator, or developer access is required.")
        if form.is_valid():
            try:
                result = create_dataset(
                    actor=_current_user(request),
                    organization=organization,
                    project_id=form.cleaned_data["project_id"],
                    name=form.cleaned_data["name"],
                    requested_slug=form.cleaned_data.get("slug"),
                    description=form.cleaned_data.get("description", ""),
                    tags=form.cleaned_data["tags"],
                    input_schema=form.cleaned_data["input_schema"],
                    output_schema=form.cleaned_data["output_schema"],
                    audit_context=audit_context_from_request(request),
                )
            except DatasetError as exc:
                form_error = str(exc)
            else:
                return redirect("dataset-web:dataset-detail", dataset_id=result.dataset.id)

    query_params = {
        key: value
        for key, value in {
            "project": filters.project_id,
            "q": filters.search,
            "tag": filters.tag,
        }.items()
        if value
    }
    return render(
        request,
        "datasets/dataset_list.html",
        {
            "datasets": datasets_for_organization(organization=organization, filters=filters),
            "projects": projects,
            "filters": filters,
            "query_string": urlencode(query_params),
            "form": form,
            "form_error": form_error,
            "can_manage": _can_manage_datasets(request),
        },
        status=400 if form_error else 200,
    )


@login_required
def dataset_detail(request: HttpRequest, dataset_id: str) -> HttpResponse:
    """Render a dataset detail page."""

    return _dataset_context(request=request, dataset_id=dataset_id)


@login_required
@require_http_methods(["POST"])
def dataset_draft_update(request: HttpRequest, dataset_id: str) -> HttpResponse:
    """Update metadata on an open draft."""

    if not _can_manage_datasets(request):
        raise PermissionDenied("Owner, administrator, or developer access is required.")
    organization = _current_organization(request)
    dataset = get_dataset_for_organization(organization=organization, dataset_id=dataset_id)
    try:
        draft = get_open_draft(organization=organization, dataset=dataset)
    except DatasetError as exc:
        return _handle_dataset_error(request=request, dataset_id=dataset_id, error=exc)
    form = DatasetDraftMetadataForm.from_draft(data=request.POST, draft=draft)
    if form.is_valid():
        try:
            update_draft_metadata(
                actor=_current_user(request),
                organization=organization,
                dataset_id=dataset_id,
                tags=form.cleaned_data["tags"],
                input_schema=form.cleaned_data["input_schema"],
                output_schema=form.cleaned_data["output_schema"],
                audit_context=audit_context_from_request(request),
            )
        except DatasetError as exc:
            return _handle_dataset_error(
                request=request,
                dataset_id=dataset_id,
                error=exc,
                extra={"metadata_form": form},
            )
        return redirect("dataset-web:dataset-detail", dataset_id=dataset_id)
    return _dataset_context(request=request, dataset_id=dataset_id, extra={"metadata_form": form}, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def dataset_case_create(request: HttpRequest, dataset_id: str) -> HttpResponse:
    """Create a draft case."""

    if not _can_manage_datasets(request):
        raise PermissionDenied("Owner, administrator, or developer access is required.")
    form = DatasetCaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_draft_case(
                actor=_current_user(request),
                organization=_current_organization(request),
                dataset_id=dataset_id,
                logical_id=form.cleaned_data["logical_id"],
                input_value=form.cleaned_data["input"],
                expected_behavior=form.cleaned_data["expected_behavior"],
                expected_output=form.cleaned_data["expected_output"],
                expected_tool_calls=form.cleaned_data["expected_tool_calls"],
                forbidden_tool_calls=form.cleaned_data["forbidden_tool_calls"],
                reference_output=form.cleaned_data["reference_output"],
                reference_context=form.cleaned_data["reference_context"],
                metadata=form.cleaned_data["metadata"],
                tags=form.cleaned_data["tags"],
                audit_context=audit_context_from_request(request),
            )
        except DatasetError as exc:
            return _handle_dataset_error(request=request, dataset_id=dataset_id, error=exc, extra={"case_form": form})
        return redirect("dataset-web:dataset-detail", dataset_id=dataset_id)
    return _dataset_context(request=request, dataset_id=dataset_id, extra={"case_form": form}, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def dataset_case_edit(request: HttpRequest, dataset_id: str, case_id: str) -> HttpResponse:
    """Edit a draft case."""

    if not _can_manage_datasets(request):
        raise PermissionDenied("Owner, administrator, or developer access is required.")
    organization = _current_organization(request)
    try:
        dataset = get_dataset_for_organization(organization=organization, dataset_id=dataset_id)
        draft = get_open_draft(organization=organization, dataset=dataset)
        case = get_draft_case(organization=organization, draft=draft, case_id=case_id)
    except DatasetError as exc:
        raise Http404("Dataset case not found.") from exc

    form = DatasetCaseForm.from_case(data=request.POST if request.method == "POST" else None, case=case)
    if request.method == "POST" and form.is_valid():
        try:
            update_draft_case(
                actor=_current_user(request),
                organization=organization,
                dataset_id=dataset_id,
                case_id=case_id,
                logical_id=form.cleaned_data["logical_id"],
                input_value=form.cleaned_data["input"],
                expected_behavior=form.cleaned_data["expected_behavior"],
                expected_output=form.cleaned_data["expected_output"],
                expected_tool_calls=form.cleaned_data["expected_tool_calls"],
                forbidden_tool_calls=form.cleaned_data["forbidden_tool_calls"],
                reference_output=form.cleaned_data["reference_output"],
                reference_context=form.cleaned_data["reference_context"],
                metadata=form.cleaned_data["metadata"],
                tags=form.cleaned_data["tags"],
                audit_context=audit_context_from_request(request),
            )
        except DatasetError as exc:
            return render(
                request,
                "datasets/case_form.html",
                {"dataset": dataset, "case": case, "form": form, "form_error": str(exc)},
                status=400,
            )
        return redirect("dataset-web:dataset-detail", dataset_id=dataset_id)

    return render(request, "datasets/case_form.html", {"dataset": dataset, "case": case, "form": form})


@login_required
@require_http_methods(["POST"])
def dataset_case_delete(request: HttpRequest, dataset_id: str, case_id: str) -> HttpResponse:
    """Delete a draft case."""

    if not _can_manage_datasets(request):
        raise PermissionDenied("Owner, administrator, or developer access is required.")
    try:
        delete_draft_case(
            actor=_current_user(request),
            organization=_current_organization(request),
            dataset_id=dataset_id,
            case_id=case_id,
            audit_context=audit_context_from_request(request),
        )
    except DatasetError as exc:
        return _handle_dataset_error(request=request, dataset_id=dataset_id, error=exc)
    return redirect("dataset-web:dataset-detail", dataset_id=dataset_id)


@login_required
@require_http_methods(["POST"])
def dataset_import_create(request: HttpRequest, dataset_id: str) -> HttpResponse:
    """Create and enqueue a JSONL import job."""

    if not _can_manage_datasets(request):
        raise PermissionDenied("Owner, administrator, or developer access is required.")
    form = DatasetImportForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            job = create_import_job(
                actor=_current_user(request),
                organization=_current_organization(request),
                dataset_id=dataset_id,
                uploaded_file=form.cleaned_data["file"],
                audit_context=audit_context_from_request(request),
            )
        except DatasetError as exc:
            return _handle_dataset_error(request=request, dataset_id=dataset_id, error=exc, extra={"import_form": form})
        process_import_job.delay(str(job.id))
        return redirect("dataset-web:dataset-import-detail", dataset_id=dataset_id, job_id=job.id)
    return _dataset_context(request=request, dataset_id=dataset_id, extra={"import_form": form}, status=400)


@login_required
def dataset_import_detail(request: HttpRequest, dataset_id: str, job_id: str) -> HttpResponse:
    """Render JSONL import status and row errors."""

    organization = _current_organization(request)
    try:
        dataset = get_dataset_for_organization(organization=organization, dataset_id=dataset_id)
        job = get_import_job(organization=organization, dataset=dataset, job_id=job_id)
    except DatasetError as exc:
        raise Http404("Dataset import job not found.") from exc
    return render(request, "datasets/import_detail.html", {"dataset": dataset, "job": job})


@login_required
@require_http_methods(["POST"])
def dataset_publish(request: HttpRequest, dataset_id: str) -> HttpResponse:
    """Publish the open draft."""

    if not _can_manage_datasets(request):
        raise PermissionDenied("Owner, administrator, or developer access is required.")
    try:
        version = publish_dataset_version(
            actor=_current_user(request),
            organization=_current_organization(request),
            dataset_id=dataset_id,
            audit_context=audit_context_from_request(request),
        )
    except DatasetError as exc:
        return _handle_dataset_error(request=request, dataset_id=dataset_id, error=exc)
    return redirect("dataset-web:dataset-version-detail", dataset_id=dataset_id, version_id=version.id)


@login_required
def dataset_version_detail(request: HttpRequest, dataset_id: str, version_id: str) -> HttpResponse:
    """Render an immutable dataset version."""

    organization = _current_organization(request)
    try:
        dataset = get_dataset_for_organization(organization=organization, dataset_id=dataset_id)
        version = get_dataset_version(organization=organization, dataset=dataset, version_id=version_id)
    except DatasetError as exc:
        raise Http404("Dataset version not found.") from exc
    return render(
        request,
        "datasets/version_detail.html",
        {"dataset": dataset, "version": version, "can_manage": _can_manage_datasets(request)},
    )


@login_required
@require_http_methods(["POST"])
def dataset_version_clone(request: HttpRequest, dataset_id: str, version_id: str) -> HttpResponse:
    """Clone a version into a new draft."""

    if not _can_manage_datasets(request):
        raise PermissionDenied("Owner, administrator, or developer access is required.")
    try:
        clone_version_to_draft(
            actor=_current_user(request),
            organization=_current_organization(request),
            dataset_id=dataset_id,
            version_id=version_id,
            audit_context=audit_context_from_request(request),
        )
    except DatasetError as exc:
        return _handle_dataset_error(request=request, dataset_id=dataset_id, error=exc)
    return redirect("dataset-web:dataset-detail", dataset_id=dataset_id)


@login_required
def dataset_version_export(request: HttpRequest, dataset_id: str, version_id: str) -> HttpResponse:
    """Export a published version as JSONL."""

    organization = _current_organization(request)
    try:
        dataset = get_dataset_for_organization(organization=organization, dataset_id=dataset_id)
        version = get_dataset_version(organization=organization, dataset=dataset, version_id=version_id)
    except DatasetError as exc:
        raise Http404("Dataset version not found.") from exc
    response = HttpResponse(version_cases_jsonl(version), content_type="application/x-ndjson")
    response["Content-Disposition"] = f'attachment; filename="{dataset.slug}-v{version.version_number}.jsonl"'
    return response


@login_required
@require_http_methods(["GET", "POST"])
def trace_case_create(request: HttpRequest, trace_id: str) -> HttpResponse:
    """Create a dataset case from a trace."""

    if not _can_manage_datasets(request):
        raise PermissionDenied("Owner, administrator, or developer access is required.")
    organization = _current_organization(request)
    try:
        trace = Trace.objects.select_related("project", "environment").get(id=trace_id, organization=organization)
    except Trace.DoesNotExist as exc:
        raise Http404("Trace not found.") from exc

    datasets = tuple(
        datasets_for_organization(organization=organization, filters=DatasetFilters(project_id=trace.project_id))
        .filter(drafts__status=DatasetDraftStatus.OPEN)
        .distinct()
    )
    initial_logical_id = slugify(f"{trace.name}-{trace.external_trace_id}", allow_unicode=True)[:120]
    form = TraceDatasetCaseForm(
        request.POST or None,
        initial={
            "logical_id": initial_logical_id,
            "input": json_initial(trace.input),
            "expected_behavior": "",
            "expected_output": json_initial({}),
            "expected_tool_calls": json_initial([]),
            "forbidden_tool_calls": json_initial([]),
            "reference_output": json_initial(trace.output),
            "reference_context": json_initial({"attributes": trace.attributes, "tags": trace.tags}),
            "metadata": json_initial(
                {
                    "source": "trace",
                    "trace_id": str(trace.id),
                    "external_trace_id": trace.external_trace_id,
                    "trace_name": trace.name,
                }
            ),
            "tags": tags_initial(trace.tags),
        },
    )
    form_error = ""
    if request.method == "POST" and form.is_valid():
        try:
            case = create_case_from_trace(
                actor=_current_user(request),
                organization=organization,
                dataset_id=form.cleaned_data["dataset_id"],
                trace_id=trace_id,
                logical_id=form.cleaned_data["logical_id"],
                expected_behavior=form.cleaned_data["expected_behavior"],
                tags=form.cleaned_data["tags"],
                audit_context=audit_context_from_request(request),
            )
        except (DatasetError, TraceNotFound) as exc:
            form_error = str(exc)
        else:
            return redirect("dataset-web:dataset-detail", dataset_id=case.draft.dataset_id)

    return render(
        request,
        "datasets/trace_case_form.html",
        {
            "trace": trace,
            "datasets": datasets,
            "form": form,
            "form_error": form_error,
        },
        status=400 if form_error or (request.method == "POST" and not form.is_valid()) else 200,
    )
