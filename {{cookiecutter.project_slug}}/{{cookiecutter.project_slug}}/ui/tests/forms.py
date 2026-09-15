"""The form the field tests render: one field of each kind the component handles."""

from django import forms


class SampleForm(forms.Form):
    name = forms.CharField(label="Name", help_text="How to address you.")
    agree = forms.BooleanField(label="Agree", required=False)
    flavour = forms.ChoiceField(
        label="Flavour",
        choices=[("a", "Apple"), ("b", "Berry")],
        widget=forms.RadioSelect,
        help_text="Pick one.",
    )
    token = forms.CharField(widget=forms.HiddenInput, required=False)
    custom = forms.CharField(
        label="Custom",
        required=False,
        widget=forms.TextInput(attrs={"id": "custom-id"}),
    )
