"""``startapp``: a new app copied from the app template under the names given, and the
names it refuses."""

from __future__ import annotations

import shutil
import subprocess
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from django.conf import settings as project_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.template import engines

from {{ cookiecutter.project_slug }}.scaffold.names import Names
from {{ cookiecutter.project_slug }}.scaffold.names import rename

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import Settings

PACKAGE = "{{ cookiecutter.project_slug }}"


@pytest.fixture
def apps_dir(settings: Settings, tmp_path: Path) -> Path:
    """The package directory of a project of its own under ``tmp_path``, with this
    project's ruff configuration, so the copy is sorted and formatted as here."""
    shutil.copy(project_settings.BASE_DIR / "pyproject.toml", tmp_path)
    directory = tmp_path / PACKAGE
    directory.mkdir()
    settings.BASE_DIR = tmp_path
    settings.APPS_DIR = directory
    return directory


def startapp(*args: str) -> str:
    out = StringIO()
    call_command("startapp", *args, stdout=out)
    return out.getvalue()


def files_of(app: Path) -> set[str]:
    return {p.relative_to(app).as_posix() for p in app.rglob("*") if p.is_file()}


def test_a_new_app_is_copied_under_its_names(apps_dir: Path):
    out = startapp("blog", "--model", "Post")

    app = apps_dir / "blog"
    files = files_of(app)
    assert {"apps.py", "models.py", "migrations/0001_initial.py"} <= files
    assert {"tests/test_views.py", "templates/blog/post_list.html"} <= files
    assert f'name = "{PACKAGE}.blog"' in (app / "apps.py").read_text()
    assert "class Post(models.Model)" in (app / "models.py").read_text()
    assert 'app_name = "blog"' in (app / "urls.py").read_text()
    # Renaming the copy again changes nothing: no placeholder is left in it
    for path in (path for path in app.rglob("*") if path.is_file()):
        text = path.read_text()
        assert rename(text, Names(app="blog", model="Post")) == text, path
    assert f'"{PACKAGE}.blog" to LOCAL_APPS' in out


def test_the_copy_is_python_and_templates_the_project_parses(apps_dir: Path):
    startapp("blog")

    app = apps_dir / "blog"
    for path in app.rglob("*.py"):
        compile(path.read_text(), str(path), "exec")
    for path in app.rglob("*.html"):
        engines["django"].from_string(path.read_text())


def test_the_copy_passes_ruff_whatever_its_name_sorts_after(apps_dir: Path):
    """``zoo`` sorts after every module of the package its files import from, where
    ``app_template`` sorts before; the copy's imports are sorted for its own name."""
    ruff = shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff is not on the path")
    startapp("zoo", "--model", "Animal")

    app = apps_dir / "zoo"
    check = subprocess.run(  # noqa: S603
        [ruff, "check", app],
        capture_output=True,
        text=True,
        check=False,
    )
    formatted = subprocess.run(  # noqa: S603
        [ruff, "format", "--check", app],
        capture_output=True,
        text=True,
        check=False,
    )

    assert check.returncode == 0, check.stdout
    assert formatted.returncode == 0, formatted.stdout


def test_the_model_is_the_apps_name_in_capwords_unless_given(apps_dir: Path):
    startapp("blog_posts")

    models = (apps_dir / "blog_posts" / "models.py").read_text()
    assert "class BlogPosts(models.Model)" in models


def test_a_name_that_holds_a_placeholder_word_is_renamed_once(apps_dir: Path):
    startapp("item_tracker", "--model", "Tracker")

    app = apps_dir / "item_tracker"
    assert f'name = "{PACKAGE}.item_tracker"' in (app / "apps.py").read_text()
    assert "class ItemTrackerConfig" in (app / "apps.py").read_text()
    assert 'app_name = "item_tracker"' in (app / "urls.py").read_text()
    assert "class Tracker(models.Model)" in (app / "models.py").read_text()


def test_the_formatters_not_found_are_said(apps_dir: Path, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PATH", str(tmp_path))

    out = startapp("blog")

    assert "ruff is not on the path" in out
    assert "djlint is not on the path" in out
    assert "models.py" in files_of(apps_dir / "blog")


@pytest.mark.parametrize(
    ("args", "refused"),
    [
        (("Blog",), "'Blog' is not a lowercase identifier"),
        (("1blog",), "'1blog' is not a lowercase identifier"),
        (("class",), "'class' is not a lowercase identifier"),
        (("blog", "--model", "post"), "'post' is not in CapWords"),
        (("blog", "--model", "Blog Post"), "'Blog Post' is not in CapWords"),
        # The test helper that reads a page, and the filter's form
        (("blog", "--model", "Page"), "'Page' cannot name a model: .* has page"),
        (("blog", "--model", "Filter"), "the app template has FilterForm"),
    ],
)
def test_a_name_that_cannot_name_an_app_or_a_model_is_refused(
    apps_dir: Path,
    args: tuple[str, ...],
    refused: str,
):
    with pytest.raises(CommandError, match=refused):
        startapp(*args)

    assert list(apps_dir.iterdir()) == []


def test_a_module_of_the_package_is_not_shadowed(apps_dir: Path):
    (apps_dir / "htmx.py").write_text("")

    with pytest.raises(CommandError, match="'htmx' is the name of a module"):
        startapp("htmx")

    assert not (apps_dir / "htmx").exists()


def test_an_existing_directory_is_left_alone(apps_dir: Path):
    (apps_dir / "blog").mkdir()

    with pytest.raises(CommandError, match="exists already"):
        startapp("blog")

    assert list((apps_dir / "blog").iterdir()) == []
