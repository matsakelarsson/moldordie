"""The copy of a tree under a renaming, and the ruff pass over it."""

import shutil

import pytest

from {{ cookiecutter.project_slug }}.scaffold.copying import copy_renamed
from {{ cookiecutter.project_slug }}.scaffold.copying import run_formatters


def to_post(text: str) -> str:
    return text.replace("item", "post")


def test_copy_renamed_renames_paths_and_contents_and_skips_byte_code(tmp_path):
    source = tmp_path / "app_template"
    (source / "templates" / "item").mkdir(parents=True)
    (source / "__pycache__").mkdir()
    (source / "templates" / "item" / "item_list.html").write_text("item.name")
    (source / "models.py").write_text("class Item:")
    (source / "__pycache__" / "models.cpython.pyc").write_bytes(b"\0")
    target = tmp_path / "blog"

    written = copy_renamed(source, target, to_post)

    assert sorted(path.as_posix() for path in written) == [
        "models.py",
        "templates/post/post_list.html",
    ]
    assert (target / "models.py").read_text() == "class Item:"
    assert (target / "templates" / "post" / "post_list.html").read_text() == "post.name"
    assert not (target / "__pycache__").exists()


def test_copy_renamed_keeps_an_existing_target(tmp_path):
    (tmp_path / "blog").mkdir()

    with pytest.raises(FileExistsError):
        copy_renamed(tmp_path / "app_template", tmp_path / "blog", to_post)

    assert list((tmp_path / "blog").iterdir()) == []


def test_run_formatters_lays_out_the_python_and_the_templates(tmp_path):
    """Under a configuration of the test's own, found from the directory upwards: the
    imports sorted, the call that no longer fits split one argument per line with its
    trailing comma, and the tag's attributes one per line."""
    if shutil.which("ruff") is None or shutil.which("djlint") is None:
        pytest.skip("ruff or djlint is not on the path")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.ruff]\nline-length = 36\nlint.select = ["COM", "I"]\n'
        '[tool.djlint]\nprofile = "django"\nindent = 2\nmax_attribute_length = 20\n',
    )
    app = tmp_path / "app"
    app.mkdir()
    module = app / "module.py"
    module.write_text(
        "import sys\nimport os\nx = [1,2]\ny = call(a_long_argument, another_one)\n",
    )
    template = app / "page.html"
    template.write_text('<div class="card" id="subscription-card">Name</div>\n')

    assert run_formatters(app) == []
    assert module.read_text() == (
        "import os\nimport sys\n\nx = [1, 2]\n"
        "y = call(\n    a_long_argument,\n    another_one,\n)\n"
    )
    assert template.read_text() == (
        '<div class="card"\n     id="subscription-card">Name</div>\n'
    )


def test_run_formatters_names_the_formatters_it_did_not_find(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    module = tmp_path / "module.py"
    module.write_text("import sys\nimport os\n")

    assert run_formatters(tmp_path) == ["ruff", "djlint"]
    assert module.read_text() == "import sys\nimport os\n"
