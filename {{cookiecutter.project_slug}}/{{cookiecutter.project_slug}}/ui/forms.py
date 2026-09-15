"""The showcase's forms: a sample with nothing behind it, the filter of its results and
the theme preview (docs/frontend.rst)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .contrast import HEX_COLOUR
from .palettes import BRAND_TOKENS
from .palettes import PALETTES
from .palettes import SETS
from .themes import MODES
from .themes import InvalidThemeError
from .themes import servable_theme

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .themes import Theme

PLANS = [("starter", "Starter"), ("team", "Team"), ("enterprise", "Enterprise")]
MAX_SEATS = 50
# A team plan is shared, so it takes more than one seat
TEAM_SEATS = 2


class SampleForm(forms.Form):
    """A form with nothing behind it, for the showcase: a field of each kind the field
    component renders, help text, a disabled field and a rule across two fields."""

    name = forms.CharField(
        label="Name",
        max_length=40,
        help_text="As it should appear on the invoice.",
    )
    email = forms.EmailField(label="Email", required=False)
    plan = forms.ChoiceField(
        label="Plan",
        choices=PLANS,
        initial="starter",
        widget=forms.RadioSelect,
    )
    seats = forms.IntegerField(
        label="Seats",
        min_value=1,
        max_value=MAX_SEATS,
        initial=1,
    )
    notes = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    reference = forms.CharField(
        label="Reference",
        required=False,
        disabled=True,
        initial="SAMPLE-042",
        help_text="Disabled: the form keeps this value whatever is submitted.",
    )
    terms = forms.BooleanField(label="I accept the terms")

    def clean(self) -> dict[str, Any] | None:
        cleaned_data = super().clean()
        if cleaned_data and cleaned_data.get("plan") == "team":
            seats = cleaned_data.get("seats")
            if seats is not None and seats < TEAM_SEATS:
                msg = "A team plan needs at least two seats."
                raise ValidationError(msg, code="team_seats")
        return cleaned_data

    def summary(self) -> str:
        """What a valid submission asked for, as a sentence."""
        data = self.cleaned_data
        plan = dict(PLANS)[data["plan"]]
        return f"{data['name']} chose the {plan} plan; seats: {data['seats']}."


class FilterForm(forms.Form):
    """The filter of the showcase's results: a word to find in a task."""

    q = forms.CharField(label="Filter the tasks", required=False, max_length=40)


def colour_field(set_name: str, token: str) -> str:
    """The name of the preview form's field for ``token`` in ``set_name``."""
    return f"{set_name}_{token.replace('-', '_')}"


def validate_colour(value: str) -> None:
    """A ``#RRGGBB`` colour, the only kind a theme holds."""
    if not HEX_COLOUR.fullmatch(value):
        msg = "Enter a colour as #RRGGBB."
        raise ValidationError(msg, code="colour")


class PreviewForm(forms.Form):
    """A theme to preview: a palette, a mode and, for each set, colours for the tokens a
    brand may override, a blank one keeping the colour beneath it.

    ``beneath`` is the theme the colours apply over, a palette with ``UI_BRAND``; its
    colours are the fields' placeholders. The result is validated as a whole, over the
    palette and ``UI_BRAND``, the way ``resolve_theme`` resolves it.
    """

    palette = forms.ChoiceField(
        label="Palette",
        choices=[(name, name) for name in PALETTES],
    )
    mode = forms.ChoiceField(
        label="Mode",
        choices=[(mode, mode) for mode in MODES],
        widget=forms.RadioSelect,
    )

    def __init__(self, *args: Any, beneath: Theme, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for set_name in SETS:
            for token in BRAND_TOKENS:
                widget = forms.TextInput(
                    attrs={
                        "placeholder": beneath.colours(set_name)[token],
                        "autocomplete": "off",
                        "spellcheck": "false",
                    },
                )
                self.fields[colour_field(set_name, token)] = forms.CharField(
                    label=token,
                    required=False,
                    validators=[validate_colour],
                    widget=widget,
                )

    @staticmethod
    def initial_for(theme: Theme, preview: Mapping[str, Any] | None) -> dict[str, str]:
        """The form's initial values: the theme's palette and mode, and the colours of
        the preview it came from, if any."""
        initial = {"palette": theme.palette, "mode": theme.mode}
        for set_name in SETS:
            colours = preview.get(set_name, {}) if preview else {}
            for token, colour in colours.items():
                initial[colour_field(set_name, token)] = colour
        return initial

    @property
    def light_fields(self) -> list[forms.BoundField]:
        """The colour fields of the light set."""
        return [self[colour_field("light", token)] for token in BRAND_TOKENS]

    @property
    def dark_fields(self) -> list[forms.BoundField]:
        """The colour fields of the dark set."""
        return [self[colour_field("dark", token)] for token in BRAND_TOKENS]

    @property
    def shows_colours(self) -> bool:
        """Whether the colour fields start open: one holds a colour or an error."""
        fields = self.light_fields + self.dark_fields
        return any(field.value() or field.errors for field in fields)

    def clean(self) -> dict[str, Any] | None:
        cleaned_data = super().clean()
        if self.errors or not cleaned_data:
            return cleaned_data
        try:
            servable_theme(
                cleaned_data["palette"],
                cleaned_data["mode"],
                settings.UI_BRAND,
                self.colours(),
            )
        except InvalidThemeError as error:
            errors = [ValidationError(str(p), code="theme") for p in error.problems]
            raise ValidationError(errors) from error
        return cleaned_data

    def colours(self) -> dict[str, dict[str, str]]:
        """The colours given, per set, the blank ones left out."""
        return {
            set_name: {
                token: value
                for token in BRAND_TOKENS
                if (value := self.cleaned_data.get(colour_field(set_name, token)))
            }
            for set_name in SETS
        }

    def preview(self) -> dict[str, Any]:
        """The preview to keep in the session: palette, mode and the colours given."""
        return {
            "palette": self.cleaned_data["palette"],
            "mode": self.cleaned_data["mode"],
            **self.colours(),
        }
