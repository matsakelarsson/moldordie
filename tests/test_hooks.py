"""Unit tests for the hooks"""

import os
from pathlib import Path

import pytest

from hooks.post_gen_project import append_to_gitignore_file
from hooks.post_gen_project import envs_unused
from hooks.post_gen_project import normalize_context
from hooks.post_gen_project import remove_celery_files
from hooks.post_gen_project import remove_channels_files

PROJECT_SLUG = "my_test_project"


@pytest.fixture
def working_directory(tmp_path):
    prev_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(prev_cwd)


def test_append_to_gitignore_file(working_directory):
    gitignore_file = working_directory / ".gitignore"
    gitignore_file.write_text("node_modules/\n")
    append_to_gitignore_file(".envs/*")
    linesep = os.linesep.encode()
    assert gitignore_file.read_bytes() == b"node_modules/" + linesep + b".envs/*" + linesep
    assert gitignore_file.read_text() == "node_modules/\n.envs/*\n"


def test_normalize_context_lowercases_only_the_flags_on_a_copy():
    context = {"use_docker": "Y", "cloud_provider": "AWS", "project_name": "Yes Project"}
    assert normalize_context(context) == {
        "use_docker": "y",
        "cloud_provider": "AWS",
        "project_name": "Yes Project",
    }
    assert context["use_docker"] == "Y"


@pytest.mark.parametrize(
    ("use_docker", "use_heroku", "expected"),
    [("n", "n", True), ("y", "n", False), ("n", "y", False), ("y", "y", False)],
)
def test_envs_unused_when_neither_docker_nor_heroku(use_docker, use_heroku, expected):
    assert envs_unused({"use_docker": use_docker, "use_heroku": use_heroku}) is expected


@pytest.fixture
def channels_files(tmp_path):
    """The files that only exist for ``realtime=channels``."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "websocket.py").touch()
    tests_path = tmp_path / PROJECT_SLUG / "tests"
    tests_path.mkdir(parents=True)
    (tests_path / "__init__.py").touch()
    (tests_path / "test_websocket.py").touch()
    return tests_path


def test_remove_channels_files_drops_the_package_when_only_the_websocket_test_lives_there(tmp_path, channels_files):
    remove_channels_files(tmp_path, PROJECT_SLUG)
    assert not (tmp_path / "config" / "websocket.py").exists()
    assert not channels_files.exists()


def test_remove_channels_files_keeps_other_tests(tmp_path, channels_files):
    other_test = channels_files / "test_urls.py"
    other_test.touch()
    remove_channels_files(tmp_path, PROJECT_SLUG)
    assert not (channels_files / "test_websocket.py").exists()
    assert other_test.exists()
    assert (channels_files / "__init__.py").exists()


@pytest.fixture
def celery_files(tmp_path):
    """The Celery entry point next to the tasks example that every project keeps."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "celery_app.py").touch()
    users_path = tmp_path / PROJECT_SLUG / "users"
    (users_path / "tests").mkdir(parents=True)
    (users_path / "tasks.py").touch()
    (users_path / "tests" / "test_tasks.py").touch()
    return tmp_path


def test_remove_celery_files_keeps_the_tasks_example(celery_files):
    remove_celery_files(celery_files)
    assert not (celery_files / "config" / "celery_app.py").exists()
    users_path = celery_files / PROJECT_SLUG / "users"
    assert (users_path / "tasks.py").exists()
    assert (users_path / "tests" / "test_tasks.py").exists()
