"""The copy of a tree under a renaming, and the formatters' pass over it."""

import shutil

import pytest

from {{ cookiecutter.project_slug }}.scaffold.copying import copy_renamed
from {{ cookiecutter.project_slug }}.scaffold.copying import run_formatters


def to_post(text: str) -> str:
    return text.replace("item", "post")


@pytest.fixture
def source(tmp_path):
    """A tree with byte code and a hidden file, which the copy leaves, and a file that
    is not text, which it copies as it is."""
    source = tmp_path / "app_template"
    (source / "templates" / "item").mkdir(parents=True)
    (source / "__pycache__").mkdir()
    (source / "templates" / "item" / "item_list.html").write_text("item.name")
    (source / "models.py").write_text("class Item:")
    (source / "logo.png").write_bytes(b"\x89PNG\xff\xfe")
    (source / ".DS_Store").write_bytes(b"\0")
    (source / "__pycache__" / "models.cpython.pyc").write_bytes(b"\0")
    return source


def test_copy_renamed_renames_paths_and_contents(source, tmp_path):
    target = tmp_path / "blog"

    written = copy_renamed(source, target, to_post)

    assert sorted(path.as_posix() for path in written) == [
        "logo.png",
        "models.py",
        "templates/post/post_list.html",
    ]
    assert (target / "models.py").read_text() == "class Item:"
    assert (target / "templates" / "post" / "post_list.html").read_text() == "post.name"
    assert (target / "logo.png").read_bytes() == b"\x89PNG\xff\xfe"
    assert not (target / "__pycache__").exists()
    assert not (target / ".DS_Store").exists()


def test_copy_renamed_keeps_an_existing_target(source, tmp_path):
    (tmp_path / "blog").mkdir()

    with pytest.raises(FileExistsError):
        copy_renamed(source, tmp_path / "blog", to_post)

    assert list((tmp_path / "blog").iterdir()) == []


def test_a_copy_that_fails_leaves_nothing_behind(source, tmp_path):
    def failing(text: str) -> str:
        # The template, which is copied after models.py
        if "item.name" in text:
            raise ValueError(text)
        return to_post(text)

    with pytest.raises(ValueError, match=r"item\.name"):
        copy_renamed(source, tmp_path / "blog", failing)

    assert not (tmp_path / "blog").exists()


def test_a_missing_source_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="nowhere"):
        copy_renamed(tmp_path / "nowhere", tmp_path / "blog", to_post)

    assert not (tmp_path / "blog").exists()


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


def test_run_formatters_says_which_formatters_it_did_not_find(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    module = tmp_path / "module.py"
    module.write_text("import sys\nimport os\n")

    problems = run_formatters(tmp_path)

    assert problems == ["ruff is not on the path", "djlint is not on the path"]
    assert module.read_text() == "import sys\nimport os\n"


def test_a_formatter_that_fails_is_reported_with_what_it_said(tmp_path, monkeypatch):
    executables = tmp_path / "bin"
    executables.mkdir()
    ruff = executables / "ruff"
    ruff.write_text("#!/bin/sh\necho 'unknown field `lint.nope`' >&2\nexit 2\n")
    ruff.chmod(0o700)
    monkeypatch.setenv("PATH", str(executables))

    problems = run_formatters(tmp_path)

    assert problems == [
        "ruff exited with 2: unknown field `lint.nope`",
        "djlint is not on the path",
    ]
