"""Traces and metrics over OTLP.

Naming this package imports nothing of the SDK. The variable below lives here for
that reason: ``apps.py`` reads it on the way into every management command, and
only a process that answers it goes on to import ``configure``.
"""

# What tells an app registry that this process serves something. A start script sets
# it for the processes that have no hook of their own to start from.
COMPONENT_VARIABLE = "DJANGO_TELEMETRY_COMPONENT"
