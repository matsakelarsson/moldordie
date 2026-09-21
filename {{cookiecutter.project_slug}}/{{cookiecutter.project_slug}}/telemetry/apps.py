"""The app that starts the exporters of a process that has no hook to start from.

``config/settings/base.py`` installs it in every environment, because what decides
whether anything is exported is the configured endpoint rather than the environment
the process runs in. ``ready`` runs for every management command, so this one starts
the exporters only where the environment says the process serves something
(``telemetry/configure.py``).
"""

import os

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from .configure import COMPONENT_VARIABLE
from .configure import configure


class TelemetryConfig(AppConfig):
    name = "{{ cookiecutter.project_slug }}.telemetry"
    verbose_name = _("Telemetry")

    def ready(self) -> None:
        component = os.environ.get(COMPONENT_VARIABLE, "")
        if component:
            configure(component)
