{%- if cookiecutter.username_type == "email" -%}
from typing import ClassVar

{% endif -%}
from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
{%- if cookiecutter.username_type == "email" %}
from django.db.models import EmailField
{%- endif %}
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
{%- if cookiecutter.username_type == "email" %}

from .managers import UserManager
{%- endif %}


class User(AbstractUser):
    """
    Default custom user model for {{ cookiecutter.project_name | string_escape }}.
    A field to fill in at signup needs a signup form named in allauth's
    ``ACCOUNT_FORMS`` setting.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    {%- if cookiecutter.username_type == "email" %}
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()
    {%- endif %}

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        {%- if cookiecutter.username_type == "email" %}
        return reverse("users:detail", kwargs={"pk": self.id})
        {%- else %}
        return reverse("users:detail", kwargs={"username": self.username})
        {%- endif %}

    # AbstractUser builds these from first_name and last_name, which this model drops
    def get_full_name(self) -> str:
        return self.name.strip()

    def get_short_name(self) -> str:
        return self.name.strip()

    @property
    def display_name(self) -> str:
        """The name, or a fallback that never shows the email address."""
        {%- if cookiecutter.username_type == "email" %}
        return self.name.strip() or str(_("User"))
        {%- else %}
        return self.name.strip() or self.username
        {%- endif %}
