"""The app that starts the exporters of a process that has no hook to start from.

``config/settings/base.py`` installs it in every environment, because what decides
whether anything is exported is the configured endpoint rather than the environment
the process runs in. ``ready`` runs for every management command, so this one starts
the exporters only where the environment says the process serves something, and
imports what would start them no sooner (``telemetry/configure.py``).
"""

import os

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from . import COMPONENT_VARIABLE


class TelemetryConfig(AppConfig):
    name = "{{ cookiecutter.project_slug }}.telemetry"
    verbose_name = _("Telemetry")

    def ready(self) -> None:
        component = os.environ.get(COMPONENT_VARIABLE, "")
        if not component:
            return
        # Imported here rather than above: this runs for every management command,
        # and the SDK and its instrumentations cost the best part of a second to
        # import, which a command that exports nothing should not be paying.
        from .configure import configure  # noqa: PLC0415

        configure(component)
