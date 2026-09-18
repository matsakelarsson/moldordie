"""The stylesheet builds, and the static files collect under a manifest storage.

Tailwind's CLI builds the stylesheet into a temporary directory that stands first among
the static directories, so the working tree stays as it was and a stylesheet the watcher
left there is not the one collected. Everything is then collected into a second
temporary directory under Django's manifest storage, or WhiteNoise's when the project
was generated with it, in place of the configured storage: every reference has to
resolve, hashed. The deployment's own storage, S3 for one, is not exercised. The first
run downloads the CLI that TAILWIND_CLI_VERSION names into ``.django_tailwind_cli/``,
which needs the network once.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from django.core.management import call_command
from django.templatetags.static import static

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


def test_the_stylesheet_builds_and_the_static_files_collect(
    settings: Settings,
    tmp_path: Path,
):
    # The suite's MEDIA_ROOT is tmp_path itself, and Django wants the roots apart
    build_dir = tmp_path / "build"
    static_root = tmp_path / "static"
    # The CLI writes TAILWIND_CLI_DIST_CSS under the first static directory
    settings.STATICFILES_DIRS = [str(build_dir), *settings.STATICFILES_DIRS]
    settings.STATIC_ROOT = str(static_root)
    settings.STORAGES = {**settings.STORAGES, "staticfiles": {"BACKEND": BACKEND}}
    stylesheet = settings.TAILWIND_CLI_DIST_CSS

    call_command("tailwind", "build")
    call_command("collectstatic", interactive=False, verbosity=0)

    manifest = json.loads((static_root / "staticfiles.json").read_text())["paths"]
    for path in (*LIBRARY, stylesheet):
        assert (static_root / manifest[path]).is_file(), path
    # What the tailwind_css tag hands to the static tag resolves through the manifest
    assert static(stylesheet) == f"{settings.STATIC_URL}{manifest[stylesheet]}"
