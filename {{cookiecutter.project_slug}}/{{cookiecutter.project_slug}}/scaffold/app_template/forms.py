"""The form that creates or changes a record, and the filter of the list."""

from django import forms
from django.utils.translation import gettext_lazy as _

from {{ cookiecutter.project_slug }}.scaffold.app_template.models import Item


class ItemForm(forms.ModelForm[Item]):
    class Meta:
        model = Item
        fields = ["name", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class FilterForm(forms.Form):
    q = forms.CharField(
        label=_("Filter"),
        required=False,
        widget=forms.TextInput(attrs={"type": "search", "autocomplete": "off"}),
    )
