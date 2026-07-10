"""Forms for dataset web pages."""

import json
from collections.abc import Mapping
from typing import Any

from django import forms

from agentproof_backend.apps.datasets.models import DatasetDraftCase


class JSONFormField(forms.CharField):
    """Textarea field that returns parsed JSON."""

    def __init__(self, *args: Any, empty_value: Any, **kwargs: Any) -> None:
        self.empty_value = empty_value
        kwargs.setdefault("widget", forms.Textarea(attrs={"rows": 5}))
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def to_python(self, value: object) -> Any:
        if value in self.empty_values:
            return self.empty_value

        if not isinstance(value, str):
            raise forms.ValidationError("Enter valid JSON.")

        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Enter valid JSON: {exc.msg}.") from exc


class TagsFormField(forms.Field):
    """Comma-separated tags field."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("required", False)
        kwargs.setdefault("help_text", "Comma-separated tags.")
        kwargs.setdefault("widget", forms.TextInput)
        super().__init__(*args, **kwargs)

    def to_python(self, value: object) -> list[str]:
        if value in self.empty_values:
            return []

        if not isinstance(value, str):
            raise forms.ValidationError("Enter comma-separated tags.")

        return [tag.strip() for tag in value.split(",") if tag.strip()]


def json_initial(value: object) -> str:
    """Return pretty JSON for form initial values."""

    return json.dumps(value, indent=2, sort_keys=True)


def tags_initial(value: object) -> str:
    """Return comma-separated tags for form initial values."""

    if not isinstance(value, list):
        return ""
    return ", ".join(str(tag) for tag in value)


class DatasetCreateForm(forms.Form):
    """Create a dataset and its first draft."""

    project_id = forms.UUIDField()
    name = forms.CharField(max_length=150)
    slug = forms.SlugField(max_length=63, required=False, allow_unicode=True)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    tags = TagsFormField()
    input_schema = JSONFormField(empty_value={})
    output_schema = JSONFormField(empty_value={})


class DatasetDraftMetadataForm(forms.Form):
    """Edit version-affecting draft metadata."""

    tags = TagsFormField()
    input_schema = JSONFormField(empty_value={})
    output_schema = JSONFormField(empty_value={})

    @classmethod
    def from_draft(cls, *, data: Mapping[str, Any] | None, draft: object) -> "DatasetDraftMetadataForm":
        return cls(
            data=data,
            initial={
                "tags": tags_initial(getattr(draft, "tags", [])),
                "input_schema": json_initial(getattr(draft, "input_schema", {})),
                "output_schema": json_initial(getattr(draft, "output_schema", {})),
            },
        )


class DatasetCaseForm(forms.Form):
    """Create or update a draft test case."""

    logical_id = forms.SlugField(max_length=120, allow_unicode=True)
    input = JSONFormField(empty_value={})
    expected_behavior = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    expected_output = JSONFormField(empty_value={})
    expected_tool_calls = JSONFormField(empty_value=[])
    forbidden_tool_calls = JSONFormField(empty_value=[])
    reference_output = JSONFormField(empty_value={})
    reference_context = JSONFormField(empty_value={})
    metadata = JSONFormField(empty_value={})
    tags = TagsFormField()

    @classmethod
    def from_case(cls, *, data: Mapping[str, Any] | None, case: DatasetDraftCase) -> "DatasetCaseForm":
        return cls(
            data=data,
            initial={
                "logical_id": case.logical_id,
                "input": json_initial(case.input),
                "expected_behavior": case.expected_behavior,
                "expected_output": json_initial(case.expected_output),
                "expected_tool_calls": json_initial(case.expected_tool_calls),
                "forbidden_tool_calls": json_initial(case.forbidden_tool_calls),
                "reference_output": json_initial(case.reference_output),
                "reference_context": json_initial(case.reference_context),
                "metadata": json_initial(case.metadata),
                "tags": tags_initial(case.tags),
            },
        )


class TraceDatasetCaseForm(DatasetCaseForm):
    """Create a draft case from a trace."""

    dataset_id = forms.UUIDField()


class DatasetImportForm(forms.Form):
    """Upload JSONL cases into a draft."""

    file = forms.FileField()
