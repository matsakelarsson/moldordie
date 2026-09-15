"""The static files collect under a manifest storage: every reference resolves, hashed.

The files are collected into a temporary directory under Django's manifest storage,
or WhiteNoise's when the project was generated with it, in place of the configured
storage. The deployment's own storage, S3 for one, is not exercised.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from django.core.management import call_command

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import Settings

{%- if cookiecutter.use_whitenoise == 'y' %}
BACKEND = "whitenoise.storage.CompressedManifestStaticFilesStorage"
{%- else %}
BACKEND = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
{%- endif %}
LIBRARY = (
    "css/ui/tokens.css",
    "css/ui/base.css",
    "css/ui/components.css",
    "css/project.css",
    "js/project.js",
)


def test_the_static_files_collect_and_hash(settings: Settings, tmp_path: Path):
    # The suite's MEDIA_ROOT is tmp_path itself, and Django wants the two roots apart
    static_root = tmp_path / "static"
    settings.STATIC_ROOT = str(static_root)
    settings.STORAGES = {**settings.STORAGES, "staticfiles": {"BACKEND": BACKEND}}

    call_command("collectstatic", interactive=False, verbosity=0)

    manifest = json.loads((static_root / "staticfiles.json").read_text())["paths"]
    for path in LIBRARY:
        assert (static_root / manifest[path]).is_file(), path
