"""The UI library's Python side.

The template filters that write a component's attributes and URLs, the palettes with
their contrast arithmetic, the theme resolved for each request and served as a
stylesheet, and the showcase, registered under DEBUG (docs/frontend.rst).
"""

from __future__ import annotations

from django.apps import AppConfig
from django.core import checks
from django.utils.translation import gettext_lazy as _

from .checks import check_theme_settings


class UiConfig(AppConfig):
    name = "{{ cookiecutter.project_slug }}.ui"
    verbose_name = _("UI")

    def ready(self) -> None:
        checks.register(check_theme_settings)
