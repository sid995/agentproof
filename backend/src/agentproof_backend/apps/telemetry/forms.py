"""Forms for trace explorer web views."""

from django import forms


class TraceAnnotationForm(forms.Form):
    """Create a human-authored trace annotation."""

    annotation_type = forms.CharField(max_length=80)
    comment = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
