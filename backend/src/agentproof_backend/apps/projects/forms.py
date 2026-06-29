"""Forms for project web pages."""

from django import forms

from agentproof_backend.apps.projects.models import CaptureMode, EnvironmentType


class ProjectForm(forms.Form):
    """Create or update a project"""

    name = forms.CharField(max_length=150)
    slug = forms.SlugField(max_length=63, required=False)
    description = forms.CharField(required=False, widget=forms.Textarea)
    capture_mode = forms.ChoiceField(choices=CaptureMode.choices)
    retention_days = forms.IntegerField(min_value=1)


class EnvironmentForm(forms.Form):
    """Create or update an environment."""

    name = forms.CharField(max_length=150)
    slug = forms.SlugField(max_length=63, required=False)
    environment_type = forms.ChoiceField(choices=EnvironmentType.choices)
    capture_mode_override = forms.ChoiceField(
        choices=(("", "Use project default"), *CaptureMode.choices),
        required=False,
    )
    retention_days_override = forms.IntegerField(min_value=1, required=False)
