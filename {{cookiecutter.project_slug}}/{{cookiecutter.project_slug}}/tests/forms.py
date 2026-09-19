"""The forms the renderer tests render: the fields the field template tells apart, and
one widget of each kind the widget templates give a class."""

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


class WidgetsForm(forms.Form):
    text = forms.CharField()
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    number = forms.IntegerField()
    day = forms.DateField()
    level = forms.IntegerField(widget=forms.NumberInput(attrs={"type": "range"}))
    notes = forms.CharField(widget=forms.Textarea)
    colour = forms.ChoiceField(choices=[("Warm", [("r", "Red")]), ("b", "Blue")])
    colours = forms.MultipleChoiceField(choices=[("r", "Red"), ("b", "Blue")])
    agree = forms.BooleanField()
    notify = forms.BooleanField(widget=forms.CheckboxInput(attrs={"class": "toggle"}))
    size = forms.ChoiceField(
        choices=[("s", "Small"), ("l", "Large")],
        widget=forms.RadioSelect,
    )
    toppings = forms.MultipleChoiceField(
        choices=[("Cheese", [("c", "Cheddar")]), ("o", "Olives")],
        widget=forms.CheckboxSelectMultiple,
    )
    upload = forms.FileField(widget=forms.FileInput)
    avatar = forms.FileField(required=False)
    tagged = forms.CharField(widget=forms.TextInput(attrs={"class": "validator"}))
