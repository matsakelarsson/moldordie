"""The forms of the examples page: one widget of each kind the form templates style,
validated on the server, and the filter of the task table. Nothing is saved."""

from __future__ import annotations

from typing import Any

from django import forms

TEAM_PLAN = "team"
SMALLEST_TEAM = 2


class ExampleForm(forms.Form):
    name = forms.CharField(help_text="How the invitation addresses you.")
    email = forms.EmailField(required=False)
    plan = forms.ChoiceField(
        choices=[("solo", "Solo"), (TEAM_PLAN, "Team")],
        widget=forms.RadioSelect,
        initial="solo",
    )
    seats = forms.IntegerField(min_value=1, initial=1)
    contact = forms.ChoiceField(
        label="Preferred contact",
        choices=[("", "No preference"), ("email", "Email"), ("phone", "Phone")],
        required=False,
    )
    topics = forms.MultipleChoiceField(
        choices=[("news", "News"), ("tips", "Tips"), ("events", "Events")],
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    reference = forms.CharField(initial="EX-2026", disabled=True, required=False)
    newsletter = forms.BooleanField(
        label="Send me the newsletter",
        widget=forms.CheckboxInput(attrs={"class": "toggle"}),
        required=False,
    )
    terms = forms.BooleanField(label="I accept the terms")

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        seats = cleaned.get("seats")
        if cleaned.get("plan") == TEAM_PLAN and seats and seats < SMALLEST_TEAM:
            self.add_error("seats", "A team has at least two seats.")
        return cleaned

    def summary(self) -> str:
        """What a valid form asked for, in a sentence."""
        data = self.cleaned_data
        return f"{data['name']}: the {data['plan']} plan with {data['seats']} seat(s)."


class FilterForm(forms.Form):
    q = forms.CharField(
        label="Filter the tasks",
        required=False,
        widget=forms.TextInput(attrs={"type": "search", "autocomplete": "off"}),
    )
